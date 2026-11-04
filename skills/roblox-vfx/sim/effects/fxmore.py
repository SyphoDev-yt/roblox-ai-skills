"""More effect blocks for the 20-move batch (build_moves2.py, build_moves3.py):
magic circles that spin, glyph drift, trails, solid props (swords, books),
a stand-in enemy that can be knocked back, travelling projectiles.
"""
import numpy as np

from fxlib import NR, NS, CS, C3, V3, V2, E, FB4, STAR, PERP, PAR, pe, att, part, sa, mesh, _rot

WHITE = (1, 1, 1)


def brief(name, cat, tier, dom, acc, beats, phases, shape, style="anime_cel"):
    return {"name": name, "category": cat, "tier": tier, "style": style, "shape": shape, "dominant": dom, "accent": acc,
            "signature_beats": beats, "phases": [{"name": n, "t0": round(a, 3), "t1": round(b, 3)} for n, a, b in phases]}


def normal_of(rot):
    return _rot(*rot) @ np.array([0, 1, 0])


def circle(t, nm, pos, rot, d, tint, t0, t1, alt="sigil", spin=40, emis=1.6, layers=("outer", "band", "inner", "core"), grow=0.32):
    """Layered magic circle on flat planes (normal = local +Y). Pops in with a
    Back ease layer by layer, counter-rotates, then erodes out (grows while it
    fades) at t1. Returns the MeshParts."""
    n = normal_of(rot)
    out = []
    for j, layer in enumerate(layers):
        nmj = f"{nm}_{layer}"
        dd = d * (1 - 0.07 * j)
        p = [float(pos[k] + n[k] * 0.035 * j) for k in range(3)]
        out.append(mesh(nmj, "plane", p + list(rot), [0.2, 0.05, 0.2], [sa(f"{alt}_{layer}", tint, emis, tint)]))
        ta = t0 + 0.05 * j
        sgn = 1 if j % 2 == 0 else -1.4
        t(ta, do="set", target=nmj, prop="Transparency", value=0.02)
        t(ta, do="tween", target=nmj, prop="Size", from_=[0.2, 0.05, 0.2], to=[dd, 0.05, dd], time=grow, style="Back", dir="Out")
        life = t1 + 0.3 - ta
        t(ta, do="spin", target=nmj, axis="Y", rate=spin * sgn, time=life)
        t(t1, do="tween", target=nmj, prop="Transparency", to=1, time=0.28, style="Quad", dir="In")
        t(t1, do="tween", target=nmj, prop="Size", to=[dd * 1.25, 0.05, dd * 1.25], time=0.28, style="Quad", dir="Out")
    return out


def glyphs(nm, pos, rot, radius, tint, speed=(1.2, 2.4)):
    """Rune glyphs drifting off a circle. Stream '<nm>.Runes'."""
    return part(nm, list(pos) + list(rot), [pe("Runes", Texture="sim:glyph_2x2", **STAR, Shape=E("ParticleEmitterShape.Sphere"), ShapeStyle=E("ParticleEmitterShapeStyle.Surface"),
                                              Lifetime=NR(0.5, 0.9), Speed=NR(*speed), Drag=1.5, Size=NS((0, 0.35), (0.2, 0.55), (1, 0.4)),
                                              Transparency=NS((0, 0.1), (0.6, 0.2), (1, 1)), Color=CS((0, WHITE), (1, tint)), LightEmission=1, Brightness=1.8)],
                size=(radius * 2, radius * 2, radius * 2), shape="Ball")


def gather(nm, pos, radius, col, rate_name="Pull"):
    """Sparks drawn inward to a point. Stream '<nm>.Pull'."""
    return part(nm, list(pos) + [0, 0, 0], [pe(rate_name, Texture="sim:spark_needle", **PAR, Shape=E("ParticleEmitterShape.Sphere"), ShapeStyle=E("ParticleEmitterShapeStyle.Surface"),
                                              ShapeInOut=E("ParticleEmitterShapeInOut.Inward"), Lifetime=NR(0.2, 0.32), Speed=NR(radius * 2.2, radius * 3.2),
                                              Size=NS((0, 0.55, 0.2), (1, 0.15)), Color=CS((0, WHITE), (1, col)), LightEmission=1, Brightness=2)],
                size=(radius * 2, radius * 2, radius * 2), shape="Ball")


