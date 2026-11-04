"""Place prop meshes (sim/mesh/make_props.py) by their MODEL origin, using the
sizes and centres in meshes/props.json, so a sword's guard sits at the hand
and a rock's base sits on the ground without hand-typed offsets.

A MeshPart's CFrame is its bounding-box centre (the sim and Roblox both centre
the mesh), so placing by origin means CFrame = origin * CFrame(centre * scale).
"""
import json
from pathlib import Path

import numpy as np

from fxlib import C3, E, att, pe, _rot

PROPS = json.loads((Path(__file__).resolve().parent.parent / "meshes" / "props.json").read_text())


def box_of(mesh_name, scale=1.0):
    m = PROPS[mesh_name]
    s = scale if isinstance(scale, (list, tuple)) else (scale, scale, scale)
    return [round(m["size"][k] * s[k], 4) for k in range(3)], [m["centre"][k] * s[k] for k in range(3)]


def look(tex, col=(1, 1, 1), emis=0.0, et=(1, 1, 1), alpha=True):
    return {"class": "SurfaceAppearance", "name": "Look", "props": {"ColorMap": f"sim:{tex}", "EmissiveMask": f"sim:{tex}",
            "AlphaMode": E("AlphaMode.Transparency" if alpha else "AlphaMode.Overlay"), "Color": C3(col), "EmissiveStrength": emis, "EmissiveTint": C3(et)}}


def place(origin, centre):
    """origin: [x,y,z,rx,ry,rz] of the model origin; returns the part CFrame."""
    R = _rot(*origin[3:6])
    p = np.array(origin[:3], float) + R @ np.array(centre, float)
    return [round(float(v), 4) for v in p] + list(origin[3:6])


def prop(name, mesh_name, origin, scale=1.0, tex="stone_cel", col=(1, 1, 1), emis=0.0, et=(1, 1, 1), transparency=0.0, children=(), material="SmoothPlastic"):
    size, c = box_of(mesh_name, scale)
    return {"class": "MeshPart", "name": name, "MeshId": f"sim:{mesh_name}", "Material": material, "Color": [1, 1, 1], "Transparency": transparency,
            "CFrame": place(origin, c), "Size": size, "props": {"DoubleSided": True}, "children": [look(tex, col, emis, et)] + list(children)}


def held(name, mesh_name, grip_y, scale=1.0, tex="blade_katana", col=(1, 1, 1), emis=0.0, et=(1, 1, 1), hand="RightHand", extra=(0, 0, 0, 0, 0, 0), transparency=0.0):
    """A weapon held in a hand: the grip centre (model y = grip_y) sits in the
    fist and the blade continues down the arm line (model -Y)."""
    size, c = box_of(mesh_name, scale)
    off = [extra[0] + c[0], extra[1] + c[1] - grip_y * scale, extra[2] + c[2], extra[3], extra[4], extra[5]]
    return {"class": "MeshPart", "name": name, "MeshId": f"sim:{mesh_name}", "Material": "SmoothPlastic", "Color": [1, 1, 1], "Transparency": transparency,
            "CFrame": [0, 0, 0, 0, 0, 0], "Size": size, "props": {"DoubleSided": True}, "children": [look(tex, col, emis, et)],
            "Follow": hand, "FollowOffset": [round(v, 4) for v in off]}


GRIP = {"katana": 0.62, "sword_asta": 0.62, "sword_light": 0.42}
ROCKS = ["rock_0", "rock_1", "rock_2", "rock_3", "rock_4"]
STONE = (0.62, 0.55, 0.5)


# ------------------------------------------------------------- ground destruction
def crater(t, name, centre, radius, t0, tint=STONE, sink_at=None):
    """Uplifted ring of cracked slabs that punches up out of the ground at t0
    (a real mesh, not a decal). Optionally sinks back at sink_at."""
    s = radius / 1.2
    size, c = box_of("crater_rim", s)
    flat = [size[0] * 0.6, 0.05, size[2] * 0.6]
    cf = place([centre[0], 0.0, centre[2], 0, (sum(map(ord, name)) * 37 % 360), 0], c)
    part = {"class": "MeshPart", "name": name, "MeshId": "sim:crater_rim", "Material": "SmoothPlastic", "Color": [1, 1, 1], "Transparency": 1,
            "CFrame": [cf[0], 0.0] + cf[2:], "Size": flat, "props": {"DoubleSided": True}, "children": [look("stone_cel", tint)]}
    t(t0, do="set", target=name, prop="Transparency", value=0)
    t(t0, do="tween", target=name, prop="Size", from_=flat, to=size, time=0.18, style="Back", dir="Out")
    t(t0, do="tween", target=name, prop="CFrame", to=cf, time=0.18, style="Back", dir="Out")
    if sink_at:
        t(sink_at, do="tween", target=name, prop="CFrame", to=[cf[0], cf[1] - size[1] * 1.2] + cf[2:], time=1.2, style="Quad", dir="In")
        t(sink_at + 1.2, do="set", target=name, prop="Transparency", value=1)
    return part


def debris(t, prefix, centre, n, t0, scale=(0.5, 1.1), speed=(18, 34), up=(25, 45), tint=STONE, spread=360, heading=0, seed=1, sink_at=None, jitter=0.0,
           meshes=None, tex="stone_cel"):
    """n real rock chunks thrown from centre at t0 with Roblox physics (toss):
    random size, outward speed, upward kick and spin; they bounce, settle and
    (optionally) sink into the ground at sink_at."""
    import random
    import math
    rnd = random.Random(seed)
    parts = []
    for i in range(n):
        nm = f"{prefix}{i}"
        pool = meshes or ROCKS
        mesh_name = pool[(i + seed) % len(pool)]
        k = rnd.uniform(*scale)
        size, _ = box_of(mesh_name, k)
        p = [centre[0] + rnd.uniform(-0.6, 0.6), centre[1] + rnd.uniform(0, 0.6), centre[2] + rnd.uniform(-0.6, 0.6)]
        parts.append({"class": "MeshPart", "name": nm, "MeshId": f"sim:{mesh_name}", "Material": "SmoothPlastic", "Color": [1, 1, 1], "Transparency": 1,
                      "CFrame": p + [rnd.uniform(0, 360), rnd.uniform(0, 360), 0], "Size": size, "props": {"DoubleSided": True},
                      "children": [look(tex, tuple(c * rnd.uniform(0.85, 1.1) for c in tint))]})
        a = math.radians(heading + rnd.uniform(-spread / 2, spread / 2))
        sp = rnd.uniform(*speed)
        tt = t0 + rnd.uniform(0, jitter)
        t(tt, do="set", target=nm, prop="Transparency", value=0)
        t(tt, do="toss", target=nm, vel=[round(math.sin(a) * sp, 2), round(rnd.uniform(*up), 2), round(-math.cos(a) * sp, 2)],
          spin=[rnd.uniform(-400, 400), rnd.uniform(-400, 400), rnd.uniform(-400, 400)])
        if sink_at:
            t(sink_at + rnd.uniform(0, 0.4), do="tween", target=nm, prop="Size", to=[v * 0.05 for v in size], time=0.6, style="Quad", dir="In")
            t(sink_at + 1.1, do="set", target=nm, prop="Transparency", value=1)
    return parts
