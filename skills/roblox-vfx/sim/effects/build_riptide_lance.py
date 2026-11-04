"""Riptide Lance: an original beam, designed with NO reference (references/DESIGN.md).

BRIEF
  Name:           Riptide Lance
  Fantasy:        the caster compresses the sea into one spear of light and drives it through the target
  Tier:           big skill (2-4 s)
  Style family:   anime_cel
  Category:       beam (corpus: flash 2 frames, ~9 layers, white core 78 %, dark beat before release 6/10,
                  two-stage onset, aftermath in a different colour 5/10, residue:main 0.4-1.0)
  Shape word:     spiral needle
  Dominant:       #26e0c8 teal     Accent: #ff6a4d coral (complementary)     Darks: #062a33
  Colour arc:     teal charge, three rings lighting in sequence -> lights dim (dark beat) -> 2-frame white
                  -> teal beam, white core, coral rim, rings riding it -> impact swaps THROUGH white to coral
                  -> steam (pale teal-grey) + coral embers + scorched trench
  Signature beats: rings light in sequence then collapse into the hand (suck-in + dark beat); two-stage
                  onset (pops to 35 %, holds, SURGES); escalating impact (second, bigger burst on the surge)
                  with a 2-frame black-and-white impact frame; colour swap at the target
  Timeline:       anticipation 0.00-1.10 | quiet_beat 1.10-1.20 | release 1.20-1.233 | sustain 1.233-2.40
                  | dissipation 2.40-2.55 | residue 2.55-4.40
  Staging:        side gameplay camera, shake on the surge, world desaturated + teal during charge
  Residue:        steam, embers, trench (~1.85 s vs 1.35 s main: residue:main ~1.4, beam p75 1.0, justified by the
                  long trench)
"""
import json
from pathlib import Path

TEAL, CORAL, DARK, WHITE = (0.15, 0.88, 0.78), (1.0, 0.42, 0.30), (0.02, 0.16, 0.2), (1, 1, 1)


def NR(a, b=None): return {"NumberRange": [a, a if b is None else b]}
def NS(*k): return {"NumberSequence": [list(p) for p in k]}
def CS(*k): return {"ColorSequence": [[t, list(c)] for t, c in k]}
def E(e): return {"Enum": e}
def C3(c): return {"Color3": list(c)}


FB = {"FlipbookLayout": E("ParticleFlipbookLayout.Grid4x4"), "FlipbookMode": E("ParticleFlipbookMode.OneShot"), "FlipbookBlendFrames": False}


def pe(name, **p):
    return {"class": "ParticleEmitter", "name": name, "props": dict({"Rate": 0}, **p)}


def sa(tex, col, emis, et):
    return {"class": "SurfaceAppearance", "name": "Look", "props": {"ColorMap": f"sim:{tex}", "EmissiveMask": f"sim:{tex}",
            "AlphaMode": E("AlphaMode.Transparency"), "Color": C3(col), "EmissiveStrength": emis, "EmissiveTint": C3(et)}}


