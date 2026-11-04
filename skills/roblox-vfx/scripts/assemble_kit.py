#!/usr/bin/env python3
"""Assemble a game's VFX kit from MANY harvested recipes, bake the look in, and
check the kit the way the game will drive it.

    python assemble_kit.py --lib "<lib>" --spec kit_spec.json --out <game>/work/vfx \
        --names <game>/design/vfx.json
    python assemble_kit.py --self-test

WHY (2026-10-08, a 45-effect creature game). Three defects this exists for:

  1. curate.py takes ONE source recipe per effect. A real game effect is often
     layers from several packs (a ring from one, sparks from another), and the
     library's nature sprites (leaf shards, petals-ish spindles) only exist as
     single layers. Hand-merging JSON per effect is where layers get lost.
  2. Tint/scale were RUNTIME-only (VFXKit.build opts), so the look of an effect
     lived in 45 call sites instead of the recipe, and nothing checked a
     pale-stage LightEmission cap (SKILL.md trap 15). Here tint (same luminance
     math as VFXKit's tintSeq), scale, LightEmission and Brightness caps are BAKED
     into the recipe JSON, and every changed value is logged in "edits".
  4. (added later the same day) A BLACK-BACKED sprite - opaque, with black where
     it should be transparent - only works additively, at LightEmission 1, where
     black adds nothing. The pale-stage cap pulled those to 0.4 and every one drew
     a black or grey SQUARE in Studio (HazeSting's star sat on a black tile, the
     'Specs' leaf shards were grey diamonds). Measured from the texture cache:
     black_backed() reads the cached PNG's border, and such layers get
     LightEmission 1 with Brightness held at 1 instead of the cap. check_kit fails
     a black-backed layer below LightEmission 1.
  3. The silent trap: build() fires nothing. handle.emit() fires ONLY burst
     layers and setEnabled() ONLY continuous ones. A "burst" effect with a
     continuous layer, or a "loop" effect with a burst layer, passes
     verify_vfx.py and shows nothing in game. check_kit() fails on it, on loops
     that would start streaming at build (Enabled=true), on caps, on loop budgets,
     and on spec names with no recipe (a verifier must find its own target).

Spec format (JSON):
  {"defaults": {"le_max": 0.4, "bright_max": 2, "loop_budget": 120},
   "templates": {"NAME": {layer fields}},           # reusable layer bases
   "effects": [{"name", "mode": "burst|loop|trail|both", "tint": "#hex", "scale": 1,
                "offset": [x,y,z] (hint only), "confidence": "high|check",
                "gap": "what the library could not supply", "notes",
                "layers": [{"src": "Stem#i", "template": NAME, "count": n | "rate": r,
                            "tint", "scale", "lifetime_mul", "texture_from": "Stem#i",
                            "set": {Prop: value}}]}]}
  set shorthands: Size/Transparency/Squash number -> flat NumberSequence, list of
  [t,v] -> sequence; Lifetime/Speed/RotSpeed [a,b] -> NumberRange;
  Acceleration [x,y,z]; EmissionDirection/Orientation/Shape "Top" etc.
"""
from __future__ import annotations

import argparse
import copy
import json
import math
import os
import sys
import tempfile
from pathlib import Path

ENUMS = {"EmissionDirection": "NormalId", "Orientation": "ParticleOrientation",
         "Shape": "ParticleEmitterShape", "FlipbookLayout": "ParticleFlipbookLayout",
         "FlipbookMode": "ParticleFlipbookMode"}
SEQ = {"Size", "Transparency", "Squash", "WidthScale"}
RANGE = {"Lifetime", "Speed", "RotSpeed", "Rotation", "FlipbookFramerate"}


def hexrgb(h):
    h = h.lstrip("#")
    return [int(h[i:i + 2], 16) / 255 for i in (0, 2, 4)]


def tint_seq(cs, c):
    """Identical to VFXKit tintSeq: keep luminance, replace hue."""
    out = []
    for kp in cs["ColorSequence"]:
        r, g, b = kp[1]
        lum = 0.2126 * r + 0.7152 * g + 0.0722 * b
        out.append([kp[0], [round(min(1, max(0, ch * lum * 1.6)), 4) for ch in c]])
    return {"ColorSequence": out}