def trail_kids(owner, w, col, life, tex="beam_paint", le=0.6, tr0=0.0, bright=1.4, col1=None):
    return [att("T0", [], [0, w / 2, 0, 0, 0, 0]), att("T1", [], [0, -w / 2, 0, 0, 0, 0]),
            {"class": "Trail", "name": "Trail", "props": {"Attachment0": {"Ref": f"{owner}.T0"}, "Attachment1": {"Ref": f"{owner}.T1"}, "Lifetime": life,
             "Texture": f"sim:{tex}", "TextureMode": E("TextureMode.Stretch"), "FaceCamera": True, "LightEmission": le, "Brightness": bright,
             "Color": CS((0, WHITE), (0.15, col), (1, col1 or col)), "Transparency": NS((0, tr0), (0.5, 0.3), (1, 1)), "WidthScale": NS((0, 1), (1, 0.1)), "MinLength": 0.05}}]


def solid(name, cf, size, col, material="SmoothPlastic", follow=None, offset=None, transparency=0, shape=None, children=()):
    d = {"class": "Part", "name": name, "CFrame": list(cf), "Size": list(size), "Transparency": transparency, "Color": list(col), "Material": material,
         "children": list(children)}
    if shape:
        d["Shape"] = shape
    if follow:
        d["Follow"] = follow
        d["FollowOffset"] = offset or [0, 0, 0, 0, 0, 0]
    return d


def sword(name="Blade", length=4.2, width=0.45, col=(0.78, 0.8, 0.84), material="Metal"):
    """A blade continuing the arm line (the sword reads as the swing arc)."""
    return solid(name, [0, 0, 0, 0, 0, 0], [width, length, 0.18], col, material, follow="RightHand", offset=[0, -length / 2 + 0.35, 0, 0, 0, 0])


ENEMY_PARTS = (("LeftLeg", [1, 2, 1], (-0.5, 1, 0)), ("RightLeg", [1, 2, 1], (0.5, 1, 0)), ("Torso", [2, 2, 1], (0, 3, 0)),
               ("LeftArm", [1, 2, 1], (-1.5, 3, 0)), ("RightArm", [1, 2, 1], (1.5, 3, 0)), ("Head", [1.2, 1.2, 1.2], (0, 4.6, 0)))


def enemy(prefix, at, col=(0.42, 0.36, 0.38)):
    """Stand-in target figure (six blocks) so hits land on something."""
    parts = [solid(f"{prefix}{nm}", [at[0] + o[0], at[1] + o[1], at[2] + o[2], 0, 0, 0], s, col) for nm, s, o in ENEMY_PARTS]
    for p_ in parts:
        p_["simOnly"] = True   # Studio: skipped, the real target character stands at TARGET_AT
    return parts


def knock(t, prefix, t0, by, time=0.35, tilt=0.0):
    for nm, _, o in ENEMY_PARTS:
        lift = o[1] * tilt
        t(t0, do="tween", target=f"{prefix}{nm}", prop="CFrame", by=[by[0], by[1], by[2] - lift, 0, 0, 0], time=time, style="Quad", dir="Out")


def ring_burst(nm, cf, col, size=(3, 14), life=0.35, face="Top", le=0.5):
    """Painted shock ring facing a direction. Emit '<nm>.A.Ring'."""
    return part(nm, cf, [att("A", [pe("Ring", Texture="sim:ring_paint_4x4", **FB4, Orientation=E("ParticleOrientation.VelocityPerpendicular"),
                                       EmissionDirection=E(f"NormalId.{face}"), Speed=NR(0.01), Lifetime=NR(life), Size=NS((0, size[0]), (1, size[1])),
                                       Color=CS((0, WHITE), (0.3, col), (1, col)), LightEmission=le, Brightness=1.3, ZOffset=0.4)])])


def smoke(nm, cf, col, size=(2.5, 5.5), life=(1.0, 1.7), speed=(3, 8), rise=4, tex="smoke_wisp_4x4", radius=3):
    """Residue smoke. Emit/stream '<nm>.Puffs'."""
    return part(nm, cf, [pe("Puffs", Texture=f"sim:{tex}", **FB4, Shape=E("ParticleEmitterShape.Sphere"), Lifetime=NR(*life), Speed=NR(*speed),
                            Drag=1.2, Acceleration=V3(0, rise, 0), Size=NS((0, size[0], 0.6), (1, size[1], 1)), Rotation=NR(0, 360), RotSpeed=NR(-40, 40),
                            Color=CS((0, col), (1, tuple(c * 0.7 for c in col))), LightInfluence=0.4)], size=(radius, radius, radius), shape="Ball")


def decal(nm, pos, size, tex, col, emis=2.2, et=None, rot_y=0):
    """Ground decal (plane mesh); set Transparency to show it."""
    return mesh(nm, "plane", [pos[0], pos[1], pos[2], 0, rot_y, 0], [size[0], 0.05, size[1]], [sa(tex, col, emis, et or col)])
