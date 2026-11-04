"""Numeric critic gate for a sim effect definition.

    python critic_gate.py ../sim/effects/void_lance.json [--metrics m.json]

Checks the effect against its own BRIEF (the "brief" block the builder
writes), the corpus skeleton for its category (references/corpus/STATS.json)
and the rules that held across every style family (references/styles/STYLES.md).
--metrics takes app.strip() metrics (list of {t, luma, sat, hot}) sampled
densely over the effect, for the timing checks that need pixels.

Prints PASS / WARN / FAIL per check; exit code 1 if anything FAILs.
A gate is not taste: passing means "no measurable amateur defect", and the
blind review in references/DESIGN.md still has to run.
"""
import argparse
import colorsys
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
STATS = HERE.parent / "references" / "corpus" / "STATS.json"
TIER_BUDGET = {"basic": (0.3, 0.8), "skill": (0.8, 2.0), "big skill": (2.0, 4.0), "ultimate": (4.0, 15.0)}
DT = 1 / 60

results = []


def say(level, name, msg):
    results.append((level, name, msg))


def hexrgb(h):
    h = h.lstrip("#")
    return [int(h[i:i + 2], 16) / 255 for i in (0, 2, 4)]


def hue(h):
    r, g, b = hexrgb(h)
    return colorsys.rgb_to_hsv(r, g, b)


def walk(insts, path=""):
    for s in insts:
        p = f"{path}.{s['name']}" if path else s["name"]
        yield p, s
        yield from walk(s.get("children", []), p)


