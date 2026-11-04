"""Builder for a cinematic sky-circle detonation, original design, structured
on the measured KonoSuba "Explosion" skeleton (a frame-by-frame
teardown of the anime clip: timings and growth curve only). Every visual comes from our own textures
(sim/tex) and Blender meshes (sim/mesh); nothing is copied.

    python build_explosion.py [--R 90] [--out explosion_crimson.json]

R is the final fireball radius in studs; everything else scales from it, so
the same skeleton gives a hand-grenade or a city-killer.

Phases (seconds, measured skeleton in brackets):
  0.0-2.9  stacked circles scale in, staggered, counter-rotating, mana sparks   [P0-P1]
  2.9      cut to a far, calm wide shot                                         [P2]
  3.0-3.45 light point drops, star glint + ring                                 [P3]
  3.50     one-frame white flash                                                [P4]
  3.52-4.3 fireball: 0 -> 0.7R in 0.2 s (Quart Out), then -> 1.0R by +0.8 s   [P5]
  4.3      squash to a wide dome, horizontal shock rings out to 5R              [P6]
  4.35-4.65 held whiteout, then cooling white -> cream -> yellow -> orange      [P7-P8]
  4.6-9    burn: spike skirt, ground glow, boiling puffs                        [P9]
  5.5-14   mushroom rises orange -> brown -> grey, condensation rings           [P10]
  8-14.5   ember rain, sky tint                                                 [P11]
"""
import argparse
import json
from pathlib import Path


def V3(x, y, z):
    return {"Vector3": [x, y, z]}


def NR(a, b=None):
    return {"NumberRange": [a, a if b is None else b]}


def NS(*k):
    return {"NumberSequence": [list(p) for p in k]}


def CS(*k):
    return {"ColorSequence": [[t, list(c)] for t, c in k]}


def C3(*c):
    return {"Color3": list(c)}


def hexc(h):
    h = h.lstrip("#")
    return [int(h[i:i + 2], 16) / 255 for i in (0, 2, 4)]


def E(e):
    return {"Enum": e}


def sa(colormap, color, emis=1.0, etint=(1, 1, 1), alpha=True):
    return {"class": "SurfaceAppearance", "name": "Look", "props": {
        "ColorMap": f"sim:{colormap}", "EmissiveMask": f"sim:{colormap}", "AlphaMode": E("AlphaMode.Transparency" if alpha else "AlphaMode.Overlay"),
        "Color": C3(*color), "EmissiveStrength": emis, "EmissiveTint": C3(*etint)}}


def mesh(name, mid, cf, size, transparency=1, material="SmoothPlastic", color=(1, 1, 1), children=None, double=True):
    return {"class": "MeshPart", "name": name, "MeshId": f"sim:{mid}", "Material": material, "Color": list(color),
            "Transparency": transparency, "CFrame": cf, "Size": size, "props": {"DoubleSided": double}, "children": children or []}


