"""Polish passes from a 100-move anime-style showcase (v5, verified in Studio 2026-10-29), the quality bar for this skill.
Run polish(d) on every finished effect definition, last, before export.
Each pass is a Studio-measured fix and records what it touched under d["v5"].

From the audit of the v3/v4 takes (2026-10-29):
  domes()   every explosion / energy dome was a lumpy_sphere with the mesh_fire_shell SurfaceAppearance, and in Studio
            it read as a dull grey glass blob (Spirit Bomb, Giant Rasengan, Rasenshuriken, Black Getsuga...). It
            becomes a ForceField-material ball (Roblox's animated energy shell, tinted) around a Neon core ball that
            follows its tweens at 0.6x the size and fades sooner: bright in the middle, energy at the edge.
  craters() the crater rims were rings of near-black slabs (stone_cel x a brown tint): retinted to the arena stone.
  auras()   aura() put its flame tongues under an Attachment, which ignores the emitter's Box shape: Kaio-ken and
            Ichigo's auras were born inside the body. Flames and Sparks move onto the Part (paths rewritten).
"""
import copy

DOME_MESH = "sim:lumpy_sphere"
SHELL_TEXTURES = ("sim:mesh_fire_shell",)
ARENA_STONE = (0.84, 0.85, 0.9)


def _sa(inst):
    return next((c for c in inst.get("children", []) if c.get("class") == "SurfaceAppearance"), None)


def _col(v, default=(1, 1, 1)):
    if isinstance(v, dict) and "Color3" in v:
        return list(v["Color3"])
    if isinstance(v, (list, tuple)):
        return list(v)
    return list(default)


def domes(d):
    names = {}
    for inst in d["instances"]:
        if inst.get("class") != "MeshPart" or inst.get("MeshId") != DOME_MESH or inst.get("name") in ("IFDome",) or inst.get("Material") == "Neon":
            continue
        sa = _sa(inst)
        if not sa or sa.get("props", {}).get("ColorMap") not in SHELL_TEXTURES:
            continue
        col = _col(sa["props"].get("Color"))
        hot = _col(sa["props"].get("EmissiveTint"), col)
        inst["class"] = "Part"
        inst["Shape"] = "Ball"
        inst.pop("MeshId", None)
        # the core takes the dome's most SATURATED colour: a pale mix bloomed to white glare on every dome (sim audit, v5)
        sat = lambda v: max(v) - min(v)
        core_col = col if sat(col) >= sat(hot) else hot
        inst["Material"] = "ForceField"
        # and so does the shell: in Studio a pale ForceField draws as clear glass with a white rim (Spirit Bomb,
        # v5 probe) while a saturated one shows its colour (Black Getsuga's crimson)
        inst["Color"] = [min(1, c * 1.15) for c in core_col]
        inst["children"] = [c for c in inst.get("children", []) if c.get("class") != "SurfaceAppearance"]
        inst.get("props", {}).pop("DoubleSided", None)
        core = {"class": "Part", "name": inst["name"] + "Core", "Shape": "Ball", "Material": "Neon", "Color": [min(1, c) for c in core_col],
                "Transparency": 1, "CFrame": list(inst["CFrame"]), "Size": [s * 0.6 for s in inst["Size"]], "children": []}
        if inst.pop("noCore", False):
            continue
        names[inst["name"]] = core
    if not names:
        return d
    d["instances"] += list(names.values())
    extra = []
    for e in d["timeline"]:
        tg = e.get("target")
        if tg not in names:
            continue
        c = copy.deepcopy(e)
        c["target"] = tg + "Core"
        prop = e.get("prop")
        if prop == "Size":
            for k in ("to", "from", "value"):
                if isinstance(c.get(k), list):
                    c[k] = [v * 0.6 for v in c[k]]
        elif prop == "Transparency":
            for k in ("to", "from", "value"):
                if isinstance(c.get(k), (int, float)):
                    c[k] = min(1.0, c[k] + 0.45)
            if e.get("do") == "tween" and isinstance(e.get("time"), (int, float)):
                c["time"] = e["time"] * 0.7                      # the core goes out first
        elif prop not in ("CFrame", None) and e.get("do") not in ("path", "spin"):
            continue
        extra.append(c)
    d["timeline"] += extra
    d.setdefault("v5", {})["domes"] = sorted(names)
    return d


def craters(d):
    n = 0
    for inst in d["instances"]:
        if inst.get("MeshId") == "sim:crater_rim":
            sa = _sa(inst)
            if sa:
                sa["props"]["Color"] = {"Color3": list(ARENA_STONE)}
                n += 1
    if n:
        d.setdefault("v5", {})["craters"] = n
    return d


AURA_SET = {"Flames", "Envelope", "Glow", "Sparks"}
AURA_SHAPED = ("Flames", "Sparks")


def auras(d):
    moved = []
    for inst in d["instances"]:
        if inst.get("class") != "Part":
            continue
        a = next((c for c in inst.get("children", []) if c.get("class") == "Attachment" and c.get("name") == "A"), None)
        if not a:
            continue
        names = {c.get("name") for c in a.get("children", [])}
        if not AURA_SET <= names:
            continue
        keep = [c for c in a["children"] if c.get("name") not in AURA_SHAPED]
        go = [c for c in a["children"] if c.get("name") in AURA_SHAPED]
        a["children"] = keep
        inst["children"] = list(inst["children"]) + go
        moved.append(inst["name"])
    if not moved:
        return d
    for e in d["timeline"]:
        tg = e.get("target")
        if not isinstance(tg, str):
            continue
        for nm in moved:
            for em in AURA_SHAPED:
                if tg == f"{nm}.A.{em}":
                    e["target"] = f"{nm}.{em}"
    d.setdefault("v5", {})["auras"] = moved
    return d


def ghosts(d):
    """Coloured afterimages were Neon silhouettes at 0.35 transparency: solid yellow/green blocks (Saitama, Deku).
    They stay coloured but go to at least 0.6 transparent, so they read as a blur, not a body."""
    n = 0
    for e in d["timeline"]:
        if e.get("do") == "ghost" and not e.get("keep"):
            tr = e.get("transparency", 0.35)
            if tr < 0.6:
                e["transparency"] = 0.6
                n += 1
    if n:
        d.setdefault("v5", {})["ghosts"] = n
    return d


def smoke(d):
    """slam()'s lingering smoke grew to fill the end close-ups (Sneeze, Normal Punch): smaller and see-through."""
    n = 0
    for inst in d["instances"]:
        if not str(inst.get("name", "")).endswith("Smoke"):
            continue
        for c in inst.get("children", []):
            if c.get("class") == "ParticleEmitter" and c.get("name") == "Puffs":
                p = c["props"] if "props" in c else c
                sz = p.get("Size")
                if isinstance(sz, dict) and "NumberSequence" in sz:
                    sz["NumberSequence"] = [[k[0], k[1] * 0.75] + list(k[2:]) for k in sz["NumberSequence"]]
                p["Transparency"] = {"NumberSequence": [[0, 0.3], [0.6, 0.55], [1, 1]]}
                n += 1
    if n:
        d.setdefault("v5", {})["smoke"] = n
    return d


def polish(d):
    return smoke(ghosts(auras(craters(domes(d)))))
