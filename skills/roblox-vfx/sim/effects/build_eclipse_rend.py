"""Eclipse Rend: an original slash, designed with NO reference (references/DESIGN.md).

BRIEF
  Name:           Eclipse Rend
  Fantasy:        a crescent cut that swallows the light, leaving a dark sun hanging where it hit
  Tier:           skill (0.8-2.0 s)
  Style family:   anime_cel (styles/anime_cel.md)
  Category:       slash (corpus/CATEGORIES.md: flash 1 frame, 6-7 layers, residue:main 0.17-0.95)
  Shape word:     crescent / eclipse
  Dominant:       #7a4dff violet     Accent: #ffcf5a gold (complementary)     Darks: #12081f
  Colour arc:     gold glint -> world dims -> white 1-frame contact -> violet crescents with gold
                  leading edge -> dark eclipse with gold corona + violet-grey smoke
  Signature beats: dark beat before release; shape born at full size; TWIST: the cut leaves a
                  dark eclipse disc with a gold corona hanging at the point of contact, and a
                  thin gold cut-line that stays in the air and thins away
  Timeline:       anticipation 0.00-0.25 | release 0.25-0.27 | sustain 0.27-0.55 | residue 0.55-1.45
  Staging:        gameplay camera, light shake on contact, world desaturates 0.12-0.25 s
  Residue:        eclipse + cut-line + smoke, ~0.9 s (residue:main ~ 0.9/0.3 = 3 within tier)
"""
import json
import math
from pathlib import Path

VIOLET, GOLD, DARK = (0.48, 0.30, 1.0), (1.0, 0.81, 0.35), (0.07, 0.03, 0.12)


def NR(a, b=None): return {"NumberRange": [a, a if b is None else b]}
def NS(*k): return {"NumberSequence": [list(p) for p in k]}
def CS(*k): return {"ColorSequence": [[t, list(c)] for t, c in k]}
def E(e): return {"Enum": e}


FB = {"FlipbookLayout": E("ParticleFlipbookLayout.Grid4x4"), "FlipbookMode": E("ParticleFlipbookMode.OneShot"), "FlipbookBlendFrames": False}
PERP = {"Orientation": E("ParticleOrientation.VelocityPerpendicular"), "Speed": NR(0.01)}


def pe(name, **p):
    return {"class": "ParticleEmitter", "name": name, "props": dict({"Rate": 0}, **p)}


