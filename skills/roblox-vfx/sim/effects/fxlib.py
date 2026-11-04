"""Shared helpers for effect builders: typed values, instance makers, a
timeline recorder, an R6 POSE library and reusable effect blocks.

Pose angles are degrees per joint [rx, ry, rz] (vfxsim rig): rx +90 raises an
arm forward, rz + moves the RIGHT arm outward (left arm outward is rz -).
root = [x, y, z, yawDeg, pitchDeg] offset of the torso from the rig origin.
"""
import json
import math
from pathlib import Path


def NR(a, b=None): return {"NumberRange": [a, a if b is None else b]}
def NS(*k): return {"NumberSequence": [list(p) for p in k]}
def CS(*k): return {"ColorSequence": [[t, list(c)] for t, c in k]}
def C3(c): return {"Color3": list(c)}
def V3(x, y, z): return {"Vector3": [x, y, z]}
def V2(x, y): return {"Vector2": [x, y]}
def E(e): return {"Enum": e}


FB4 = {"FlipbookLayout": E("ParticleFlipbookLayout.Grid4x4"), "FlipbookMode": E("ParticleFlipbookMode.OneShot"), "FlipbookBlendFrames": False}
FB4LOOP = {"FlipbookLayout": E("ParticleFlipbookLayout.Grid4x4"), "FlipbookMode": E("ParticleFlipbookMode.Loop"), "FlipbookBlendFrames": False, "FlipbookFramerate": NR(18, 24)}
STAR = {"FlipbookLayout": E("ParticleFlipbookLayout.Grid2x2"), "FlipbookStartRandom": True, "FlipbookFramerate": NR(0)}
PERP = {"Orientation": E("ParticleOrientation.VelocityPerpendicular"), "Speed": NR(0.01)}
PAR = {"Orientation": E("ParticleOrientation.VelocityParallel")}


def pe(name, **p):
    return {"class": "ParticleEmitter", "name": name, "props": dict({"Rate": 0}, **p)}


def att(name, children, cf=None):
    d = {"class": "Attachment", "name": name, "children": children}
    if cf:
        d["CFrame"] = cf
    return d


def part(name, cf, children=(), size=(1, 1, 1), shape=None, follow=None, offset=None):
    d = {"class": "Part", "name": name, "CFrame": cf, "Size": list(size), "Transparency": 1, "children": list(children)}
    if shape:
        d["Shape"] = shape
    if follow:
        d["Follow"] = follow
        d["FollowOffset"] = offset or [0, 0, 0, 0, 0, 0]
        _lock(d)
    return d


def _lock(node):
    """Effects held in a hand must move WITH it: LockedToPart on every emitter
    under a following part, unless the builder chose otherwise (inward
    gathering sparks are fine either way). Without it the orb stays behind
    when the body lunges (found on the Rasengan study)."""
    for c in node.get("children", []):
        if c.get("class") == "ParticleEmitter":
            c["props"].setdefault("LockedToPart", True)
        _lock(c)


def sa(tex, col, emis=1.0, et=(1, 1, 1)):
    return {"class": "SurfaceAppearance", "name": "Look", "props": {"ColorMap": f"sim:{tex}", "EmissiveMask": f"sim:{tex}",
            "AlphaMode": E("AlphaMode.Transparency"), "Color": C3(col), "EmissiveStrength": emis, "EmissiveTint": C3(et)}}


def mesh(name, mid, cf, size, children=(), material="SmoothPlastic", color=(1, 1, 1), transparency=1):
    return {"class": "MeshPart", "name": name, "MeshId": f"sim:{mid}", "Material": material, "Color": list(color), "Transparency": transparency,
            "CFrame": cf, "Size": list(size), "props": {"DoubleSided": True}, "children": list(children)}


def beam(name, a0, a1, width, col, tex="beam_energy", le=0.4, tr=0.05, curve=(0, 0), z=0.0, bright=1.0, mode="Wrap", length=9, speed=3):
    return {"class": "Beam", "name": name, "props": {"Attachment0": {"Ref": a0}, "Attachment1": {"Ref": a1}, "Enabled": False, "FaceCamera": True,
            "Segments": 24, "Width0": width * 0.6, "Width1": width, "Texture": f"sim:{tex}", "TextureMode": E(f"TextureMode.{mode}"),
            "TextureLength": length, "TextureSpeed": speed, "LightEmission": le, "Brightness": bright, "CurveSize0": curve[0], "CurveSize1": curve[1],
            "Color": CS((0, col), (1, col)), "Transparency": NS((0, tr), (0.92, tr), (1, 1)), "ZOffset": z}}