def phase(brief, name):
    for ph in brief.get("phases", []):
        if ph["name"] == name:
            return ph
    return None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("effect")
    ap.add_argument("--metrics")
    a = ap.parse_args()
    d = json.loads(Path(a.effect).read_text(encoding="utf-8"))
    brief = d.get("brief")
    if not brief:
        say("FAIL", "brief", "no 'brief' block: write the design brief first (references/DESIGN.md step 1)")
        report()
        return
    need = ["category", "tier", "style", "shape", "dominant", "accent", "signature_beats", "phases"]
    miss = [k for k in need if not brief.get(k)]
    say("FAIL" if miss else "PASS", "brief", f"missing {miss}" if miss else "complete")

    rel = phase(brief, "release") or phase(brief, "impact")
    res = phase(brief, "residue")
    ant = phase(brief, "anticipation")
    main_t0 = rel["t0"] if rel else 0.0
    main_t1 = res["t0"] if res else d.get("duration", 1)
    main_len = max(1e-3, main_t1 - main_t0)

    # tier budget (main event, excluding residue)
    lo, hi = TIER_BUDGET.get(brief["tier"], (0, 99))
    total_main = main_t1 - (ant["t0"] if ant else main_t0)
    lvl = "PASS" if lo * 0.7 <= total_main <= hi * 1.3 else "WARN"
    say(lvl, "tier budget", f"anticipation+main {total_main:.2f}s vs {brief['tier']} {lo}-{hi}s")

    # corpus skeleton
    stats = json.loads(STATS.read_text()) if STATS.exists() else {"groups": {}}
    g = stats["groups"].get(f"cat:{brief['category']}")
    if ant and rel:
        ratio = (ant["t1"] - ant["t0"]) / max(DT, rel["t1"] - rel["t0"])
        if g and g.get("anticipation_to_release"):
            q = g["anticipation_to_release"]
            # cinematic ratios shrink in gameplay tiers: accept down to 1/4 of p25 for basic/skill
            floor = q["p25"] * (0.25 if brief["tier"] in ("basic", "skill") else 0.6)
            say("PASS" if ratio >= floor else "WARN", "anticipation:release", f"{ratio:.1f} (corpus {q['median']} [{q['p25']}..{q['p75']}], floor {floor:.1f})")
        else:
            say("PASS" if ratio >= 2 else "WARN", "anticipation:release", f"{ratio:.1f} (want >= 2)")
    if res:
        rr = (res["t1"] - res["t0"]) / main_len
        q = g.get("residue_to_main") if g else None
        if q:
            say("PASS" if q["p25"] * 0.5 <= rr <= q["p75"] * 2 else "WARN", "residue:main", f"{rr:.2f} (corpus {q['median']} [{q['p25']}..{q['p75']}])")
        else:
            say("PASS" if rr >= 0.5 else "WARN", "residue:main", f"{rr:.2f} (want residue to outlast the hit)")
    else:
        say("WARN", "residue", "no residue phase: pro effects leave something behind")

    # layers
    insts = list(walk(d.get("instances", [])))
    emitters = [(p, s) for p, s in insts if s.get("class") == "ParticleEmitter"]
    visual = [(p, s) for p, s in insts if s.get("class") in ("ParticleEmitter", "Beam", "Trail", "MeshPart", "Highlight", "PointLight", "ColorCorrectionEffect")]
    n = len(visual)
    q = g.get("layer_count") if g else None
    want = q["p25"] if q else 5
    say("PASS" if n >= want else "WARN", "layer count", f"{n} visual layers (corpus p25 {want})")
    lifes = {json.dumps(s.get("props", {}).get("Lifetime")) for _, s in emitters}
    say("PASS" if len(lifes) >= min(3, len(emitters)) else "WARN", "distinct lifetimes", f"{len(lifes)} distinct of {len(emitters)} emitters (layers must die at different times)")

    # linear whole-life fades on body layers
    lin = []
    for p, s in emitters:
        t = s.get("props", {}).get("Transparency")
        if isinstance(t, dict) and "NumberSequence" in t:
            k = t["NumberSequence"]
            if len(k) == 2 and k[0][1] <= 0.1 and k[1][1] >= 0.9:
                lin.append(p.split(".")[-1])
    say("PASS" if len(lin) <= max(1, len(emitters) // 3) else "WARN", "linear fades", f"{len(lin)} emitters fade linearly from birth: {lin[:6]} (hold, then fade late)")

    # flashes from the timeline
    tl = sorted(d.get("timeline", []), key=lambda e: e.get("t", 0))
    cc = {p for p, s in insts if s.get("class") == "ColorCorrectionEffect"}
    flashes = []
    for i, e in enumerate(tl):
        if e.get("target") not in cc:
            continue   # only screen-wide ColorCorrection flashes count (not lights)
        if e.get("do") == "set" and e.get("prop") == "Brightness" and isinstance(e.get("value"), (int, float)) and e["value"] >= 0.5:
            off = next((f for f in tl[i + 1:] if f.get("target") == e.get("target") and f.get("prop") == "Brightness"), None)
            dur = (off["t"] - e["t"]) if off else None
            flashes.append((e["t"], dur, off and off.get("do")))
    for t, dur, kind in flashes:
        frames = round(dur / DT) if dur is not None else None
        held = brief["tier"] in ("big skill", "ultimate") and "whiteout" in " ".join(brief.get("signature_beats", [])).lower()
        if frames is None:
            say("WARN", "flash", f"flash at {t:.2f}s never switched off")
        elif frames <= 2 or held:
            say("PASS", "flash", f"flash at {t:.2f}s lasts {frames} frame(s){' (held whiteout by brief)' if held and frames > 2 else ''}")
        else:
            say("FAIL", "flash", f"flash at {t:.2f}s lasts {frames} frames: hard-off in 1-2 frames unless the brief asks for a held whiteout")
    if brief["tier"] in ("basic",) and flashes:
        say("WARN", "flash tier", "basic attacks should not flash the screen")
    if len(flashes) >= 2:
        span = flashes[-1][0] - flashes[0][0]
        rate = (len(flashes) - 1) / max(span, 1e-3)
        say("FAIL" if rate > 3 else "PASS", "strobe rate", f"{rate:.1f} full-screen flashes/s (photosensitivity limit 3)")

    # palette
    try:
        hd, sd, vd = hue(brief["dominant"])
        ha, sa_, va = hue(brief["accent"])
        dh = min(abs(hd - ha), 1 - abs(hd - ha)) * 360
        ok = dh >= 50 or sa_ < 0.15 or va > 0.95
        say("PASS" if ok else "WARN", "accent", f"hue distance {dh:.0f} deg (want a complementary/cool contrast or a white accent)")
    except Exception as ex:
        say("WARN", "accent", f"could not read palette: {ex}")

    # anime slashes need the dark under-layer
    if brief["style"] == "anime_cel" and brief["category"] == "slash":
        dark = [p for p, s in emitters if _dark(s)]
        say("PASS" if dark else "FAIL", "dark under-layer", f"{len(dark)} dark LightEmission-0 layer(s) under the strokes")

    # pixel checks
    if a.metrics:
        m = json.loads(Path(a.metrics).read_text())
        within = [x for x in m if main_t0 - 1e-6 <= x["t"] <= main_t1 + 1e-6]
        if within:
            peak = max(within, key=lambda x: x["luma"])
            frac = (peak["t"] - main_t0) / main_len
            say("PASS" if frac <= 0.3 else "WARN", "peak early", f"brightest frame at {frac * 100:.0f}% of the main event (want <= 25-30%)")
            hot = max(x["hot"] for x in within)
            say("PASS" if hot < 0.35 or flashes else "WARN", "wash", f"max {hot * 100:.0f}% of frame saturated (>250) outside flashes")
    report()


def _dark(s):
    pr = s.get("props", {})
    c = pr.get("Color")
    le = pr.get("LightEmission", 0)
    try:
        rgb = c["ColorSequence"][0][1]
        return (0.299 * rgb[0] + 0.587 * rgb[1] + 0.114 * rgb[2]) < 0.2 and le <= 0.1
    except Exception:
        return False


def report():
    w = max(len(n) for _, n, _ in results) if results else 10
    for lvl, n, msg in results:
        print(f"{lvl:4}  {n:<{w}}  {msg}")
    fails = sum(1 for l, _, _ in results if l == "FAIL")
    warns = sum(1 for l, _, _ in results if l == "WARN")
    print(f"\n{fails} FAIL, {warns} WARN, {len(results) - fails - warns} PASS")
    sys.exit(1 if fails else 0)


if __name__ == "__main__":
    main()