def build():
    HAND = [1.6, 3.2, -1.6]
    TZ = -34.0
    TARGET = [0.0, 3.0, TZ]
    REL = 1.2
    inst, tl = [], []
    at = lambda t, **e: tl.append(dict(e, t=round(t, 4)))

    # --- charge: orb, inward strands, three rings that light in sequence
    inst.append({"class": "Part", "name": "Muzzle", "Shape": "Ball", "CFrame": HAND + [0, 0, 0], "Size": [2.4, 2.4, 2.4], "Transparency": 1, "children": [
        {"class": "Attachment", "name": "A", "children": [
            pe("Orb", Texture="sim:glow_soft", Lifetime=NR(1.15), Speed=NR(0), Size=NS((0, 0.4), (0.8, 2.6), (0.92, 3.0), (1, 0.3)),
               Transparency=NS((0, 0.3), (0.9, 0), (1, 1)), Color=CS((0, TEAL), (0.8, (0.7, 1, 0.95)), (1, WHITE)), LightEmission=1, Brightness=2.4),
            pe("Rings", Texture="sim:ring_energy", Orientation=E("ParticleOrientation.VelocityPerpendicular"), EmissionDirection=E("NormalId.Front"),
               Lifetime=NR(0.32), Speed=NR(150), Size=NS((0, 2.2), (1, 3.4)), RotSpeed=NR(240), Transparency=NS((0, 0.15), (0.7, 0.3), (1, 1)),
               Color=CS((0, (0.75, 1, 0.95)), (1, TEAL)), LightEmission=1, Brightness=1.8)]},
        pe("Strands", Texture="sim:spark_needle", Shape=E("ParticleEmitterShape.Sphere"), ShapeStyle=E("ParticleEmitterShapeStyle.Surface"),
           ShapeInOut=E("ParticleEmitterShapeInOut.Inward"), Orientation=E("ParticleOrientation.VelocityParallel"), Lifetime=NR(0.15, 0.25),
           Speed=NR(10, 18), Size=NS((0, 0.7, 0.2), (1, 0.25)), Color=CS((0, (0.75, 1, 0.95)), (1, TEAL)), LightEmission=1, Brightness=2)]})
    for i, (t0, d) in enumerate(((0.3, 3.4), (0.55, 5.0), (0.8, 6.8))):
        nm = f"CRing{i}"
        z = HAND[2] - 0.8 - i * 0.9
        inst.append({"class": "MeshPart", "name": nm, "MeshId": "sim:ring", "Material": "SmoothPlastic", "Transparency": 1,
                     "CFrame": [HAND[0], HAND[1], z, 90, 0, 0], "Size": [0.3, 0.05, 0.3], "props": {"DoubleSided": True},
                     "children": [sa("mesh_shock_ring", TEAL, 2.6, (0.7, 1, 0.95))]})
        at(t0, do="set", target=nm, prop="Transparency", value=0.02)
        at(t0, do="tween", target=nm, prop="Size", to=[d, 0.05, d], time=0.3, style="Back", dir="Out")
        at(t0, do="tween", target=nm, prop="CFrame", by=[0, 0, 0, 0, 120 * (1 if i % 2 == 0 else -1), 0], time=1.1, style="Linear")   # spin about its own axis
        # suck-in: all rings collapse into the hand on the quiet beat
        at(1.1, do="tween", target=nm, prop="Size", to=[0.2, 0.05, 0.2], time=0.08, style="Quart", dir="In")
        at(1.18, do="set", target=nm, prop="Transparency", value=1)
    at(0.0, do="emit", target="Muzzle.A.Orb", count=1)
    at(0.0, do="set", target="Muzzle.Strands", prop="Rate", value=90)
    at(0.0, do="enable", target="Muzzle.Strands", duration=1.08)

    # --- the beam: dark shadow, teal body, coral rim, white core (Beams scroll toward the target)
    inst.append({"class": "Part", "name": "From", "CFrame": HAND[:2] + [HAND[2] - 0.6, 0, 0, 0], "Size": [1, 1, 1], "Transparency": 1,
                 "children": [{"class": "Attachment", "name": "A"}]})
    inst.append({"class": "Part", "name": "Tip", "CFrame": HAND[:2] + [HAND[2] - 0.7, 0, 0, 0], "Size": [1, 1, 1], "Transparency": 1,
                 "children": [{"class": "Attachment", "name": "A"}]})
    # body is alpha-blended (LightEmission 0.35) so the teal survives; only the thin core is additive white
    layers = [("Shadow", 9.0, DARK, 0.0, 0.8, -0.03), ("Body", 10.0, (0.08, 0.72, 0.66), 0.35, 0.05, 0.0), ("Rim", 12.0, CORAL, 0.3, 0.45, -0.01), ("Core", 1.2, WHITE, 1.0, 0.0, 0.02)]
    for nm, w, col, le, tr, z in layers:
        inst.append({"class": "Beam", "name": nm, "props": {
            "Attachment0": {"Ref": "From.A"}, "Attachment1": {"Ref": "Tip.A"}, "Enabled": False, "FaceCamera": True, "Segments": 12,
            "Width0": w * 0.6, "Width1": w, "Texture": "sim:beam_paint" if nm == "Rim" else "sim:beam_energy", "TextureMode": E("TextureMode.Wrap"), "TextureLength": 9,
            "TextureSpeed": 3.0 if nm != "Shadow" else 1.5, "LightEmission": le, "Brightness": 1.8 if nm == "Core" else 1.0,
            "Color": CS((0, col), (1, col)), "Transparency": NS((0, tr), (0.92, tr), (1, 1)), "ZOffset": z}})
    # the LANCE itself (RULE ZERO): a spiralling water spear that leads the beam,
    # spins, drives into the target and stays lodged until the beam ends
    import json as _json
    _pm = _json.loads((Path(__file__).resolve().parent.parent / "meshes" / "props.json").read_text())["water_spear"]
    SP = 3.0
    for nm, k, tex, col, emis in (("Spear", 1.0, "water_body", (0.1, 0.75, 0.7), 0.6), ("SpearFoam", 1.06, "water_foam", (0.9, 1, 0.98), 1.0)):
        inst.append({"class": "MeshPart", "name": nm, "MeshId": "sim:water_spear", "Material": "SmoothPlastic", "Transparency": 1,
                     "CFrame": HAND + [0, 0, 0], "Size": [round(v * SP * k, 3) for v in _pm["size"]], "props": {"DoubleSided": True},
                     "children": [sa(tex, col, emis, (0.8, 1, 0.95))]})
    # beam riders: rings flying down the beam during the sustain
    inst.append({"class": "Part", "name": "Rider", "CFrame": HAND + [0, 0, 0], "Size": [1, 1, 1], "Transparency": 1, "children": [
        {"class": "Attachment", "name": "A", "children": [
            pe("Rings", Texture="sim:ring_paint_4x4", **FB, Orientation=E("ParticleOrientation.VelocityPerpendicular"), EmissionDirection=E("NormalId.Front"),
               Lifetime=NR(0.26, 0.36), Speed=NR(130, 170), Size=NS((0, 5.0, 1.0), (1, 7.0, 1.2)), Rotation=NR(0, 360), RotSpeed=NR(-300, 300), Transparency=NS((0, 0.15), (0.8, 0.3), (1, 1)),
               Color=CS((0, (0.45, 1, 0.9)), (1, TEAL)), LightEmission=0.6, Brightness=1.0),
            pe("Streaks", Texture="sim:spark_needle", Orientation=E("ParticleOrientation.VelocityParallel"), EmissionDirection=E("NormalId.Front"),
               SpreadAngle={"Vector2": [4, 4]}, Lifetime=NR(0.25, 0.35), Speed=NR(150, 190), Size=NS((0, 1.6, 0.4), (1, 0.6)),
               Squash=NS((0, 1.5), (1, 1.5)), Color=CS((0, WHITE), (1, (0.6, 1, 0.9))), LightEmission=1, Brightness=2)]}]})

    # --- target impact: cel burst, coral puffs (colour swap), steam, shock ring, cracks, embers
    tgt = [
        pe("Flare", Texture="sim:impact_star4_2x2", FlipbookLayout=E("ParticleFlipbookLayout.Grid2x2"), FlipbookStartRandom=True, FlipbookFramerate=NR(0),
           Lifetime=NR(0.08), Speed=NR(0), Size=NS((0, 9), (1, 13)), Color=CS((0, WHITE), (1, (1, 0.8, 0.7))), LightEmission=1, Brightness=3, ZOffset=3),
        pe("Burst", Texture="sim:impact_burst_4x4", **FB, Lifetime=NR(0.3), Speed=NR(0), Size=NS((0, 9), (1, 11)), Rotation=NR(0, 360),
           Color=CS((0, WHITE), (0.25, (1, 0.75, 0.6)), (1, CORAL)), LightEmission=0.5, Brightness=1.6, ZOffset=2),
        pe("Burst2", Texture="sim:impact_burst_4x4", **FB, Lifetime=NR(0.38), Speed=NR(0), Size=NS((0, 14), (1, 17)), Rotation=NR(0, 360),
           Color=CS((0, WHITE), (0.2, (1, 0.7, 0.55)), (1, CORAL)), LightEmission=0.5, Brightness=1.8, ZOffset=2),
        pe("Puffs", Texture="sim:fire_cel_4x4", **FB, Shape=E("ParticleEmitterShape.Sphere"), Lifetime=NR(0.5, 0.85), Speed=NR(8, 16),
           Size=NS((0, 3.2, 0.8), (1, 4.6, 0.8)), Rotation=NR(0, 360), Color=CS((0, (1, 0.85, 0.75)), (0.3, CORAL), (1, (0.55, 0.2, 0.18))),
           LightEmission=0.15, Brightness=1.3, ZOffset=1),
        pe("Steam", Texture="sim:smoke_wisp_4x4", **FB, Shape=E("ParticleEmitterShape.Sphere"), Lifetime=NR(1.4, 2.0), Speed=NR(3, 7),
           Acceleration={"Vector3": [0, 4, 0]}, Size=NS((0, 4, 1), (1, 9, 1.5)), Rotation=NR(0, 360),
           Color=CS((0, (0.85, 0.95, 0.94)), (1, (0.6, 0.7, 0.72))), LightEmission=0, LightInfluence=0.4, Transparency=NS((0, 0.2), (0.7, 0.35), (1, 1))),
        pe("Embers", Texture="sim:spark_ember_8x8", FlipbookLayout=E("ParticleFlipbookLayout.Grid8x8"), FlipbookMode=E("ParticleFlipbookMode.Loop"),
           FlipbookFramerate=NR(16, 26), FlipbookStartRandom=True, Shape=E("ParticleEmitterShape.Sphere"), Lifetime=NR(1.2, 2.0), Speed=NR(10, 22),
           Acceleration={"Vector3": [0, -10, 0]}, Drag=1.2, Size=NS((0, 0.7, 0.2), (1, 0.3)), Color=CS((0, (1, 0.85, 0.6)), (1, CORAL)),
           LightEmission=1, Brightness=2.2),
    ]
    inst.append({"class": "Part", "name": "Target", "Shape": "Ball", "CFrame": TARGET + [0, 0, 0], "Size": [5, 5, 5], "Transparency": 1,
                 "children": [{"class": "Attachment", "name": "A", "children": tgt[:3]}] + tgt[3:] +
                 [{"class": "PointLight", "name": "L", "props": {"Brightness": 0, "Range": 30, "Color": C3(CORAL)}}]})
    inst.append({"class": "Part", "name": "Floor", "CFrame": [TARGET[0], 0.1, TZ, 0, 0, 0], "Size": [1, 0.1, 1], "Transparency": 1, "children": [
        {"class": "Attachment", "name": "A", "children": [
            pe("Shock", Texture="sim:ring_cel_4x4", **FB, Orientation=E("ParticleOrientation.VelocityPerpendicular"), Speed=NR(0.01), Lifetime=NR(0.45),
               Size=NS((0, 10), (1, 30)), Color=CS((0, (1, 0.85, 0.75)), (1, CORAL)), LightEmission=0.4, ZOffset=0.2)]}]})
    inst.append({"class": "MeshPart", "name": "Trench", "MeshId": "sim:plane", "Material": "SmoothPlastic", "Transparency": 1,
                 "CFrame": [0.8, 0.15, (HAND[2] + TZ) / 2 - 2, 0, 0, 0], "Size": [7, 0.05, abs(TZ - HAND[2]) + 6], "props": {"DoubleSided": True},
                 "children": [sa("mesh_scorch", (1, 1, 1), 0.0, (1, 1, 1))]})
    inst.append({"class": "MeshPart", "name": "Cracks", "MeshId": "sim:plane", "Material": "SmoothPlastic", "Transparency": 1,
                 "CFrame": [TARGET[0], 0.2, TZ, 0, 0, 0], "Size": [22, 0.05, 22], "props": {"DoubleSided": True},
                 "children": [sa("crack_glow", CORAL, 2.4, (1, 0.6, 0.45))]})
    inst.append({"class": "ColorCorrectionEffect", "name": "Grade", "props": {"Brightness": 0, "Contrast": 0, "Saturation": 0, "TintColor": C3(WHITE)}})
    inst.append({"class": "Part", "name": "HandLamp", "CFrame": HAND + [0, 0, 0], "Size": [1, 1, 1], "Transparency": 1,
                 "children": [{"class": "PointLight", "name": "L", "props": {"Brightness": 0, "Range": 18, "Color": C3(TEAL)}}]})

    # ---------------- timeline
    at(0.0, do="tween", target="Grade", prop="Saturation", to=-0.35, time=0.9, style="Sine", dir="InOut")
    at(0.0, do="tween", target="Grade", prop="TintColor", to=C3((0.88, 1.0, 0.98)), time=0.9, style="Sine", dir="InOut")
    at(0.1, do="tween", target="HandLamp.L", prop="Brightness", to=3, time=1.0, style="Quad", dir="In")
    # quiet / dark beat: lights die, the world dims
    at(1.1, do="set", target="HandLamp.L", prop="Brightness", value=0)
    at(1.1, do="tween", target="Grade", prop="Brightness", to=-0.45, time=0.06, style="Quad", dir="In")
    # release: 2-frame white, then beam stage 1 (35 %) with the tip racing to the target
    at(REL, do="set", target="Grade", prop="Brightness", value=0.9)
    at(REL + 2 / 60, do="set", target="Grade", prop="Brightness", value=0.05)
    at(REL + 2 / 60, do="tween", target="Grade", prop="Brightness", to=0, time=0.3, style="Quad", dir="Out")
    for nm, w, *_ in layers:
        at(REL, do="set", target=nm, prop="Enabled", value=True)
        at(REL, do="tween", target=nm, prop="Width1", **{"from": w * 0.12}, to=w * 0.35, time=0.05, style="Quart", dir="Out")
        at(REL, do="tween", target=nm, prop="Width0", **{"from": w * 0.08}, to=w * 0.25, time=0.05, style="Quart", dir="Out")
    at(REL, do="tween", target="Tip", prop="CFrame", to=[TARGET[0], TARGET[1], TZ + 1.5, 0, 0, 0], time=0.12, style="Quad", dir="In")
    _half = _pm["size"][1] * SP / 2
    for nm in ("Spear", "SpearFoam"):
        at(REL, do="set", target=nm, prop="Transparency", value=0.05 if nm == "Spear" else 0.15)
        at(REL, do="path", target=nm, points=[[HAND[0], HAND[1], HAND[2] - 0.6], [TARGET[0], TARGET[1], TZ + _half - 2.2]], time=0.12, style="Quad", dir="In",
           offset=[0, 0, 0, 90, 0, 0], spin=1080)
        at(2.4, do="tween", target=nm, prop="Transparency", to=1, time=0.15, style="Quad", dir="In")
    at(REL, do="set", target="HandLamp.L", prop="Brightness", value=5)
    # first impact
    at(REL + 0.12, do="emit", target="Target.A.Flare", count=1)
    at(REL + 0.12, do="emit", target="Target.A.Burst", count=1)
    at(REL + 0.12, do="set", target="Target.L", prop="Brightness", value=4)
    at(REL + 0.12, do="set", target="Trench", prop="Transparency", value=0.1)
    # SURGE (two-stage onset): Quad In to full width, escalated second impact + B&W impact frame
    S = REL + 0.45
    for nm, w, *_ in layers:
        at(S, do="tween", target=nm, prop="Width1", to=w, time=0.1, style="Quad", dir="In")
        at(S, do="tween", target=nm, prop="Width0", to=w * 0.6, time=0.1, style="Quad", dir="In")
    at(S + 0.1, do="set", target="Grade", prop="Saturation", value=-1.0)          # 2-frame black-and-white impact frame
    at(S + 0.1, do="set", target="Grade", prop="Contrast", value=0.9)
    at(S + 0.1 + 2 / 60, do="set", target="Grade", prop="Contrast", value=0)
    at(S + 0.1 + 2 / 60, do="tween", target="Grade", prop="Saturation", to=0, time=0.5, style="Quad", dir="Out")
    at(S + 0.1 + 2 / 60, do="set", target="Grade", prop="TintColor", value=C3((1, 0.93, 0.9)))   # colour swap toward coral at the target
    at(S + 0.1, do="emit", target="Target.A.Burst2", count=1)
    at(S + 0.1, do="emit", target="Floor.A.Shock", count=1)
    at(S + 0.1, do="emit", target="Target.Puffs", count=14)
    at(S + 0.1, do="set", target="Cracks", prop="Transparency", value=0.05)
    at(S + 0.1, do="shake", amp=0.35, time=0.45, freq=26)
    at(S + 0.1, do="set", target="Target.L", prop="Brightness", value=7)
    at(S + 0.12, do="tween", target="Target.L", prop="Brightness", to=1, time=1.2, style="Quad", dir="Out")
    at(S, do="set", target="Rider.A.Rings", prop="Rate", value=26)
    at(S, do="enable", target="Rider.A.Rings", duration=0.75)
    at(S, do="set", target="Rider.A.Streaks", prop="Rate", value=60)
    at(S, do="enable", target="Rider.A.Streaks", duration=0.75)
    # sustain flicker on 2s: the core breathes every 2 frames
    t = S + 0.12
    k = 0
    while t < 2.38:
        at(t, do="set", target="Core", prop="Width1", value=1.2 * (1.0 if k % 2 == 0 else 1.45))
        t += 2 / 60
        k += 1
    # end of beam: everything narrows to nothing, tip-first fade
    for nm, w, *_ in layers:
        at(2.4, do="tween", target=nm, prop="Width1", to=0, time=0.15, style="Quad", dir="In")
        at(2.4, do="tween", target=nm, prop="Width0", to=0, time=0.15, style="Quad", dir="In")
        at(2.56, do="set", target=nm, prop="Enabled", value=False)
    at(2.4, do="set", target="HandLamp.L", prop="Brightness", value=0)
    at(2.4, do="tween", target="Grade", prop="TintColor", to=C3(WHITE), time=1.2, style="Sine", dir="InOut")
    # residue: steam, embers, trench + cracks fade
    at(S + 0.15, do="set", target="Target.Steam", prop="Rate", value=18)
    at(S + 0.15, do="enable", target="Target.Steam", duration=1.6)
    at(S + 0.15, do="set", target="Target.Embers", prop="Rate", value=40)
    at(S + 0.15, do="enable", target="Target.Embers", duration=1.4)
    at(2.6, do="tween", target="Cracks", prop="Transparency", to=1, time=1.6, style="Sine", dir="In")
    at(2.8, do="tween", target="Trench", prop="Transparency", to=1, time=1.6, style="Sine", dir="In")

    brief = {"name": "Riptide Lance", "category": "beam", "tier": "big skill", "style": "anime_cel", "shape": "spiral needle",
             "dominant": "#26e0c8", "accent": "#ff6a4d", "darks": "#062a33",
             "signature_beats": ["rings light in sequence then collapse (suck-in + dark beat)", "two-stage onset surge",
                                 "escalating impact with a B&W impact frame", "colour swap to coral at the target"],
             "phases": [{"name": "anticipation", "t0": 0.0, "t1": 1.1}, {"name": "quiet_beat", "t0": 1.1, "t1": REL},
                        {"name": "release", "t0": REL, "t1": REL + 2 / 60}, {"name": "sustain", "t0": REL + 2 / 60, "t1": 2.4},
                        {"name": "dissipation", "t0": 2.4, "t1": 2.55}, {"name": "residue", "t0": 2.55, "t1": 4.4}]}
    return {"name": "RiptideLance", "note": "Original no-reference beam (brief in build_riptide_lance.py): rings light in sequence and collapse, dark beat, two-stage surge, escalating coral impact, steam and trench.",
            "duration": 4.6, "seed": 33, "camera": {"pos": [14, 8, 11], "at": [-1, 3.2, -13], "fov": 58},
            "stage": {"ground": "light", "dummy": True}, "brief": brief, "instances": inst, "timeline": tl}


if __name__ == "__main__":
    p = Path(__file__).resolve().parent / "riptide_lance.json"
    from roblox_units import to_roblox_units
    p.write_text(json.dumps(to_roblox_units(build()), indent=1))
    print("wrote", p)