class TL:
    def __init__(self):
        self.ev = []

    def __call__(self, t, **e):
        if "from_" in e:
            e["from"] = e.pop("from_")
        e["t"] = round(t, 4)
        self.ev.append(e)

    def emit(self, t, target, count=1):
        self(t, do="emit", target=target, count=count)

    def stream(self, t, target, rate, duration):
        self(t, do="set", target=target, prop="Rate", value=rate)
        self(t, do="enable", target=target, duration=duration)

    def flash(self, t, frames=1, value=0.9, grade="Grade", tint=None):
        self(t, do="set", target=grade, prop="Brightness", value=value)
        if tint:
            self(t, do="set", target=grade, prop="TintColor", value=C3(tint))
            self(t + frames / 60, do="set", target=grade, prop="TintColor", value=C3((1, 1, 1)))
        self(t + frames / 60, do="set", target=grade, prop="Brightness", value=0)

    def hit(self, t, damage, knock=(0, 0, 0), reaction="flinch", stun=0.35, target="Foe", time=0.22, ultimate=False):
        """A damage event on the target: the Studio kit forwards it to the game's
        hit system (health bar, damage number, hit flash, reaction). The sim only
        records it (the stand-in dummy's knock tweens show the motion there).
        reaction: flinch | launch | ragdoll. knock: studs, in effect space."""
        e = dict(do="hit", target=target, damage=damage, knock=list(knock), reaction=reaction, stun=stun, time=time)
        if ultimate:
            e["ultimate"] = True
        self(t, **e)

    def bw_frame(self, t, frames=2, grade="Grade"):
        self(t, do="set", target=grade, prop="Saturation", value=-1)
        self(t, do="set", target=grade, prop="Contrast", value=0.9)
        self(t + frames / 60, do="set", target=grade, prop="Saturation", value=0)
        self(t + frames / 60, do="set", target=grade, prop="Contrast", value=0)