def typed(k, v):
    if k in SEQ:
        if isinstance(v, (int, float)):
            return {"NumberSequence": [[0, v, 0], [1, v, 0]]}
        return {"NumberSequence": [[t, val, 0] for t, val in v]}
    if k in RANGE and isinstance(v, list):
        return {"NumberRange": v}
    if k == "Acceleration":
        return {"Vector3": v}
    if k == "SpreadAngle":
        return {"Vector2": v}
    if k in ENUMS and isinstance(v, str) and "." not in v:
        return {"Enum": f"{ENUMS[k]}.{v}"}
    return v


def scale_props(p, k):
    if "Size" in p and "NumberSequence" in p["Size"]:
        p["Size"] = {"NumberSequence": [[t, round(v * k, 4), round(e * k, 4)] for t, v, *e2 in p["Size"]["NumberSequence"]
                                        for e in [(e2[0] if e2 else 0)]]}
    if "Speed" in p and "NumberRange" in p["Speed"]:
        p["Speed"] = {"NumberRange": [round(x * k, 4) for x in p["Speed"]["NumberRange"]]}
    if "Acceleration" in p and "Vector3" in p["Acceleration"]:
        p["Acceleration"] = {"Vector3": [round(x * k, 4) for x in p["Acceleration"]["Vector3"]]}


def load_layer(rdir, ref):
    stem, _, idx = ref.partition("#")
    rec = json.loads((rdir / f"{stem}.json").read_text(encoding="utf-8"))
    return copy.deepcopy(rec["layers"][int(idx or 1) - 1])


_BB_CACHE: dict = {}