def build():
    REL = 0.25
    TILT = [0, 4.3, 0, 22, 0, -14]
    crescent = [
        pe("DarkUnder", Texture="sim:slash_paint_4x4", **FB, **PERP, Lifetime=NR(0.45), Rotation=NR(174, 177), RotSpeed=NR(-300),
           Size=NS((0, 13.6, 0.15), (1, 13.6, 0.15)), Transparency=NS((0, 0.5), (0.55, 0.5), (1, 1)),
           Color=CS((0, (0.18, 0.08, 0.32)), (1, (0.12, 0.05, 0.22))), LightEmission=0, ZOffset=0),
        pe("Body", Texture="sim:slash_paint_4x4", **FB, **PERP, Lifetime=NR(0.42), Rotation=NR(175, 175), RotSpeed=NR(-300),
           Size=NS((0, 13.0, 0.3), (1, 13.0, 0.3)), Transparency=NS((0, 0), (0.6, 0), (1, 1)),
           Color=CS((0, VIOLET), (1, (0.36, 0.22, 0.85))), LightEmission=0, ZOffset=0.01),
        pe("Ink", Texture="sim:slash_paint_b_4x4", **FB, **PERP, Lifetime=NR(0.44), Rotation=NR(160, 168), RotSpeed=NR(-280),
           Size=NS((0, 12.2, 0.4), (1, 12.6, 0.4)), Transparency=NS((0, 0.1), (0.55, 0.1), (1, 1)),
           Color=CS((0, (0.3, 0.14, 0.7)), (1, (0.22, 0.1, 0.5))), LightEmission=0, ZOffset=0.02),
        pe("Rim", Texture="sim:slash_paint_rim_4x4", **FB, **PERP, Lifetime=NR(0.42), Rotation=NR(175, 175), RotSpeed=NR(-300),
           Size=NS((0, 13.0, 0.3), (1, 13.0, 0.3)), Transparency=NS((0, 0), (0.5, 0), (1, 1)),
           Color=CS((0, (1, 1, 1)), (0.18, (0.86, 0.78, 1.0)), (1, VIOLET)), LightEmission=0.5, Brightness=1.2, ZOffset=0.03),
    ]
    inst = [
        {"class": "Part", "name": "Slash", "CFrame": TILT, "Size": [1, 1, 1], "Transparency": 1,
         "children": [{"class": "Attachment", "name": "Core", "children": crescent}]},
    ]
    # curved stroke beams on one pivot (5 strokes + a dark shadow stroke)
    atts, beams = [], []
    # radii, widths, curve asymmetry and start frames deliberately irregular (blind review round 1)
    strokes = [("Shadow", 5.5, 0.1, 2.9, DARK, 0, 1.0), ("S1", 5.5, 0.1, 2.3, VIOLET, 1, 1.4), ("S2", 6.1, -0.25, 1.0, (0.62, 0.45, 1.0), 1, 1.0),
               ("S3", 4.6, 0.4, 1.5, (0.85, 0.75, 1.0), 1, 1.0), ("Gold", 7.3, -0.4, 0.45, GOLD, 1, 1.6), ("S4", 6.6, 0.25, 0.3, VIOLET, 1, 1.0)]
    asym = {"Shadow": (1.0, 1.0), "S1": (1.0, 1.0), "S2": (1.25, 0.8), "S3": (0.85, 1.15), "Gold": (1.15, 0.75), "S4": (0.7, 1.3)}
    delay = {"Shadow": 0, "S1": 0, "S2": 1, "S3": 2, "Gold": 1, "S4": 3}
    for i, (nm, r, dy, w, col, le, br) in enumerate(strokes):
        atts += [{"class": "Attachment", "name": f"L{i}", "CFrame": [-r, dy, 0, 0, 90, 0]}, {"class": "Attachment", "name": f"R{i}", "CFrame": [r, dy, 0, 0, -90, 0]}]
        beams.append({"class": "Beam", "name": nm, "props": {
            "Attachment0": {"Ref": f"Pivot.L{i}"}, "Attachment1": {"Ref": f"Pivot.R{i}"}, "Enabled": False,
            "CurveSize0": r * 4 / 3 * asym[nm][0], "CurveSize1": r * 4 / 3 * asym[nm][1], "Segments": 48, "FaceCamera": True, "Width0": 0, "Width1": w,
            "Texture": "sim:beam_paint", "TextureSpeed": 0, "LightEmission": le, "Brightness": br,
            "Color": CS((0, col), (1, col)), "Transparency": NS((0, 1), (0.25, 0.25 if le else 0.5), (0.85, 0.05 if le else 0.45), (1, 1)),
            "ZOffset": -0.02 if nm == "Shadow" else 0.0}})
    inst.append({"class": "Part", "name": "Pivot", "CFrame": TILT, "Size": [1, 1, 1], "Transparency": 1, "children": atts + beams})
    # blade glint + inward strands (anticipation)
    inst.append({"class": "Part", "name": "Blade", "Shape": "Ball", "CFrame": [2.2, 4.4, 1.2, 0, 0, 0], "Size": [3, 3, 3], "Transparency": 1, "children": [
        pe("Strands", Texture="sim:spark_needle", Shape=E("ParticleEmitterShape.Sphere"), ShapeStyle=E("ParticleEmitterShapeStyle.Surface"),
           ShapeInOut=E("ParticleEmitterShapeInOut.Inward"), Orientation=E("ParticleOrientation.VelocityParallel"), Lifetime=NR(0.12, 0.2),
           Speed=NR(10, 16), Size=NS((0, 0.5, 0.15), (1, 0.2)), Color=CS((0, (0.75, 0.6, 1.0)), (1, VIOLET)), LightEmission=1, Brightness=2),
        pe("Glint", Texture="sim:impact_star4_2x2", FlipbookLayout=E("ParticleFlipbookLayout.Grid2x2"), FlipbookStartRandom=True,
           FlipbookFramerate=NR(0), Lifetime=NR(0.16), Speed=NR(0), Size=NS((0, 0.6), (0.4, 2.6), (1, 0)),
           Color=CS((0, GOLD), (1, GOLD)), LightEmission=1, Brightness=2.5, ZOffset=1)]})
    # contact: 1-frame flare, cel burst, gold spark fan with gravity, eclipse residue, smoke
    contact = [
        pe("Flare", Texture="sim:impact_star4_2x2", FlipbookLayout=E("ParticleFlipbookLayout.Grid2x2"), FlipbookStartRandom=True,
           FlipbookFramerate=NR(0), Lifetime=NR(0.05), Speed=NR(0), Size=NS((0, 4.5), (1, 7)), Color=CS((0, (1, 1, 1)), (1, GOLD)),
           LightEmission=1, Brightness=3, ZOffset=2),
        pe("Burst", Texture="sim:impact_burst_4x4", **FB, Lifetime=NR(0.22), Speed=NR(0), Size=NS((0, 5.5), (1, 6.5)), Rotation=NR(0, 360),
           Color=CS((0, (1, 1, 1)), (0.3, (0.8, 0.7, 1.0)), (1, VIOLET)), LightEmission=0.6, Brightness=1.5, ZOffset=1.5),
        pe("Sparks", Texture="sim:spark_needle", Orientation=E("ParticleOrientation.VelocityParallel"), EmissionDirection=E("NormalId.Front"),
           SpreadAngle={"Vector2": [55, 35]}, Lifetime=NR(0.3, 0.55), Speed=NR(26, 46), Drag=3, Acceleration={"Vector3": [0, -38, 0]},
           Size=NS((0, 0.55, 0.15), (1, 0.15)), Color=CS((0, (1, 0.95, 0.75)), (0.5, GOLD), (1, (0.9, 0.35, 0.15))), LightEmission=1, Brightness=2),
        pe("Eclipse", Texture="sim:eclipse_paint", Lifetime=NR(0.55), Speed=NR(0.9), EmissionDirection=E("NormalId.Top"), Drag=1.5,
           Rotation=NR(0, 360), RotSpeed=NR(-35),
           Size=NS((0, 0.4), (0.07, 3.6), (0.25, 3.1), (0.45, 3.4), (0.7, 2.9), (1, 0)), Transparency=NS((0, 0), (0.8, 0), (1, 1)),
           Color=CS((0, GOLD), (1, (1, 0.62, 0.3))), LightEmission=0, ZOffset=2.5),
        pe("Smoke", Texture="sim:smoke_wisp_4x4", **FB, Lifetime=NR(0.6, 0.95), Speed=NR(2, 5), SpreadAngle={"Vector2": [180, 180]},
           Size=NS((0, 1.4, 0.7), (1, 3.0, 0.9)), Rotation=NR(0, 360), RotSpeed=NR(-60, 60), Color=CS((0, (0.62, 0.56, 0.75)), (1, (0.45, 0.42, 0.55))),
           LightEmission=0, LightInfluence=0.3, ZOffset=0.5),
    ]
    inst.append({"class": "Part", "name": "Contact", "CFrame": [3.6, 4.6, -2.6, 0, 0, 0], "Size": [1, 1, 1], "Transparency": 1,
                 "children": [{"class": "Attachment", "name": "A", "children": contact}]})
    # ground: cel shock ring + wind swirl
    ground = [
        pe("Ring", Texture="sim:ring_paint_4x4", **FB, **PERP, Lifetime=NR(0.4), Size=NS((0, 5), (1, 13)),
           Color=CS((0, (0.85, 0.75, 1.0)), (1, VIOLET)), LightEmission=0.4, ZOffset=0.2),
        pe("Wind", Texture="sim:wind_swirl_4x4", **FB, **PERP, Lifetime=NR(0.55), Rotation=NR(0, 360), RotSpeed=NR(-90),
           Size=NS((0, 6), (1, 11)), Transparency=NS((0, 0.3), (1, 1)), Color=CS((0, (0.75, 0.7, 0.9)), (1, (0.6, 0.55, 0.75))), LightEmission=0.2, ZOffset=0.1),
    ]
    inst.append({"class": "Part", "name": "Ground", "CFrame": [0, 0.08, 0, 0, 0, 0], "Size": [1, 0.1, 1], "Transparency": 1,
                 "children": [{"class": "Attachment", "name": "A", "children": ground}]})
    inst.append({"class": "Highlight", "name": "Hit", "props": {"Adornee": "Dummy", "FillColor": {"Color3": list(VIOLET)}, "FillTransparency": 1,
                 "OutlineTransparency": 1, "DepthMode": E("HighlightDepthMode.AlwaysOnTop")}})
    inst.append({"class": "ColorCorrectionEffect", "name": "Grade", "props": {"Brightness": 0, "Saturation": 0, "TintColor": {"Color3": [1, 1, 1]}}})
    inst.append({"class": "Part", "name": "Lamp", "CFrame": [0.7, 3.5, -0.7, 0, 0, 0], "Size": [1, 1, 1], "Transparency": 1,
                 "children": [{"class": "PointLight", "name": "L", "props": {"Brightness": 0, "Range": 16, "Color": {"Color3": list(VIOLET)}}}]})

    tl = []
    at = lambda t, **e: tl.append(dict(e, t=round(t, 4)))
    # anticipation
    at(0.0, do="set", target="Blade.Strands", prop="Rate", value=70)
    at(0.0, do="enable", target="Blade.Strands", duration=0.2)
    at(0.06, do="emit", target="Blade.Glint", count=1)
    at(0.12, do="tween", target="Grade", prop="Brightness", to=-0.22, time=0.1, style="Quad", dir="In")      # dark beat
    at(0.12, do="tween", target="Grade", prop="Saturation", to=-0.35, time=0.1, style="Quad", dir="In")
    # release: one white frame, everything full size
    at(REL, do="set", target="Grade", prop="Brightness", value=-0.2)          # an ECLIPSE: the hit darkens the world for 2 frames, the local flare carries the light
    at(REL, do="set", target="Grade", prop="TintColor", value={"Color3": [0.95, 0.88, 1.0]})
    at(REL + 2 / 60, do="set", target="Grade", prop="TintColor", value={"Color3": [1, 1, 1]})
    at(REL + 2 / 60, do="set", target="Grade", prop="Brightness", value=-0.1)
    at(REL + 1 / 60, do="tween", target="Grade", prop="Brightness", to=0, time=0.35, style="Quad", dir="Out")
    at(REL + 1 / 60, do="tween", target="Grade", prop="Saturation", to=0, time=0.35, style="Quad", dir="Out")
    at(REL, do="emit", target="Slash.Core", count=1)
    for nm, r, dy, w, *_ in strokes:
        t0 = REL + delay[nm] / 60
        at(t0, do="set", target=f"Pivot.{nm}", prop="Enabled", value=True)
        at(t0, do="tween", target=f"Pivot.{nm}", prop="Width1", **{"from": w * 1.25}, to=0, time=0.16 + 0.05 * ((len(nm) * 7 % 5) / 4), style="Linear")
    at(REL, do="tween", target="Pivot", prop="CFrame", by=[0, 0, 0, 0, -175, 0], time=0.26, style="Linear")
    at(REL, do="emit", target="Contact.A.Flare", count=1)
    at(REL, do="emit", target="Contact.A.Burst", count=1)
    at(REL, do="emit", target="Contact.A.Sparks", count=18)
    at(REL, do="shake", amp=0.14, time=0.22, freq=28)
    at(REL, do="set", target="Lamp.L", prop="Brightness", value=4)
    at(REL + 0.02, do="tween", target="Lamp.L", prop="Brightness", to=0, time=0.35, style="Quad", dir="Out")
    at(REL + 0.03, do="tween", target="Hit", prop="FillTransparency", **{"from": 1}, to=0.5, time=0.07, style="Circular", dir="Out", reverses=True)
    # residue
    at(REL + 0.03, do="emit", target="Contact.A.Eclipse", count=1)
    at(REL + 0.05, do="emit", target="Contact.A.Smoke", count=9)
    at(REL + 0.06, do="emit", target="Ground.A.Ring", count=1)
    for nm, *_ in strokes:
        at(REL + 0.3, do="set", target=f"Pivot.{nm}", prop="Enabled", value=False)

    brief = {"name": "Eclipse Rend", "category": "slash", "tier": "skill", "style": "anime_cel", "shape": "crescent / eclipse",
             "dominant": "#7a4dff", "accent": "#ffcf5a", "darks": "#12081f",
             "signature_beats": ["dark beat before release", "shape born at full size", "hanging eclipse residue"],
             "phases": [{"name": "anticipation", "t0": 0.0, "t1": REL}, {"name": "release", "t0": REL, "t1": REL + 1 / 60},
                        {"name": "sustain", "t0": REL + 1 / 60, "t1": 0.68}, {"name": "residue", "t0": 0.68, "t1": 1.1}]}
    return {"name": "EclipseRend", "note": "Original no-reference slash (brief in build_eclipse_rend.py): dark beat, full-size crescent, gold corona eclipse left hanging at the contact.",
            "duration": 1.6, "seed": 21, "camera": {"pos": [9, 7, 12], "at": [0, 3, 0]}, "stage": {"ground": "light", "dummy": True},
            "brief": brief, "instances": inst, "timeline": tl}


if __name__ == "__main__":
    p = Path(__file__).resolve().parent / "eclipse_rend.json"
    from roblox_units import to_roblox_units
    p.write_text(json.dumps(to_roblox_units(build()), indent=1))
    print("wrote", p)