def build(R=90.0):
    inst, tl = [], []

    def at(t, **e):
        e["t"] = round(t, 4)
        tl.append(e)

    # ------------------------------------------------------------------ P0 circles
    Rc = R * 0.78
    base_y = R * 1.35
    radii = [1.0, 0.8, 0.62, 0.52, 0.62, 0.8, 0.95]
    tints = [hexc("#e88a82"), hexc("#c35673"), hexc("#e88a82"), hexc("#f3d54e"), hexc("#e88a82"), hexc("#c35673"), hexc("#f8d792")]
    for i, (rf, tint) in enumerate(zip(radii, tints)):
        y = base_y + i * R * 0.3
        t0 = 0.25 + i * 0.2
        layers = []
        for j, (layer, emis, dt, spin) in enumerate([("outer", 1.3, 0.0, 22), ("band", 1.5, 0.2, -30), ("inner", 1.3, 0.3, 38), ("core", 1.7, 0.38, -50)]):
            nm = f"C{i}{layer}"
            d = Rc * 2 * rf * (1 - 0.06 * j)
            layers.append(mesh(nm, "plane", [0, y + j * 0.08, 0, 0, i * 17, 0], [0.4, 0.05, 0.4], 1,
                               children=[sa(f"sigil_{layer}", tint, emis, tint)]))
            path = f"Circles.{nm}"
            at(t0 + dt, do="set", target=path, prop="Transparency", value=0.02)
            at(t0 + dt, do="tween", target=path, prop="Size", from_=None, to=[d, 0.05, d], time=0.42, style="Quart", dir="Out")
            at(t0 + dt, do="tween", target=path, prop="CFrame", by=[0, 0, 0, 0, spin * 3.0, 0], time=3.0, style="Linear")
        inst_c = layers
        inst.extend(inst_c) if False else None
        inst.append({"class": "Folder", "name": f"_c{i}", "children": []}) if False else None
        for L in layers:
            inst.append(L)
    # group circles under a Folder named Circles (paths above use it)
    circles = [x for x in inst if x["name"].startswith("C")]
    inst = [x for x in inst if not x["name"].startswith("C")]
    inst.append({"class": "Folder", "name": "Circles", "children": circles})

    # mana sparks drawn inward to the stack, cyan (complementary to the red)
    inst.append({"class": "Part", "name": "Mana", "Shape": "Ball", "CFrame": [0, base_y + R * 0.9, 0, 0, 0, 0], "Size": [R * 1.6, R * 1.6, R * 1.6], "Transparency": 1, "children": [
        {"class": "ParticleEmitter", "name": "Sparks", "props": {
            "Texture": "sim:spark_needle", "Shape": E("ParticleEmitterShape.Sphere"), "ShapeStyle": E("ParticleEmitterShapeStyle.Surface"),
            "ShapeInOut": E("ParticleEmitterShapeInOut.Inward"), "Rate": 0, "Lifetime": NR(0.35, 0.6), "Speed": NR(R * 0.9, R * 1.4),
            "Orientation": E("ParticleOrientation.VelocityParallel"), "Size": NS((0, R * 0.05, R * 0.02), (1, R * 0.02)),
            "Squash": NS((0, 1.2), (1, 1.2)), "Color": CS((0, hexc("#9fd4ff")), (1, hexc("#456cc9"))), "LightEmission": 1, "Brightness": 2.5,
            "Transparency": NS((0, 0.2), (0.8, 0.2), (1, 1))}}]})
    at(0.4, do="enable", target="Mana.Sparks", duration=2.4)
    at(0.4, do="set", target="Mana.Sparks", prop="Rate", value=140)

    # charge point under the stack + staff-style 4-point flare
    inst.append({"class": "Part", "name": "Charge", "CFrame": [0, base_y - R * 0.12, 0, 0, 0, 0], "Size": [1, 1, 1], "Transparency": 1, "children": [
        {"class": "Attachment", "name": "A", "children": [
            {"class": "ParticleEmitter", "name": "Glow", "props": {"Texture": "sim:glow_soft", "Rate": 0, "Lifetime": NR(2.6), "Speed": NR(0),
                "Size": NS((0, R * 0.1), (0.85, R * 0.55), (1, R * 0.05)), "Transparency": NS((0, 0.4), (0.85, 0.0), (1, 1)),
                "Color": CS((0, hexc("#f8d792")), (1, hexc("#ffffff"))), "LightEmission": 1, "Brightness": 2.2}},
            {"class": "ParticleEmitter", "name": "Flare", "props": {"Texture": "sim:impact_star4_2x2", "FlipbookLayout": E("ParticleFlipbookLayout.Grid2x2"),
                "FlipbookStartRandom": True, "FlipbookFramerate": NR(0), "Rate": 0, "Lifetime": NR(0.3), "Speed": NR(0),
                "Size": NS((0, R * 0.2), (0.15, R * 1.3), (1, R * 1.1)), "Transparency": NS((0, 0), (0.6, 0), (1, 1)),
                "Color": CS((0, hexc("#efebf6")), (1, hexc("#c88ed1"))), "LightEmission": 1, "Brightness": 3}}]}]})
    at(0.2, do="emit", target="Charge.A.Glow", count=1)
    at(2.55, do="emit", target="Charge.A.Flare", count=1)
    # circles compress into the point, then everything up there disappears
    for i in range(7):
        for layer in ("outer", "band", "inner", "core"):
            at(2.6, do="tween", target=f"Circles.C{i}{layer}", prop="Size", to=[0.5, 0.05, 0.5], time=0.28, style="Quart", dir="In")
    at(2.9, do="hide", target="Circles")
    at(2.9, do="hide", target="Charge")

    # ------------------------------------------------------------------ camera
    at(0.0, do="camera", pos=[R * 0.35, R * 0.35, R * 2.2], at=[0, base_y + R * 0.4, 0], fov=62)
    at(0.0, do="camera", pos=[R * 0.3, R * 0.3, R * 2.0], at=[0, base_y + R * 1.2, 0], fov=60, time=2.8, style="Sine", dir="InOut")
    at(2.9, do="camera", pos=[0, R * 0.28, R * 5.4], at=[0, R * 1.0, 0], fov=44)                    # the calm wide shot
    at(3.0, do="camera", pos=[0, R * 0.32, R * 5.0], at=[0, R * 1.25, 0], fov=44, time=11.5, style="Linear")

    # ------------------------------------------------------------------ P3 light point drops
    inst.append(mesh("Point", "lumpy_sphere", [0, base_y, 0, 0, 0, 0], [R * 0.06] * 3, 1, "Neon", hexc("#fff6d8")))
    at(2.95, do="set", target="Point", prop="Transparency", value=0)
    at(3.0, do="tween", target="Point", prop="CFrame", to=[0, R * 0.05, 0, 0, 0, 0], time=0.25, style="Quad", dir="In")
    at(3.3, do="set", target="Point", prop="Transparency", value=1)
    inst.append({"class": "Part", "name": "Ignite", "CFrame": [0, R * 0.1, 0, 0, 0, 0], "Size": [1, 1, 1], "Transparency": 1, "children": [
        {"class": "Attachment", "name": "A", "children": [
            {"class": "ParticleEmitter", "name": "Star", "props": {"Texture": "sim:impact_star4_2x2", "FlipbookLayout": E("ParticleFlipbookLayout.Grid2x2"),
                "FlipbookStartRandom": True, "FlipbookFramerate": NR(0), "Rate": 0, "Lifetime": NR(0.22), "Speed": NR(0),
                "Size": NS((0, R * 0.1), (0.3, R * 1.4), (1, R * 0.6)), "Transparency": NS((0, 0), (0.7, 0), (1, 1)),
                "Color": CS((0, (1, 1, 1)), (1, hexc("#f2ea1e"))), "LightEmission": 1, "Brightness": 3, "ZOffset": 5}},
            {"class": "ParticleEmitter", "name": "Ring", "props": {"Texture": "sim:ring_energy", "Rate": 0, "Lifetime": NR(0.26), "Speed": NR(0),
                "Size": NS((0, R * 0.2), (1, R * 3.2)), "Transparency": NS((0, 0), (1, 1)),
                "Color": CS((0, hexc("#f2ea1e")), (1, hexc("#f2ea1e"))), "LightEmission": 1, "Brightness": 2, "ZOffset": 4}}]}]})
    at(3.25, do="emit", target="Ignite.A.Star", count=1)
    at(3.27, do="emit", target="Ignite.A.Ring", count=1)

    # ------------------------------------------------------------------ grading
    inst.append({"class": "ColorCorrectionEffect", "name": "Grade", "props": {"Brightness": 0, "Contrast": 0, "Saturation": 0, "TintColor": C3(1, 1, 1)}})
    inst.append({"class": "BloomEffect", "name": "Bloom", "props": {"Intensity": 1.2, "Size": 36, "Threshold": 1.7}})
    at(3.5, do="set", target="Grade", prop="Brightness", value=1.0)                         # P4: one white frame
    at(3.52, do="set", target="Grade", prop="Brightness", value=0.0)
    at(4.3, do="tween", target="Grade", prop="Brightness", to=0.95, time=0.08, style="Linear")  # P7 whiteout
    at(4.3, do="set", target="Grade", prop="TintColor", value=C3(1, 0.99, 0.94))
    at(4.65, do="tween", target="Grade", prop="Brightness", to=0.12, time=1.6, style="Quad", dir="Out")
    at(4.65, do="tween", target="Grade", prop="TintColor", to=C3(*hexc("#fdf1cf")), time=0.9, style="Linear")
    at(5.55, do="tween", target="Grade", prop="TintColor", to=C3(*hexc("#f8de90")), time=1.0, style="Linear")
    at(6.6, do="tween", target="Grade", prop="TintColor", to=C3(*hexc("#f0c08a")), time=2.5, style="Linear")
    at(6.3, do="tween", target="Grade", prop="Brightness", to=0.0, time=3.0, style="Sine", dir="InOut")
    at(9.5, do="tween", target="Grade", prop="TintColor", to=C3(*hexc("#e3c3d2")), time=4.5, style="Sine", dir="InOut")

    # ------------------------------------------------------------------ P5 fireball
    D = 2 * R
    fire_children = lambda tex, col, emis, et: [sa(tex, col, emis, et)]
    inst.append(mesh("Core", "lumpy_sphere", [0, 0, 0, 0, 0, 0], [1, 1, 1], 1, "Neon", hexc("#fffbe6")))
    inst.append(mesh("ShellIn", "lumpy_sphere", [0, 0, 0, 0, 40, 0], [1, 1, 1], 1,
                     children=fire_children("mesh_fire_shell", hexc("#fff59a"), 3.0, hexc("#fff6c0"))))
    inst.append(mesh("ShellOut", "lumpy_sphere", [0, 0, 0, 0, 160, 0], [1, 1, 1], 1,
                     children=fire_children("mesh_fire_shell", hexc("#f59a2a"), 1.6, hexc("#ffb050"))))
    for nm, scale, tr in (("Core", 0.86, 0.0), ("ShellIn", 0.97, 0.02), ("ShellOut", 1.07, 0.45)):
        at(3.52, do="set", target=nm, prop="Transparency", value=tr)
        at(3.52, do="tween", target=nm, prop="Size", from_=[D * 0.27 * scale] * 3, to=[D * 0.7 * scale] * 3, time=0.2, style="Quart", dir="Out")
        at(3.72, do="tween", target=nm, prop="Size", to=[D * scale] * 3, time=0.6, style="Quad", dir="In")
        # P6 squash to a dome about 2:1 wide
        at(4.32, do="tween", target=nm, prop="Size", to=[D * scale * 1.22, D * scale * 0.62, D * scale * 1.22], time=0.7, style="Quad", dir="Out")
        at(4.0, do="tween", target=nm, prop="CFrame", by=[0, 0, 0, 0, 25 if nm != "ShellOut" else -18, 0], time=6.0, style="Linear")
    # colour: yellow core -> white by +0.75 -> cooling to cream, yellow, orange
    at(3.77, do="tween", target="ShellIn.Look", prop="Color", to=C3(1, 1, 0.94), time=0.5, style="Linear")
    at(4.9, do="tween", target="ShellIn.Look", prop="Color", to=C3(*hexc("#f8de90")), time=0.8, style="Linear")
    at(5.8, do="tween", target="ShellIn.Look", prop="Color", to=C3(*hexc("#fad54c")), time=1.2, style="Linear")
    at(7.0, do="tween", target="ShellIn.Look", prop="Color", to=C3(*hexc("#e4842a")), time=2.0, style="Linear")
    at(7.0, do="tween", target="ShellOut.Look", prop="Color", to=C3(*hexc("#a5513b")), time=2.5, style="Linear")
    at(6.0, do="tween", target="ShellIn.Look", prop="EmissiveStrength", to=0.6, time=4.0, style="Sine", dir="InOut")
    at(6.0, do="tween", target="ShellOut.Look", prop="EmissiveStrength", to=0.25, time=4.0, style="Sine", dir="InOut")
    at(4.8, do="tween", target="Core", prop="Transparency", to=1, time=1.6, style="Sine", dir="In")
    for nm in ("ShellIn", "ShellOut"):
        at(9.0, do="tween", target=nm, prop="Transparency", to=1, time=2.5, style="Sine", dir="In")

    # boiling cartoon puffs around the ball (fire flipbook, snapped frames)
    inst.append({"class": "Part", "name": "PuffZone", "Shape": "Ball", "CFrame": [0, R * 0.25, 0, 0, 0, 0], "Size": [D * 0.95, D * 0.6, D * 0.95], "Transparency": 1, "children": [
        {"class": "ParticleEmitter", "name": "Puffs", "props": {
            "Texture": "sim:fire_hot_4x4", "FlipbookLayout": E("ParticleFlipbookLayout.Grid4x4"), "FlipbookMode": E("ParticleFlipbookMode.OneShot"),
            "FlipbookBlendFrames": False, "Shape": E("ParticleEmitterShape.Sphere"), "ShapeStyle": E("ParticleEmitterShapeStyle.Surface"),
            "Rate": 0, "Lifetime": NR(0.7, 1.15), "Speed": NR(R * 0.08, R * 0.2), "Acceleration": V3(0, R * 0.15, 0),
            "Size": NS((0, R * 0.45, R * 0.1), (1, R * 0.72, R * 0.12)), "Rotation": NR(0, 360), "RotSpeed": NR(-30, 30),
            "Color": CS((0, (1, 1, 1)), (1, (1, 1, 1))), "LightEmission": 0.15, "Brightness": 1.4, "ZOffset": 2}}]})
    at(3.6, do="set", target="PuffZone.Puffs", prop="Rate", value=170)
    at(3.6, do="enable", target="PuffZone.Puffs", duration=1.1)
    at(4.7, do="set", target="PuffZone.Puffs", prop="Rate", value=55)
    at(4.71, do="enable", target="PuffZone.Puffs", duration=4.3)

    # debris thrown inside the ring band
    inst.append({"class": "Part", "name": "Debris", "Shape": "Ball", "CFrame": [0, R * 0.1, 0, 0, 0, 0], "Size": [R * 0.3] * 3, "Transparency": 1, "children": [
        {"class": "ParticleEmitter", "name": "Rocks", "props": {
            "Texture": "sim:debris_rock_8x8", "FlipbookLayout": E("ParticleFlipbookLayout.Grid8x8"), "FlipbookMode": E("ParticleFlipbookMode.Loop"),
            "FlipbookFramerate": NR(18, 30), "FlipbookStartRandom": True, "Shape": E("ParticleEmitterShape.Sphere"),
            "ShapePartial": 0.5, "Rate": 0, "Lifetime": NR(1.4, 2.4), "Speed": NR(R * 0.9, R * 1.7), "Acceleration": V3(0, -R * 0.9, 0), "Drag": 0.4,
            "Size": NS((0, R * 0.05, R * 0.03), (1, R * 0.05, R * 0.03)), "Color": CS((0, hexc("#3a1a14")), (1, hexc("#2b0d0d"))),
            "LightEmission": 0, "LightInfluence": 0.3, "ZOffset": 3}}]})
    at(3.6, do="emit", target="Debris.Rocks", count=30)          # distant gravel only; the big chunks are real meshes
    import sys
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    from fxprops import crater, debris

    def at_(t, **e):
        if "from_" in e:
            e["from"] = e.pop("from_")
        at(t, **e)
    inst.append(crater(at_, "Rim", [0, 0, 0], R * 0.75, 3.6, tint=(0.42, 0.3, 0.27)))
    inst.extend(debris(at_, "Chunk", [0, R * 0.08, 0], 26, 3.6, scale=(R * 0.025, R * 0.06), speed=(R * 0.35, R * 0.8), up=(R * 0.5, R * 0.95),
                       tint=(0.4, 0.28, 0.25), seed=71, jitter=0.15))

    # ------------------------------------------------------------------ P6 shock rings
    ring_sa = [sa("mesh_shock_ring", hexc("#f3e5d4"), 2.5, (1, 1, 1))]
    inst.append(mesh("Shock1", "ring", [0, R * 0.04, 0, 0, 0, 0], [1, 0.1, 1], 1, children=ring_sa))
    inst.append(mesh("Shock2", "ring", [0, R * 0.55, 0, 0, 30, 0], [1, 0.1, 1], 1, children=[sa("mesh_shock_ring", hexc("#f3e5d4"), 2.0, (1, 1, 1))]))
    for nm, t0, reach in (("Shock1", 4.3, 5.6), ("Shock2", 4.37, 4.0)):
        at(t0, do="set", target=nm, prop="Transparency", value=0.05)
        at(t0, do="tween", target=nm, prop="Size", from_=[D * 0.9, 0.1, D * 0.9], to=[D * reach, 0.1, D * reach], time=0.6, style="Quart", dir="Out")
        at(t0 + 0.12, do="tween", target=nm, prop="Transparency", to=1, time=0.5, style="Quad", dir="In")
    at(4.75, do="shake", amp=R * 0.004, time=0.5, freq=24)   # the shock front reaches the viewer

    # dust wall racing out under the ring
    inst.append({"class": "Part", "name": "DustRing", "Shape": "Cylinder", "CFrame": [0, R * 0.06, 0, 0, 0, 0], "Size": [D * 0.55, R * 0.05, D * 0.55], "Transparency": 1, "children": [
        {"class": "ParticleEmitter", "name": "Dust", "props": {
            "Texture": "sim:smoke_dust_4x4", "FlipbookLayout": E("ParticleFlipbookLayout.Grid4x4"), "FlipbookMode": E("ParticleFlipbookMode.OneShot"),
            "FlipbookBlendFrames": False, "Shape": E("ParticleEmitterShape.Cylinder"), "ShapeStyle": E("ParticleEmitterShapeStyle.Surface"),
            "Rate": 0, "Lifetime": NR(1.6, 2.8), "Speed": NR(R * 0.8, R * 1.4), "Drag": 1.1, "Acceleration": V3(0, R * 0.05, 0),
            "Size": NS((0, R * 0.22, R * 0.06), (1, R * 0.62, R * 0.12)), "Rotation": NR(0, 360),
            "Color": CS((0, hexc("#d9c3a2")), (1, hexc("#a68f78"))), "LightEmission": 0, "LightInfluence": 0.45, "ZOffset": 1}}]})
    at(4.3, do="set", target="DustRing.Dust", prop="Rate", value=260)
    at(4.3, do="enable", target="DustRing.Dust", duration=0.7)

    # ------------------------------------------------------------------ P9 burn
    inst.append(mesh("Skirt", "cone", [0, R * 0.38, 0, 0, 0, 0], [D * 1.25, R * 0.62, D * 1.25], 1,
                     children=[sa("mesh_spike_skirt", (1, 0.97, 0.9), 2.0, hexc("#ffd9b0"))]))
    at(4.55, do="set", target="Skirt", prop="Transparency", value=0.1)
    at(4.55, do="tween", target="Skirt", prop="Size", from_=[D * 0.9, R * 0.3, D * 0.9], to=[D * 1.3, R * 0.66, D * 1.3], time=0.5, style="Quart", dir="Out")
    at(5.4, do="tween", target="Skirt.Look", prop="Color", to=C3(*hexc("#e08c57")), time=2.0, style="Linear")
    at(6.8, do="tween", target="Skirt", prop="Transparency", to=1, time=2.0, style="Sine", dir="In")
    inst.append(mesh("GroundGlow", "plane", [0, 0.6, 0, 0, 0, 0], [D * 2.6, 0.1, D * 2.6], 1,
                     children=[sa("glow_falloff", hexc("#e08c57"), 1.2, hexc("#ffb070"))]))
    at(3.55, do="set", target="GroundGlow", prop="Transparency", value=0.1)
    at(8.0, do="tween", target="GroundGlow", prop="Transparency", to=1, time=4.0, style="Sine", dir="In")
    inst.append(mesh("Scorch", "plane", [0, 0.3, 0, 0, 0, 0], [D * 1.9, 0.1, D * 1.9], 1, children=[sa("mesh_scorch", (1, 1, 1), 0.0)]))
    at(5.0, do="tween", target="Scorch", prop="Transparency", to=0.05, time=2.0, style="Linear")
    inst.append({"class": "Part", "name": "Lamp", "CFrame": [0, R * 0.4, 0, 0, 0, 0], "Size": [1, 1, 1], "Transparency": 1, "children": [
        {"class": "PointLight", "name": "L", "props": {"Brightness": 0, "Range": 60, "Color": C3(*hexc("#ffb36b"))}}]})
    at(3.52, do="set", target="Lamp.L", prop="Brightness", value=5)
    # Roblox lights nearby surfaces with this (the sim does not): left on, it paints a bright band under
    # the cap at 10 s (Studio round 2). Fade it out while the fireball is still the brightest thing.
    at(4.4, do="tween", target="Lamp.L", prop="Brightness", to=0, time=2.6, style="Sine", dir="Out")

    # ------------------------------------------------------------------ P10 mushroom
    # emissive set for Roblox at night (Studio round 2: lit-only smoke goes dark brown at ClockTime 0)
    smoke_col0 = hexc("#dd8639")
    inst.append(mesh("Stem", "stem", [0, R * 0.05, 0, 0, 0, 0], [R * 0.5, 0.2, R * 0.5], 1,
                     children=[sa("mesh_smoke_shell", smoke_col0, 1.4, hexc("#f6d59f"))]))
    at(5.5, do="set", target="Stem", prop="Transparency", value=0.05)
    at(5.5, do="tween", target="Stem", prop="Size", to=[R * 0.95, R * 2.5, R * 0.95], time=8.0, style="Sine", dir="Out")
    at(5.5, do="tween", target="Stem", prop="CFrame", to=[0, R * 1.25, 0, 0, 40, 0], time=8.0, style="Sine", dir="Out")
    inst.append(mesh("Cap", "lumpy_sphere", [0, R * 0.8, 0, 0, 0, 0], [D * 0.9, R * 1.0, D * 0.9], 1,
                     children=[sa("mesh_smoke_shell", smoke_col0, 2.6, hexc("#f6d59f")),
                               {"class": "ParticleEmitter", "name": "Billow", "props": {
                                   "Texture": "sim:smoke_cel_4x4", "FlipbookLayout": E("ParticleFlipbookLayout.Grid4x4"), "FlipbookMode": E("ParticleFlipbookMode.OneShot"),
                                   "FlipbookBlendFrames": False, "Shape": E("ParticleEmitterShape.Sphere"), "ShapeStyle": E("ParticleEmitterShapeStyle.Surface"),
                                   "Rate": 0, "Lifetime": NR(2.0, 3.2), "Speed": NR(R * 0.05, R * 0.15), "Acceleration": V3(0, R * 0.04, 0),
                                   "Size": NS((0, R * 0.6, R * 0.15), (1, R * 1.0, R * 0.2)), "Rotation": NR(0, 360),
                                   "Color": CS((0, hexc("#c87a3c")), (1, hexc("#8a7a74"))), "LightEmission": 0, "LightInfluence": 0.35, "ZOffset": 1}}]))
    at(5.3, do="set", target="Cap", prop="Transparency", value=0.05)
    at(5.3, do="tween", target="Cap", prop="CFrame", to=[0, R * 2.9, 0, 0, 30, 0], time=9.0, style="Linear")
    at(5.3, do="tween", target="Cap", prop="Size", to=[D * 1.55, R * 1.65, D * 1.55], time=9.0, style="Sine", dir="Out")
    at(5.5, do="set", target="Cap.Billow", prop="Rate", value=38)
    import math as _m
    for k in range(7):
        a = 2 * _m.pi * k / 7 + 0.4
        rr = 0.62 if k % 2 == 0 else 0.5
        y0, y1 = R * 0.8, R * 2.9
        nm = f"Lobe{k}"
        p0 = [_m.cos(a) * D * 0.9 * rr * 0.6, y0 + R * (0.05 if k % 2 else -0.1), _m.sin(a) * D * 0.9 * rr * 0.6]
        p1 = [_m.cos(a) * D * 1.55 * rr * 0.62, y1 + R * (0.12 if k % 2 else -0.15), _m.sin(a) * D * 1.55 * rr * 0.62]
        sz0 = D * (0.42 if k % 2 else 0.5)
        inst.append(mesh(nm, "lumpy_sphere", [*p0, 0, k * 47, 0], [sz0, sz0 * 0.75, sz0], 1,
                         children=[sa("mesh_smoke_shell", smoke_col0, 2.4, hexc("#f6d59f"))]))
        at(5.3, do="set", target=nm, prop="Transparency", value=0.05)
        at(5.3, do="tween", target=nm, prop="CFrame", to=[*p1, 0, k * 47 + 40, 0], time=9.0, style="Linear")
        at(5.3, do="tween", target=nm, prop="Size", to=[sz0 * 1.6, sz0 * 1.15, sz0 * 1.6], time=9.0, style="Sine", dir="Out")
        at(7.0, do="tween", target=f"{nm}.Look", prop="Color", to=C3(*hexc("#b05f25")), time=3.5, style="Linear")
        at(10.5, do="tween", target=f"{nm}.Look", prop="Color", to=C3(*hexc("#867671")), time=3.5, style="Linear")
        at(6.0, do="tween", target=f"{nm}.Look", prop="EmissiveStrength", to=0.5, time=7.0, style="Sine", dir="InOut")
    at(5.5, do="enable", target="Cap.Billow", duration=8.5)
    for nm in ("Stem.Look", "Cap.Look"):
        at(7.0, do="tween", target=nm, prop="Color", to=C3(*hexc("#b05f25")), time=3.5, style="Linear")
        at(10.5, do="tween", target=nm, prop="Color", to=C3(*hexc("#867671")), time=3.5, style="Linear")
        at(6.0, do="tween", target=nm, prop="EmissiveStrength", to=0.5, time=7.0, style="Sine", dir="InOut")
    inst.append(mesh("Vortex", "torus", [0, R * 0.55, 0, 0, 0, 0], [D * 0.9, R * 0.5, D * 0.9], 1,
                     children=[sa("mesh_smoke_shell", hexc("#c97534"), 0.9, hexc("#f6d59f"))]))
    at(5.4, do="set", target="Vortex", prop="Transparency", value=0.1)
    at(5.4, do="tween", target="Vortex", prop="CFrame", to=[0, R * 2.45, 0, 0, 180, 0], time=9.0, style="Linear")
    at(5.4, do="tween", target="Vortex", prop="Size", to=[D * 1.7, R * 0.75, D * 1.7], time=9.0, style="Sine", dir="Out")
    at(7.0, do="tween", target="Vortex.Look", prop="Color", to=C3(*hexc("#8f6b5a")), time=6.0, style="Linear")
    for k, (hy, tk) in enumerate(((1.05, 8.3), (1.6, 8.7))):
        nm = f"Condense{k}"
        # vapour, not light: Neon here glowed as a bright band edge-on in Roblox (Studio round 3)
        inst.append(mesh(nm, "torus", [0, R * hy, 0, 0, 0, 0], [D * 0.75, R * 0.07, D * 0.75], 1, "SmoothPlastic", hexc("#e9d2b8")))
        at(tk, do="set", target=nm, prop="Transparency", value=0.55)
        at(tk, do="tween", target=nm, prop="Size", to=[D * 1.15, R * 0.09, D * 1.15], time=3.5, style="Quad", dir="Out")
        at(tk + 0.8, do="tween", target=nm, prop="Transparency", to=1, time=2.8, style="Sine", dir="In")

    # ------------------------------------------------------------------ P11 embers
    inst.append({"class": "Part", "name": "EmberSky", "CFrame": [0, R * 3.4, 0, 0, 0, 0], "Size": [D * 3.0, 2, D * 2.0], "Transparency": 1, "children": [
        {"class": "ParticleEmitter", "name": "Embers", "props": {
            "Texture": "sim:spark_ember_8x8", "FlipbookLayout": E("ParticleFlipbookLayout.Grid8x8"), "FlipbookMode": E("ParticleFlipbookMode.Loop"),
            "FlipbookFramerate": NR(12, 24), "FlipbookStartRandom": True, "EmissionDirection": E("NormalId.Bottom"),
            "Rate": 0, "Lifetime": NR(4, 6.5), "Speed": NR(R * 0.08, R * 0.2), "Acceleration": V3(0, -R * 0.05, 0), "Drag": 0.3,
            "SpreadAngle": {"Vector2": [25, 25]}, "Size": NS((0, R * 0.032, R * 0.012), (1, R * 0.02)),
            "Color": CS((0, hexc("#f8d698")), (1, hexc("#d57344"))), "LightEmission": 1, "Brightness": 2.4,
            "Transparency": NS((0, 1), (0.1, 0), (0.85, 0), (1, 1))}}]})
    at(7.5, do="set", target="EmberSky.Embers", prop="Rate", value=320)
    at(7.5, do="enable", target="EmberSky.Embers", duration=7.0)

    return {
        "name": "CrimsonDetonation",
        "note": f"Original sky-circle detonation (R = {R:.0f} studs) on the measured KonoSuba skeleton: stacked circles, calm wide cut, point -> star -> ring, 1-frame flash, measured growth curve, squash + shock rings, held whiteout, cooling grade, burn, mushroom, embers. All textures and meshes are ours.",
        "duration": 14.5,
        "seed": 11,
        "camera": {"pos": [R * 0.35, R * 0.35, R * 2.2], "at": [0, R * 1.75, 0], "fov": 62},
        "stage": {"ground": "grass", "sky": "night", "dummy": False, "fog": [R * 4, R * 14, [0.08, 0.1, 0.16]]},
        "instances": inst,
        "timeline": [fix(e) for e in tl],
    }


def fix(e):
    if "from_" in e:
        v = e.pop("from_")
        if v is not None:
            e["from"] = v
    return e


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--R", type=float, default=90.0)
    ap.add_argument("--out", default="explosion_crimson.json")
    a = ap.parse_args()
    d = build(a.R)
    p = Path(__file__).resolve().parent / a.out
    from roblox_units import to_roblox_units
    p.write_text(json.dumps(to_roblox_units(d), indent=1))
    print("wrote", p, len(d["instances"]), "top-level instances,", len(d["timeline"]), "timeline events")