def black_backed(rdir, texture) -> bool:
    """True when the cached sprite is opaque at its border with near-black there:
    a texture authored for additive blending (see WHY 4)."""
    tid = "".join(ch for ch in str(texture or "") if ch.isdigit())
    if not tid:
        return False
    if tid in _BB_CACHE:
        return _BB_CACHE[tid]
    png = Path(rdir).parent / ".cache" / "tex" / f"{tid}.png"
    out = False
    if png.exists():
        try:
            from PIL import Image
            im = Image.open(png).convert("RGBA")
            w, h = im.size
            pts = [(0, 0), (w - 1, 0), (0, h - 1), (w - 1, h - 1), (w // 2, 0), (0, h // 2), (w - 1, h // 2), (w // 2, h - 1)]
            px = [im.getpixel(p) for p in pts]
            out = sum(1 for q in px if q[3] > 200 and max(q[:3]) < 40) >= 4
        except Exception:
            out = False
    _BB_CACHE[tid] = out
    return out


def build_effect(rdir, eff, defaults, templates):
    le_max = eff.get("le_max", defaults.get("le_max", 0.4))
    br_max = eff.get("bright_max", defaults.get("bright_max", 2))
    layers, sources = [], []
    for n, spec in enumerate(eff["layers"], 1):
        spec = {**templates.get(spec.get("template", ""), {}), **spec}
        L = load_layer(rdir, spec["src"])
        edits = []
        p = L["props"]
        src = spec["src"]
        if spec.get("texture_from"):
            t = load_layer(rdir, spec["texture_from"])["props"]
            for k in ("Texture", "FlipbookLayout", "FlipbookMode", "FlipbookFramerate", "FlipbookStartRandom"):
                if k in t and t.get(k) != p.get(k):
                    edits.append(f"{k} <- {spec['texture_from']}")
                    p[k] = t[k]
            src += f" +texture {spec['texture_from']}"
        for k, v in (spec.get("set") or {}).items():
            tv = typed(k, v)
            edits.append(f"{k}: {json.dumps(p.get(k))[:60]} -> {json.dumps(tv)[:60]}")
            p[k] = tv
        k = spec.get("scale", eff.get("scale", 1)) or 1
        if k != 1 and L["class"] == "ParticleEmitter":
            scale_props(p, k)
        if L["class"] in ("Trail", "Beam") and L.get("endpoints"):
            eps = L["endpoints"]
            mid = [(eps[0]["offset"][i] + eps[1]["offset"][i]) / 2 for i in range(3)]
            for e in eps:
                e["offset"] = [round((e["offset"][i] - mid[i]) * k, 4) for i in range(3)]
            edits.append(f"endpoints recentred on the anchor, x{k}")
        tint = spec.get("tint", eff.get("tint"))
        if tint and isinstance(p.get("Color"), dict) and "ColorSequence" in p["Color"]:
            p["Color"] = tint_seq(p["Color"], hexrgb(tint))
        if spec.get("lifetime_mul"):
            m = spec["lifetime_mul"]
            if isinstance(p.get("Lifetime"), dict):
                p["Lifetime"] = {"NumberRange": [round(x * m, 4) for x in p["Lifetime"]["NumberRange"]]}
            elif isinstance(p.get("Lifetime"), (int, float)):
                p["Lifetime"] = round(p["Lifetime"] * m, 4)
            edits.append(f"Lifetime x{m}")
        le = p.get("LightEmission")
        if L["class"] == "ParticleEmitter" and black_backed(rdir, p.get("Texture")):
            L["black_backed"] = True
            if le != 1:
                edits.append(f"LightEmission {le} -> 1 (black-backed sprite needs additive)")
                p["LightEmission"] = 1
            br0 = p.get("Brightness")
            if isinstance(br0, (int, float)) and br0 > 1:
                edits.append(f"Brightness {br0:.3g} -> 1 (additive on a pale stage)")
                p["Brightness"] = 1
        elif isinstance(le, (int, float)) and le > le_max:
            edits.append(f"LightEmission {le:.2f} -> {le_max} (pale-stage cap)")
            p["LightEmission"] = le_max
        br = p.get("Brightness")
        if L["class"] == "ParticleEmitter" and isinstance(br, (int, float)) and br > br_max:
            edits.append(f"Brightness {br:.3g} -> {br_max} (pale-stage cap)")
            p["Brightness"] = br_max
        harvested = copy.deepcopy(L.get("emit") or {})
        mode = eff["mode"]
        if L["class"] == "ParticleEmitter":
            if mode == "both":
                # 2026-10-09 (a 143-recipe roster): ONE recipe used as a move's travel
                # (setEnabled on a flying carrier) AND its impact (emit()). Per layer:
                # "count" -> burst, "rate" -> continuous. Exactly one of them.
                if ("count" in spec) == ("rate" in spec):
                    raise SystemExit(f"{eff['name']} layer {n}: mode 'both' needs exactly one of count/rate")
            if mode == "burst" or (mode == "both" and "count" in spec):
                L["emit"] = {"mode": "burst", "count": int(spec["count"])}
                p["Rate"] = 0
            else:
                L["emit"] = {"mode": "continuous"}
                p["Rate"] = spec["rate"]
            p["Enabled"] = False  # nothing streams until the game says so
        elif L["class"] == "Trail":
            L["emit"] = {"mode": "continuous"}
            p["Enabled"] = False
        L["harvested_emit"] = harvested
        L["offset"] = spec.get("offset", [0, 0, 0])  # centred: harvested offsets ignored (trap 16)
        L["name"] = f"{n}_{L['name'].split('/')[-1]}".replace(" ", "_")
        L["source"] = src
        L["edits"] = edits
        L.pop("renders_in_place", None)
        layers.append(L)
        sources.append(src)
    refs = sorted({str(L["props"].get("Texture")) for L in layers if L["props"].get("Texture")})
    lives = [x for L in layers for x in ([L["props"]["Lifetime"]["NumberRange"][1]]
                                         if isinstance(L["props"].get("Lifetime"), dict) else [L["props"].get("Lifetime", 1)])]
    return {"name": eff["name"], "duration": math.ceil(max(lives + [0.5]) * 100) / 100,
            "texture_portable": all(r.startswith("rbxasset://") for r in refs),
            "texture_refs": refs, "kit_mode": eff["mode"], "sources": sources, "layers": layers}


def budget(rec):
    tot = 0.0
    for L in rec["layers"]:
        if L["class"] != "ParticleEmitter":
            continue
        life = L["props"]["Lifetime"]["NumberRange"][1]
        if L["emit"]["mode"] == "burst":
            tot += L["emit"]["count"]
        else:
            tot += L["props"]["Rate"] * life
    return round(tot, 1)


def check_kit(recs, defaults, names=None):
    """Fail on anything that builds fine and then shows nothing (or too much) in game."""
    fails = []
    le_max, br_max = defaults.get("le_max", 0.4), defaults.get("bright_max", 2)
    for r in recs:
        n, mode = r["name"], r["kit_mode"]
        pes = [L for L in r["layers"] if L["class"] == "ParticleEmitter"]
        for L in r["layers"]:
            p = L["props"]
            if L.get("black_backed"):
                if p.get("LightEmission") != 1:
                    fails.append(f"{n}.{L['name']}: black-backed sprite below LightEmission 1 draws a square")
            elif isinstance(p.get("LightEmission"), (int, float)) and p["LightEmission"] > r.get("le_max", le_max) + 1e-9:
                fails.append(f"{n}.{L['name']}: LightEmission {p['LightEmission']} over cap")
            if L["class"] == "ParticleEmitter" and p.get("Brightness", 0) > br_max + 1e-9:
                fails.append(f"{n}.{L['name']}: Brightness {p['Brightness']} over cap")
            if L["class"] == "ParticleEmitter" and p.get("Enabled") is not False:
                fails.append(f"{n}.{L['name']}: Enabled at build - streams before the game asks")
        if mode == "burst":
            if not pes:
                fails.append(f"{n}: burst effect with no ParticleEmitter - emit() fires nothing")
            for L in pes:
                if L["emit"].get("mode") != "burst" or not L["emit"].get("count") or L["props"].get("Rate") != 0:
                    fails.append(f"{n}.{L['name']}: in a burst effect but not a Rate=0 burst layer - emit() skips it")
        elif mode == "loop":
            if not any(L["emit"].get("mode") == "continuous" and L["props"].get("Rate", 0) > 0 for L in pes):
                fails.append(f"{n}: loop effect with no streaming layer - setEnabled(true) shows nothing")
            for L in pes:
                if L["emit"].get("mode") == "burst":
                    fails.append(f"{n}.{L['name']}: burst layer in a loop - setEnabled never fires it")
            b = budget(r)
            if b > r.get("loop_budget", defaults.get("loop_budget", 120)):
                fails.append(f"{n}: ~{b} live particles while on, over the loop budget")
        elif mode == "both":
            bursts = [L for L in pes if L["emit"].get("mode") == "burst"]
            streams = [L for L in pes if L["emit"].get("mode") == "continuous"]
            ribbons = [L for L in r["layers"] if L["class"] == "Trail"]
            if not bursts:
                fails.append(f"{n}: travel+impact effect with no burst layer - emit() at the hit fires nothing")
            if not any(L["props"].get("Rate", 0) > 0 for L in streams) and not any(
                    len(L.get("endpoints") or []) == 2 for L in ribbons):
                fails.append(f"{n}: travel+impact effect with no streaming layer - setEnabled on the carrier shows nothing")
            for L in bursts:
                if not L["emit"].get("count") or L["props"].get("Rate") != 0:
                    fails.append(f"{n}.{L['name']}: burst layer that is not Rate=0 with a count")
            for L in streams:
                if L["props"].get("Rate", 0) <= 0:
                    fails.append(f"{n}.{L['name']}: continuous layer with Rate 0 never emits")
            b = sum(L["props"]["Rate"] * L["props"]["Lifetime"]["NumberRange"][1] for L in streams)
            if b > r.get("loop_budget", defaults.get("loop_budget", 120)):
                fails.append(f"{n}: ~{b:.0f} live travel particles, over the loop budget")
        elif mode == "trail":
            tr = [L for L in r["layers"] if L["class"] == "Trail"]
            if not tr or any(len(L.get("endpoints") or []) != 2 for L in tr):
                fails.append(f"{n}: trail effect without a two-endpoint Trail - draws nothing")
        else:
            fails.append(f"{n}: unknown mode {mode!r}")
    if names is not None:
        have = {r["name"] for r in recs}
        for x in sorted(set(names) - have):
            fails.append(f"{x}: named in the spec, no recipe built")
        for x in sorted(have - set(names)):
            fails.append(f"{x}: built but not in the spec")
    return fails


def write_atomic(path: Path, text: str):
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=path.parent, suffix=".tmp")
    with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as f:
        f.write(text)
    os.replace(tmp, path)


def self_test():
    base = {"name": "X", "kit_mode": "burst", "layers": [{"name": "a", "class": "ParticleEmitter",
            "emit": {"mode": "burst", "count": 3},
            "props": {"Rate": 0, "Enabled": False, "LightEmission": 0.2, "Brightness": 1,
                      "Lifetime": {"NumberRange": [0.5, 1]}}}]}
    d = {"le_max": 0.4, "bright_max": 2, "loop_budget": 50}
    assert not check_kit([base], d, ["X"]), check_kit([base], d, ["X"])
    cases = {
        "burst effect with a continuous layer": lambda r: r["layers"][0].__setitem__("emit", {"mode": "continuous"}),
        "loop effect built from burst layers": lambda r: r.__setitem__("kit_mode", "loop"),
        "loop enabled at build": lambda r: r["layers"][0]["props"].__setitem__("Enabled", True),
        "LightEmission over cap": lambda r: r["layers"][0]["props"].__setitem__("LightEmission", 1),
        "spec name missing": None,
        "trail without endpoints": lambda r: r.__setitem__("kit_mode", "trail"),
        "travel+impact effect with no stream": lambda r: r.__setitem__("kit_mode", "both"),
    }
    ok = 0
    for label, sab in cases.items():
        r = copy.deepcopy(base)
        names = ["X", "Y"] if sab is None else ["X"]
        if sab:
            sab(r)
        caught = bool(check_kit([r], d, names))
        ok += caught
        print(f"  {'caught' if caught else 'MISSED'}  {label}")
    print(f"self-test {ok}/{len(cases)}")
    return 0 if ok == len(cases) else 1


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--lib")
    ap.add_argument("--spec")
    ap.add_argument("--out", help="dir: writes recipes/<Name>.json + manifest.json")
    ap.add_argument("--names", help="design vfx.json whose effect names the kit must cover exactly")
    ap.add_argument("--self-test", action="store_true")
    a = ap.parse_args()
    if a.self_test:
        return self_test()
    lib = Path(a.lib)
    rdir = lib / "recipes" if (lib / "recipes").is_dir() else lib
    spec = json.loads(Path(a.spec).read_text(encoding="utf-8"))
    defaults, templates = spec.get("defaults", {}), spec.get("templates", {})
    out = Path(a.out)
    recs, man = [], []
    for eff in spec["effects"]:
        r = build_effect(rdir, eff, defaults, templates)
        for k in ("le_max", "loop_budget"):
            if k in eff:
                r[k] = eff[k]
        recs.append(r)
        write_atomic(out / "recipes" / f"{r['name']}.json", json.dumps(r, indent=1))
        les = [L["props"].get("LightEmission", 0) for L in r["layers"]]
        man.append({
            "name": r["name"],
            "mode": eff["mode"],
            "drive": {"burst": "h = VFXKit.build(name, part, opts); h.emit(mult)",
                      "loop": "h = VFXKit.build(name, part, opts); h.setEnabled(true) ... h.setEnabled(false)/h.destroy()",
                      "trail": "h = VFXKit.build(name, seedPart); h.setEnabled(true) on throw; h.destroy() on land",
                      "both": "travel: h = VFXKit.build(name, carrier, opts); h.setEnabled(true) while flying, h.setEnabled(false) on arrival; "
                              "impact: h = VFXKit.build(name, anchor, opts); h.emit(mult)"}[eff["mode"]],
            "source_recipes": sorted({s.split(" ")[0].split("#")[0] for s in r["sources"]}),
            "source_layers": r["sources"],
            "harvest_kind": eff.get("kind", "harvested"),
            "tint": eff.get("tint") or sorted({l.get("tint") for l in eff["layers"] if l.get("tint")}) or None,
            "scale": eff.get("scale", 1),
            "offset_hint": eff.get("offset", [0, 0, 0]),
            "runtime_opts": eff.get("runtime_opts"),
            "max_light_emission": max(les) if les else 0,
            "particle_budget": budget(r),
            "budget_meaning": {"loop": "max live particles while enabled", "both": "burst particles per emit(1) + streaming particles live while enabled"}.get(eff["mode"], "particles per emit(1)"),
            "edited_values": sum(len(L["edits"]) for L in r["layers"]),
            "gap": eff.get("gap"),
            "notes": eff.get("notes", ""),
            "confidence": eff.get("confidence", "check"),
        })
    names = None
    if a.names:
        names = [e["name"] for e in json.loads(Path(a.names).read_text(encoding="utf-8"))["effects"]]
    fails = check_kit(recs, defaults, names)
    write_atomic(out / "manifest.json", json.dumps({"effects": man, "kit_check_failures": fails}, indent=1))
    print(f"{len(recs)} recipes -> {out / 'recipes'}")
    for f in fails:
        print("KIT FAIL", f)
    print("kit check:", "PASS" if not fails else f"{len(fails)} failure(s)")
    return 1 if fails else 0


if __name__ == "__main__":
    raise SystemExit(main())