# R6 poses (degrees). Built by eye in the sim; keep them as data so the same
# library later drives roblox-animation KeyframeSequences.
POSES = {
    "idle": {"RightArm": [0, 0, 8], "LeftArm": [0, 0, -8]},
    "guard": {"Torso": [8, 0, 0], "RightArm": [40, 0, -20], "LeftArm": [40, 0, 20], "RightLeg": [0, 0, 10], "LeftLeg": [0, 0, -10]},
    "kame_charge": {"Torso": [12, 35, 0], "Head": [0, -30, 0], "RightArm": [-25, 0, 10], "LeftArm": [-15, -20, -55], "RightLeg": [0, 0, 18], "LeftLeg": [0, 0, -18]},
    "kame_fire": {"Torso": [-6, 0, 0], "RightArm": [90, 0, -9], "LeftArm": [90, 0, 9], "RightLeg": [10, 0, 16], "LeftLeg": [-12, 0, -16]},
    "palm_hold": {"Torso": [10, 15, 0], "RightArm": [55, 0, -12], "LeftArm": [20, 0, -25], "RightLeg": [0, 0, 12], "LeftLeg": [0, 0, -12]},
    "palm_thrust": {"Torso": [18, -10, 0], "RightArm": [95, 0, -4], "LeftArm": [-35, 0, -10], "RightLeg": [-30, 0, 6], "LeftLeg": [35, 0, -6]},
    "arms_wide": {"Torso": [-5, 0, 0], "RightArm": [15, 0, 75], "LeftArm": [15, 0, -75], "RightLeg": [0, 0, 10], "LeftLeg": [0, 0, -10]},
    "hands_meet": {"Torso": [4, 0, 0], "RightArm": [82, 0, -32], "LeftArm": [82, 0, 32], "RightLeg": [0, 0, 10], "LeftLeg": [0, 0, -10]},
    "point_fwd": {"Torso": [0, -15, 0], "RightArm": [92, 0, -4], "LeftArm": [10, 0, -15], "RightLeg": [0, 0, 10], "LeftLeg": [0, 0, -10]},
    "sword_ready": {"Torso": [22, 20, 0], "Head": [-15, -15, 0], "RightArm": [70, 0, -35], "LeftArm": [70, 0, 35], "RightLeg": [-20, 0, 22], "LeftLeg": [25, 0, -18]},
    "dash_lean": {"Torso": [35, 0, 0], "Head": [-25, 0, 0], "RightArm": [-50, 0, 15], "LeftArm": [-50, 0, -15], "RightLeg": [-35, 0, 5], "LeftLeg": [40, 0, -5]},
    "slash_through": {"Torso": [15, -35, 0], "Head": [-5, 25, 0], "RightArm": [95, 0, 55], "LeftArm": [95, 0, -55], "RightLeg": [-25, 0, 15], "LeftLeg": [30, 0, -15]},
    "punch_wind": {"Torso": [5, 40, 0], "RightArm": [-35, 0, 25], "LeftArm": [55, 0, 10], "RightLeg": [20, 0, 12], "LeftLeg": [-20, 0, -12]},
    "punch": {"Torso": [10, -30, 0], "RightArm": [92, 0, 0], "LeftArm": [-25, 0, -18], "RightLeg": [-25, 0, 10], "LeftLeg": [30, 0, -10]},
    "crouch_low": {"Torso": [30, 0, 0], "Head": [-25, 0, 0], "RightArm": [-15, 0, 30], "LeftArm": [-15, 0, -30], "RightLeg": [-40, 0, 15], "LeftLeg": [-40, 0, -15]},
    "land_pose": {"Torso": [10, 60, 0], "Head": [0, -50, 0], "RightArm": [20, 0, 70], "LeftArm": [60, 0, -10], "RightLeg": [-20, 0, 20], "LeftLeg": [20, 0, -20]},
    # magic / weapon batch (build_moves2.py)
    "cast_fwd": {"Torso": [0, -12, 0], "RightArm": [90, 0, -4], "LeftArm": [40, 0, 30], "RightLeg": [-10, 0, 10], "LeftLeg": [12, 0, -10]},
    "cast_both": {"Torso": [-4, 0, 0], "RightArm": [88, 0, -14], "LeftArm": [88, 0, 14], "RightLeg": [-8, 0, 12], "LeftLeg": [10, 0, -12]},
    "arm_up": {"Torso": [-8, 0, 0], "Head": [-20, 0, 0], "RightArm": [170, 0, -8], "LeftArm": [20, 0, -20], "RightLeg": [0, 0, 10], "LeftLeg": [0, 0, -10]},
    "summon_up": {"Torso": [-10, 0, 0], "Head": [-25, 0, 0], "RightArm": [160, 0, 22], "LeftArm": [160, 0, -22], "RightLeg": [0, 0, 12], "LeftLeg": [0, 0, -12]},
    "palm_down": {"Torso": [20, 0, 0], "RightArm": [40, 0, -10], "LeftArm": [40, 0, 10], "RightLeg": [-20, 0, 14], "LeftLeg": [-20, 0, -14]},
    "kneel_ground": {"Torso": [38, 0, 0], "Head": [-30, 0, 0], "RightArm": [70, 0, -6], "LeftArm": [-10, 0, -25], "RightLeg": [-60, 0, 10], "LeftLeg": [20, 0, -10]},
    "sword_overhead": {"Torso": [-12, 10, 0], "Head": [10, -10, 0], "RightArm": [165, 0, -18], "LeftArm": [165, 0, 18], "RightLeg": [-15, 0, 14], "LeftLeg": [20, 0, -12]},
    "sword_down": {"Torso": [28, -5, 0], "Head": [-20, 0, 0], "RightArm": [45, 0, -16], "LeftArm": [45, 0, 16], "RightLeg": [-35, 0, 12], "LeftLeg": [35, 0, -10]},
    "side_wind": {"Torso": [8, 55, 0], "Head": [0, -45, 0], "RightArm": [70, 0, 75], "LeftArm": [60, 0, 30], "RightLeg": [10, 0, 16], "LeftLeg": [-15, 0, -14]},
    "side_follow": {"Torso": [12, -55, 0], "Head": [0, 40, 0], "RightArm": [85, 0, -55], "LeftArm": [70, 0, -15], "RightLeg": [-25, 0, 14], "LeftLeg": [25, 0, -14]},
    "stab": {"Torso": [18, -22, 0], "Head": [-10, 15, 0], "RightArm": [92, 0, 2], "LeftArm": [-30, 0, -20], "RightLeg": [-40, 0, 8], "LeftLeg": [40, 0, -8]},
    "crouch_charge": {"Torso": [25, 20, 0], "Head": [-20, -15, 0], "RightArm": [-10, 0, 40], "LeftArm": [40, 0, -30], "RightLeg": [-35, 0, 16], "LeftLeg": [-30, 0, -16]},
    "punch_l": {"Torso": [10, 30, 0], "LeftArm": [92, 0, 0], "RightArm": [-25, 0, 18], "RightLeg": [-25, 0, 10], "LeftLeg": [30, 0, -10]},
    "smash_wind": {"Torso": [15, 55, 0], "Head": [0, -45, 0], "RightArm": [-50, 0, 30], "LeftArm": [70, 0, 20], "RightLeg": [25, 0, 16], "LeftLeg": [-30, 0, -14]},
}


# ------------------------------------------------------------- rig points
# Python twin of vfxsim.js rigCFs, so builders can place world effects where
# a hand WILL be at a pose (circles that must spin cannot Follow the hand).
def _rot(rx, ry, rz):
    import numpy as np
    a, b, c = (math.radians(v) for v in (rx, ry, rz))
    X = np.array([[1, 0, 0], [0, math.cos(a), -math.sin(a)], [0, math.sin(a), math.cos(a)]])
    Y = np.array([[math.cos(b), 0, math.sin(b)], [0, 1, 0], [-math.sin(b), 0, math.cos(b)]])
    Z = np.array([[math.cos(c), -math.sin(c), 0], [math.sin(c), math.cos(c), 0], [0, 0, 1]])
    return X @ Y @ Z


def _cf(s):
    import numpy as np
    return (np.array(s[:3], float), _rot(*(list(s[3:6]) + [0, 0, 0])[:3]))


def _mul(A, B):
    return (A[0] + A[1] @ B[0], A[1] @ B[1])


def rig_point(pose, part="RightHand", root=(0, 0, 0, 0, 0), at=(0, 0, 0), facing=0, off=(0, 0, 0), stretch=None, reach=None):
    """World position of a rig part (plus a local offset) at a pose."""
    P = POSES[pose] if isinstance(pose, str) else pose
    g = lambda j: P.get(j, [0, 0, 0])
    r = list(root) + [0] * (5 - len(root))
    base = _cf([at[0], at[1], at[2], 0, facing, 0])
    torso = _mul(_mul(base, _cf([r[0], 3 + r[1], r[2], r[4], r[3], 0])), _cf([0, 0, 0] + g("Torso")))
    def kw(j):
        v = (stretch or {}).get(j, 1)
        return (v[0], v[1]) if isinstance(v, (list, tuple)) else (v, 1)
    kR, wR = kw("RightArm")
    kL, wL = kw("LeftArm")
    def rd(j):
        v = (reach or {}).get(j, 0)
        return v[0] if isinstance(v, (list, tuple)) else v
    chains = {"RightArm": ([1, 0.5, 0], [0.5 * wR, 0.5 - kR - rd("RightArm"), 0]), "LeftArm": ([-1, 0.5, 0], [-0.5 * wL, 0.5 - kL - rd("LeftArm"), 0]),
              "Head": ([0, 1, 0], [0, 0.5, 0])}
    hand = part.endswith("Hand")
    limb = part.replace("Hand", "Arm")
    if limb == "Torso":
        cf = torso
    else:
        pv, of = chains[limb]
        cf = _mul(_mul(_mul(torso, _cf(pv + [0, 0, 0])), _cf([0, 0, 0] + g(limb))), _cf(of + [0, 0, 0]))
    if hand:
        cf = _mul(cf, _cf([0, -(kR if limb == "RightArm" else kL) - 0.15, 0, 0, 0, 0]))
    cf = _mul(cf, _cf(list(off) + [0, 0, 0]))
    return [round(float(v), 3) for v in cf[0]]


def key(t, pose, root=(0, 0, 0, 0, 0), style="Quad", dir="Out"):
    return {"t": t, "pose": POSES[pose] if isinstance(pose, str) else pose, "root": list(root), "style": style, "dir": dir}


# ----------------------------------------------------------------- blocks
def impact_block(name, cf, col, accent=(1, 1, 1), scale=1.0, sparks=True):
    """Flare + painted burst + spark fan, at one point. Emit '<name>.A.*'."""
    kids = [
        pe("Flare", Texture="sim:impact_star4_2x2", **STAR, Lifetime=NR(0.07), Speed=NR(0), Size=NS((0, 6 * scale), (1, 9 * scale)),
           Color=CS((0, (1, 1, 1)), (1, accent)), LightEmission=1, Brightness=3, ZOffset=3),
        pe("Burst", Texture="sim:impact_burst_4x4", **FB4, Lifetime=NR(0.26), Speed=NR(0), Size=NS((0, 7 * scale), (1, 8.5 * scale)), Rotation=NR(0, 360),
           Color=CS((0, (1, 1, 1)), (0.3, accent), (1, col)), LightEmission=0.5, Brightness=1.6, ZOffset=2),
    ]
    if sparks:
        kids.append(pe("Sparks", Texture="sim:spark_needle", **PAR, Shape=E("ParticleEmitterShape.Sphere"), Lifetime=NR(0.25, 0.5), Speed=NR(28 * scale, 55 * scale),
                       Drag=3, Acceleration=V3(0, -30, 0), Size=NS((0, 0.7 * scale, 0.2), (1, 0.15)), Squash=NS((0, 1.2), (1, 1.2)),
                       Color=CS((0, (1, 1, 1)), (0.4, accent), (1, col)), LightEmission=1, Brightness=2))
    return part(name, cf, [att("A", kids)])


def ground_block(name, cf, col, scale=1.0, dust_col=(0.78, 0.72, 0.66)):
    """Painted shock ring + dust ring + debris on the floor. Emit '<name>.A.Ring', '<name>.Dust', '<name>.Rocks'."""
    ring = pe("Ring", Texture="sim:ring_paint_4x4", **FB4, **PERP, Lifetime=NR(0.42), Size=NS((0, 6 * scale), (1, 22 * scale)),
              Color=CS((0, (1, 1, 1)), (1, col)), LightEmission=0.4, ZOffset=0.2)
    dust = pe("Dust", Texture="sim:smoke_dust_4x4", **FB4, Shape=E("ParticleEmitterShape.Cylinder"), ShapeStyle=E("ParticleEmitterShapeStyle.Surface"),
              Lifetime=NR(0.9, 1.5), Speed=NR(18 * scale, 32 * scale), Drag=1.4, Size=NS((0, 2.5 * scale, 0.7), (1, 5.5 * scale, 1.0)), Rotation=NR(0, 360),
              Color=CS((0, dust_col), (1, tuple(c * 0.8 for c in dust_col))), LightEmission=0, LightInfluence=0.4, ZOffset=0.5)
    rocks = pe("Rocks", Texture="sim:debris_rock_8x8", FlipbookLayout=E("ParticleFlipbookLayout.Grid8x8"), FlipbookMode=E("ParticleFlipbookMode.Loop"),
               FlipbookFramerate=NR(18, 30), FlipbookStartRandom=True, Shape=E("ParticleEmitterShape.Sphere"), ShapePartial=0.5,
               Lifetime=NR(0.7, 1.2), Speed=NR(20 * scale, 38 * scale), Acceleration=V3(0, -55, 0), Size=NS((0, 0.35 * scale, 0.15), (1, 0.3 * scale, 0.1)),
               Color=CS((0, (0.35, 0.3, 0.28)), (1, (0.25, 0.22, 0.2))), LightEmission=0, LightInfluence=0.5)
    return {"class": "Part", "name": name, "Shape": "Cylinder", "CFrame": cf, "Size": [4 * scale, 0.2, 4 * scale], "Transparency": 1,
            "children": [att("A", [ring]), dust, rocks]}


def grade():
    return {"class": "ColorCorrectionEffect", "name": "Grade", "props": {"Brightness": 0, "Contrast": 0, "Saturation": 0, "TintColor": C3((1, 1, 1))}}


def write(d, name):
    p = Path(__file__).resolve().parent / f"{name}.json"
    from roblox_units import to_roblox_units
    p.write_text(json.dumps(to_roblox_units(d), indent=1))
    idx = Path(__file__).resolve().parent / "index.json"
    L = json.loads(idx.read_text())
    if not any(e["file"] == p.name for e in L):
        L.append({"file": p.name, "title": d.get("title", d["name"])})
    idx.write_text(json.dumps(L, indent=1))
    print("wrote", p.name)
