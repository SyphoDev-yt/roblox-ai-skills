"""Prop, debris and creature meshes for VFX (RULE ZERO: an effect that needs a
thing gets the thing). Built in Blender, exported as OBJ for the sim and for
upload to Roblox, plus meshes/props.json with every mesh's Roblox-axis
bounding box and centre so builders never hand-type a size.

    "C:/Program Files/Blender Foundation/Blender 4.3/blender.exe" -b -P make_props.py

Axes: modelled in Blender axes, Blender +Z = Roblox +Y (up), Blender +Y =
Roblox -Z (forward). Held weapons: grip at the TOP (+Z), blade pointing DOWN
(-Z), so the blade continues the arm line from the hand (fxmore.sword()).

UV conventions (match the programmatic textures):
  rock_*, crater_rim, rock_spire, rock_fist, meteor   box projection, stone_cel
  blades                      U across the blade (edge 0 .. spine 1), V along it
  wave_blade                  U along the arc, V across (outer edge = 1)
  everything else             U around the long axis, V along it
"""
import json
import math
import os
import random

import bmesh
import bpy
from mathutils import Vector, noise

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "meshes")
MANIFEST = {}


def reset():
    bpy.ops.wm.read_factory_settings(use_empty=True)


def activate(ob):
    bpy.ops.object.select_all(action="DESELECT")
    ob.select_set(True)
    bpy.context.view_layer.objects.active = ob


def new_ob(name, bm):
    me = bpy.data.meshes.new(name)
    bm.to_mesh(me)
    bm.free()
    ob = bpy.data.objects.new(name, me)
    bpy.context.collection.objects.link(ob)
    return ob


def join(name, obs):
    bpy.ops.object.select_all(action="DESELECT")
    for o in obs:
        o.select_set(True)
    bpy.context.view_layer.objects.active = obs[0]
    if len(obs) > 1:
        bpy.ops.object.join()
    ob = bpy.context.view_layer.objects.active
    ob.name = name
    ob.data.name = name
    return ob


def clean_uv(me):
    while me.uv_layers:
        me.uv_layers.remove(me.uv_layers[0])
    uv = me.uv_layers.new(name="UVMap")
    me.uv_layers.active = uv
    return uv


def uv_box(ob, scale=0.5):
    """Box projection by face normal, world-scaled so texture density is even."""
    me = ob.data
    uv = clean_uv(me)
    for poly in me.polygons:
        n = poly.normal
        ax = max(range(3), key=lambda k: abs(n[k]))
        for li in poly.loop_indices:
            co = me.vertices[me.loops[li].vertex_index].co
            a, b = [(co.y, co.z), (co.x, co.z), (co.x, co.y)][ax]
            uv.data[li].uv = (a * scale + 0.5, b * scale + 0.5)


def uv_along(ob, axis="z"):
    """U around the long axis, V along it."""
    me = ob.data
    k = "xyz".index(axis)
    o = [i for i in range(3) if i != k]
    vals = [v.co[k] for v in me.vertices]
    lo, hi = min(vals), max(vals)
    uv = clean_uv(me)
    for poly in me.polygons:
        us = []
        for li in poly.loop_indices:
            co = me.vertices[me.loops[li].vertex_index].co
            us.append(math.atan2(co[o[0]], co[o[1]]) / (2 * math.pi) + 0.5)
        if max(us) - min(us) > 0.5:
            us = [u + 1 if u < 0.5 else u for u in us]
        for li, u in zip(poly.loop_indices, us):
            co = me.vertices[me.loops[li].vertex_index].co
            uv.data[li].uv = (u, (co[k] - lo) / max(hi - lo, 1e-6))


def uv_blade(ob):
    """U across the blade width (x), V along its length (z)."""
    me = ob.data
    xs = [v.co.x for v in me.vertices]
    zs = [v.co.z for v in me.vertices]
    x0, x1, z0, z1 = min(xs), max(xs), min(zs), max(zs)
    uv = clean_uv(me)
    for poly in me.polygons:
        for li in poly.loop_indices:
            co = me.vertices[me.loops[li].vertex_index].co
            uv.data[li].uv = ((co.x - x0) / max(x1 - x0, 1e-6), (co.z - z0) / max(z1 - z0, 1e-6))


def finish(ob, uvf=uv_along, smooth=True, **kw):
    activate(ob)
    bpy.ops.object.transform_apply(location=True, rotation=True, scale=True)
    bpy.ops.object.mode_set(mode="EDIT")
    bpy.ops.mesh.select_all(action="SELECT")
    bpy.ops.mesh.remove_doubles(threshold=0.0005)
    bpy.ops.mesh.normals_make_consistent(inside=False)
    bpy.ops.object.mode_set(mode="OBJECT")
    if smooth:
        bpy.ops.object.shade_smooth()
    else:
        bpy.ops.object.shade_flat()
    uvf(ob, **kw)
    return ob


def export(ob):
    activate(ob)
    path = os.path.join(OUT, ob.name + ".obj")
    bpy.ops.wm.obj_export(filepath=path, export_selected_objects=True, export_uv=True, export_normals=True,
                          export_materials=False, forward_axis="NEGATIVE_Z", up_axis="Y")
    cs = [v.co for v in ob.data.vertices]
    mn = Vector((min(c.x for c in cs), min(c.y for c in cs), min(c.z for c in cs)))
    mx = Vector((max(c.x for c in cs), max(c.y for c in cs), max(c.z for c in cs)))
    sz, c = mx - mn, (mn + mx) / 2
    tris = sum(len(p.vertices) - 2 for p in ob.data.polygons)
    MANIFEST[ob.name] = {"size": [round(sz.x, 4), round(sz.z, 4), round(sz.y, 4)], "centre": [round(c.x, 4), round(c.z, 4), round(-c.y, 4)], "tris": tris}
    print(f"MESH {ob.name}: {tris} tris size={MANIFEST[ob.name]['size']} centre={MANIFEST[ob.name]['centre']}")
    bpy.ops.object.select_all(action="SELECT")
    bpy.ops.object.delete()


# ------------------------------------------------------------- primitives
def box(bm, c, s, rz=0.0):
    r = bmesh.ops.create_cube(bm, size=1.0)
    for v in r["verts"]:
        v.co = Vector((v.co.x * s[0], v.co.y * s[1], v.co.z * s[2]))
        if rz:
            x, y = v.co.x, v.co.y
            v.co.x, v.co.y = x * math.cos(rz) - y * math.sin(rz), x * math.sin(rz) + y * math.cos(rz)
        v.co += Vector(c)
    return r["verts"]


def cyl(bm, c, r1, r2, h, seg=16, axis="z"):
    r = bmesh.ops.create_cone(bm, cap_ends=True, cap_tris=False, segments=seg, radius1=r1, radius2=r2, depth=h)
    for v in r["verts"]:
        x, y, z = v.co
        if axis == "y":
            v.co = Vector((x, z, -y))
        elif axis == "x":
            v.co = Vector((z, y, -x))
        v.co += Vector(c)
    return r["verts"]


def sphere(bm, c, r, s=(1, 1, 1), sub=2):
    res = bmesh.ops.create_icosphere(bm, subdivisions=sub, radius=r)
    for v in res["verts"]:
        v.co = Vector((v.co.x * s[0], v.co.y * s[1], v.co.z * s[2])) + Vector(c)
    return res["verts"]


# ------------------------------------------------------------- stone
def rock(name, seed, s=(1, 0.8, 0.9), rough=0.35):
    bm = bmesh.new()
    vs = sphere(bm, (0, 0, 0), 1.0, s, sub=2)
    off = Vector((seed * 3.1, seed * 1.7, seed * 2.3))
    for v in vs:
        d = noise.noise(v.co * 1.3 + off)
        v.co *= 1 + rough * d
    # flatten one face so it can sit on the ground, cleave another
    for v in vs:
        if v.co.z < -0.55 * s[2]:
            v.co.z = -0.55 * s[2] + (v.co.z + 0.55 * s[2]) * 0.15
        if v.co.x > 0.6 * s[0]:
            v.co.x = 0.6 * s[0] + (v.co.x - 0.6 * s[0]) * 0.3
    ob = new_ob(name, bm)
    return finish(ob, uv_box, smooth=False, scale=0.6)


def crater_rim():
    """Ring of uplifted, cracked ground slabs tilted outward around a bowl."""
    bm = bmesh.new()
    rnd = random.Random(7)
    n = 16
    for i in range(n):
        a = 2 * math.pi * (i + rnd.uniform(-0.2, 0.2)) / n
        w = rnd.uniform(0.32, 0.45)
        L = rnd.uniform(0.35, 0.55)
        vs = box(bm, (0, 0, 0), (L, w, rnd.uniform(0.08, 0.14)))
        tilt = math.radians(rnd.uniform(28, 55))
        for v in vs:
            x, y, z = v.co
            x, z = x * math.cos(tilt) - z * math.sin(tilt), x * math.sin(tilt) + z * math.cos(tilt)
            r0 = 1.0 + rnd.uniform(-0.05, 0.08)
            x += r0
            z += L * 0.25 * math.sin(tilt)
            v.co = Vector((x * math.cos(a) - y * math.sin(a), x * math.sin(a) + y * math.cos(a), z))
    # bowl lip: a shallow cone just inside the slabs
    vs = cyl(bm, (0, 0, -0.05), 1.05, 0.55, 0.1, seg=24)
    ob = new_ob("crater_rim", bm)
    return finish(ob, uv_box, smooth=False, scale=0.8)


def rock_spire():
    bm = bmesh.new()
    vs = cyl(bm, (0, 0, 0.5), 0.32, 0.02, 1.0, seg=7)
    for v in vs:
        f = v.co.z
        v.co.x += noise.noise(v.co * 4) * 0.06 * (1 - f)
        v.co.y += noise.noise(v.co * 4 + Vector((5, 5, 5))) * 0.06 * (1 - f)
    # two side shards
    for k, (dx, dy, h) in enumerate(((0.22, 0.05, 0.55), (-0.18, -0.15, 0.42))):
        vs2 = cyl(bm, (dx, dy, h * 0.5), 0.14, 0.01, h, seg=5)
        for v in vs2:
            v.co.x += (v.co.z) * dx * 0.6
            v.co.y += (v.co.z) * dy * 0.6
    ob = new_ob("rock_spire", bm)
    return finish(ob, uv_box, smooth=False, scale=1.2)


def rock_fist():
    """A titan's stone fist and forearm rising out of the ground (fist up)."""
    parts = []
    bm = bmesh.new()
    vs = cyl(bm, (0, 0, 0.55), 0.42, 0.34, 1.1, seg=9)                 # forearm
    for v in vs:
        v.co += Vector((noise.noise(v.co * 3) * 0.05, noise.noise(v.co * 3 + Vector((3, 1, 2))) * 0.05, 0))
    box(bm, (0, 0, 1.32), (0.62, 0.5, 0.5))                             # fist block
    for i in range(4):                                                  # knuckles
        box(bm, (-0.22 + i * 0.147, -0.02, 1.62), (0.13, 0.4, 0.16))
    box(bm, (0.36, -0.12, 1.3), (0.16, 0.2, 0.36))                      # thumb
    for i in range(5):                                                  # cracked plates on the forearm
        a = i * 1.3
        box(bm, (math.cos(a) * 0.4, math.sin(a) * 0.4, 0.3 + i * 0.15), (0.12, 0.2, 0.22), rz=a)
    ob = new_ob("rock_fist", bm)
    return finish(ob, uv_box, smooth=False, scale=1.0)


# ------------------------------------------------------------- ice
def ice_cluster():
    bm = bmesh.new()
    rnd = random.Random(3)
    for k in range(7):
        h = rnd.uniform(0.5, 1.0) if k else 1.0
        tilt = 0 if k == 0 else rnd.uniform(0.3, 0.7)
        a = rnd.uniform(0, 2 * math.pi)
        r = rnd.uniform(0.08, 0.14) if k else 0.17
        vs = cyl(bm, (0, 0, h / 2), r, 0.0, h, seg=6)
        for v in vs:
            x, y, z = v.co
            x2 = x + z * math.sin(tilt) * math.cos(a)
            y2 = y + z * math.sin(tilt) * math.sin(a)
            v.co = Vector((x2, y2, z * math.cos(tilt)))
    ob = new_ob("ice_cluster", bm)
    return finish(ob, uv_box, smooth=False, scale=1.5)


def ice_block():
    bm = bmesh.new()
    vs = box(bm, (0, 0, 0.5), (1.0, 0.8, 1.0))
    for v in vs:
        v.co += Vector((noise.noise(v.co * 2) * 0.12, noise.noise(v.co * 2 + Vector((4, 4, 4))) * 0.12, noise.noise(v.co * 2 + Vector((8, 1, 3))) * 0.06))
    bmesh.ops.bevel(bm, geom=list(bm.edges), offset=0.08, segments=1, affect="EDGES")
    for (dx, dy, h) in ((0.45, 0.3, 0.6), (-0.4, -0.3, 0.5), (0.1, 0.4, 0.45)):
        cyl(bm, (dx, dy, 1.0 + h / 2 - 0.1), 0.12, 0.0, h, seg=6)
    ob = new_ob("ice_block", bm)
    return finish(ob, uv_box, smooth=False, scale=1.0)


# ------------------------------------------------------------- weapons
def blade_profile(bm, length, w_base, w_tip, thick, curve=0.0, notch=False, tip=0.12, seg=24, z0=0.0):
    """Lens-section blade from z0 down to z0-length; edge at -x, spine at +x.
    curve bends the blade toward +x (katana sori)."""
    rows = []
    for j in range(seg + 1):
        f = j / seg
        z = z0 - f * length
        w = w_base + (w_tip - w_base) * f
        if f > 1 - tip:
            g = min(1.0, (f - (1 - tip)) / tip)
            w *= max(0.0, 1 - g) ** 0.7 if not notch else 1.0
        bend = curve * math.sin(f * math.pi * 0.5) ** 2
        sp = max(w, 0.004)
        edge = Vector((-sp / 2 + bend, 0, z))
        spine = Vector((sp / 2 + bend, 0, z))
        if notch and f > 1 - tip:
            g = (f - (1 - tip)) / tip
            spine.x -= sp * 0.55 * g                      # cut-in at the spine near the tip
        mid_t = thick * (1 - 0.6 * f) * 0.5
        mx = (edge.x + spine.x) / 2
        rows.append([bm.verts.new(edge), bm.verts.new(Vector((mx, mid_t, z))), bm.verts.new(spine), bm.verts.new(Vector((mx, -mid_t, z)))])
    for j in range(seg):
        a, b = rows[j], rows[j + 1]
        for i in range(4):
            bm.faces.new((a[i], a[(i + 1) % 4], b[(i + 1) % 4], b[i]))
    bm.faces.new(rows[0][::-1])
    bm.faces.new(rows[-1])


def katana(name, length=3.6, curve=0.18):
    bm = bmesh.new()
    blade_profile(bm, length, 0.2, 0.17, 0.07, curve=curve, tip=0.1, z0=0.0)
    cyl(bm, (0, 0, 0.03), 0.26, 0.26, 0.06, seg=20)                    # tsuba
    cyl(bm, (0, 0, 0.1), 0.11, 0.11, 0.08, seg=10)                     # habaki/collar
    cyl(bm, (0, 0, 0.62), 0.085, 0.09, 1.0, seg=10)                    # tsuka (grip)
    for i in range(7):                                                 # ito wrap diamonds
        box(bm, (0, 0, 0.2 + i * 0.13), (0.2, 0.2, 0.04), rz=math.radians(45 if i % 2 else -45))
    cyl(bm, (0, 0, 1.14), 0.1, 0.1, 0.05, seg=10)                      # kashira
    ob = new_ob(name, bm)
    return finish(ob, uv_blade, smooth=False)


def asta_sword():
    """Broad, flat, slab-like greatsword: wide rectangular blade, chipped tip
    notch, plain guard, long wrapped grip."""
    bm = bmesh.new()
    blade_profile(bm, 4.6, 0.62, 0.66, 0.1, notch=True, tip=0.14, z0=0.0)
    for i in range(3):                                                 # chips along the edge
        box(bm, (-0.33, 0, -1.2 - i * 1.1), (0.06, 0.11, 0.12))
    box(bm, (0, 0, 0.06), (0.86, 0.22, 0.12))                          # guard
    cyl(bm, (0, 0, 0.62), 0.1, 0.1, 1.0, seg=10)                       # grip
    for i in range(6):
        box(bm, (0, 0, 0.22 + i * 0.15), (0.24, 0.24, 0.05), rz=math.radians(45))
    sphere(bm, (0, 0, 1.17), 0.12, sub=1)                              # pommel
    ob = new_ob("sword_asta", bm)
    return finish(ob, uv_blade, smooth=False)


def light_sword():
    bm = bmesh.new()
    blade_profile(bm, 3.2, 0.32, 0.26, 0.08, tip=0.16, z0=0.0)
    box(bm, (0, 0, 0.06), (1.0, 0.16, 0.12))                           # crossguard
    for s in (-1, 1):
        sphere(bm, (s * 0.52, 0, 0.06), 0.09, sub=1)                    # guard finials
    cyl(bm, (0, 0, 0.42), 0.07, 0.08, 0.6, seg=10)                      # grip
    sphere(bm, (0, 0, 0.78), 0.11, sub=1)                               # pommel
    ob = new_ob("sword_light", bm)
    return finish(ob, uv_blade, smooth=False)


def spear():
    bm = bmesh.new()
    cyl(bm, (0, 0, 0.0), 0.05, 0.05, 4.0, seg=8)                       # shaft
    vs = cyl(bm, (0, 0, -2.35), 0.0, 0.16, 0.7, seg=4)                 # leaf head (pointing -z)
    cyl(bm, (0, 0, -1.98), 0.09, 0.09, 0.08, seg=8)
    cyl(bm, (0, 0, 2.05), 0.08, 0.04, 0.12, seg=8)
    ob = new_ob("spear", bm)
    return finish(ob, uv_blade, smooth=False)


def axe():
    bm = bmesh.new()
    cyl(bm, (0, 0, 0.0), 0.06, 0.06, 2.6, seg=8)                       # haft
    # crescent bit on one side near the top (the "business end" is -z: it flies head-first)
    rows = []
    for j in range(11):
        f = j / 10
        a = math.radians(-60 + 120 * f)
        r = 0.75
        rows.append((math.cos(a) * r - 0.1, math.sin(a) * r * 1.1 - 1.0))
    top = [bm.verts.new((-0.05, 0.03, -0.75)), bm.verts.new((-0.05, -0.03, -0.75))]
    prev = None
    for (x, z) in rows:
        a1, a2 = bm.verts.new((-x, 0.02, z)), bm.verts.new((-x, -0.02, z))
        if prev:
            bm.faces.new((prev[0], a1, a2, prev[1]))
            bm.faces.new((prev[0], top[0], a1))
            bm.faces.new((prev[1], a2, top[1]))
        prev = (a1, a2)
    ob = new_ob("axe", bm)
    return finish(ob, uv_blade, smooth=False)


def water_spear():
    """Riptide's lance: a long tapering spear of water with two ribbons
    spiralling round it and a barbed head (pointing -z)."""
    bm = bmesh.new()
    cyl(bm, (0, 0, 0.6), 0.12, 0.2, 4.0, seg=12)                       # shaft thickening to the rear
    cyl(bm, (0, 0, -1.75), 0.0, 0.24, 0.9, seg=8)                      # head
    for s in (-1, 1):
        box(bm, (s * 0.2, 0, -1.25), (0.12, 0.06, 0.4), rz=0)           # barbs
    for k in range(2):
        prev = None
        for j in range(60):
            f = j / 59
            a = f * 6 * math.pi + k * math.pi
            r = 0.3 - 0.1 * f
            z = 2.4 - f * 3.8
            c = Vector((math.cos(a) * r, math.sin(a) * r, z))
            v1 = bm.verts.new(c + Vector((0, 0, 0.09)))
            v2 = bm.verts.new(c - Vector((0, 0, 0.09)))
            if prev:
                bm.faces.new((prev[0], v1, v2, prev[1]))
            prev = (v1, v2)
    ob = new_ob("water_spear", bm)
    return finish(ob, uv_along, smooth=True)


def wave_blade():
    """A THICK crescent wave (lens cross-section, tapered horns) in the XY
    plane bulging +Y (forward): Black Divider / Getsuga waves."""
    bm = bmesh.new()
    span, nu, nv = math.radians(150), 48, 8
    rows = []
    for i in range(nu + 1):
        u = i / nu
        a = -span / 2 + span * u
        taper = math.sin(math.pi * u) ** 0.7
        w = 0.42 * taper + 0.01
        th = 0.16 * taper + 0.005
        ring = []
        for j in range(nv):
            b = 2 * math.pi * j / nv
            rr = 1.0 - w / 2 + (w / 2) * math.cos(b)
            ring.append(bm.verts.new((math.sin(a) * rr, math.cos(a) * rr, math.sin(b) * th)))
        rows.append(ring)
    for i in range(nu):
        for j in range(nv):
            bm.faces.new((rows[i][j], rows[i][(j + 1) % nv], rows[i + 1][(j + 1) % nv], rows[i + 1][j]))
    ob = new_ob("wave_blade", bm)
    finish(ob, uv_along, smooth=True, axis="x")
    return ob


# ------------------------------------------------------------- book
def book_parts():
    """Grimoire: cover board (used for back and front), page block, single
    page, spine. Book stands upright: spine along Z at x=0, pages extend +X,
    the reader looks from -Y. Covers swing about the spine (local x=-w/2)."""
    out = []
    bm = bmesh.new()
    box(bm, (0, 0, 0), (1.0, 0.07, 1.4))
    for sx in (-1, 1):                                                  # metal corner caps
        for sz in (-1, 1):
            box(bm, (sx * 0.43, 0, sz * 0.63), (0.16, 0.09, 0.16))
    sphere(bm, (0.08, -0.04, 0), 0.16, (1, 0.35, 1), sub=2)             # raised emblem
    out.append(finish(new_ob("book_cover", bm), uv_blade, smooth=False))
    bm = bmesh.new()
    box(bm, (0, 0, 0), (0.94, 0.22, 1.32))
    out.append(finish(new_ob("book_pages", bm), uv_blade, smooth=False))
    bm = bmesh.new()
    box(bm, (0, 0, 0), (0.92, 0.012, 1.3))
    out.append(finish(new_ob("book_page", bm), uv_blade, smooth=False))
    bm = bmesh.new()
    vs = cyl(bm, (0, 0, 0), 0.19, 0.19, 1.42, seg=12)
    out.append(finish(new_ob("book_spine", bm), uv_along, smooth=True))
    return out


# ------------------------------------------------------------- flora
def petal_ring(bm, n, r, cup, z, length=0.45, width=0.22):
    for i in range(n):
        a = 2 * math.pi * i / n
        rows = []
        for j in range(6):
            f = j / 5
            ww = width * math.sin(math.pi * min(1, f * 1.1 + 0.05)) ** 0.8
            d = r + f * length
            h = z + cup * f * f
            rows.append([bm.verts.new(Vector((math.cos(a) * d - math.sin(a) * (s * ww / 2), math.sin(a) * d + math.cos(a) * (s * ww / 2), h + abs(s) * 0.0)))
                         for s in (-1, 0, 1)])
        for j in range(5):
            for k in range(2):
                bm.faces.new((rows[j][k], rows[j][k + 1], rows[j + 1][k + 1], rows[j + 1][k]))


def flowers():
    """Three bloom stages (bud / half / open) so a flower opens by mesh swap,
    plus a stem with two leaves."""
    out = []
    for name, cup, length, rad in (("flower_bud", 0.9, 0.3, 0.02), ("flower_half", 0.45, 0.42, 0.04), ("flower_open", 0.08, 0.5, 0.06)):
        bm = bmesh.new()
        petal_ring(bm, 5, rad, cup, 0.0, length=length, width=0.3)
        if name != "flower_bud":
            petal_ring(bm, 5, rad * 0.6, cup * 1.3, 0.02, length=length * 0.7, width=0.22)
        sphere(bm, (0, 0, 0.04), 0.09, sub=1)
        out.append(finish(new_ob(name, bm), uv_along, smooth=True))
    bm = bmesh.new()
    cyl(bm, (0, 0, 0.5), 0.025, 0.02, 1.0, seg=6)
    for s, h in ((1, 0.35), (-1, 0.55)):
        rows = []
        for j in range(6):
            f = j / 5
            w = 0.14 * math.sin(math.pi * f)
            rows.append([bm.verts.new((s * f * 0.45, sv * w, h + f * 0.15 - f * f * 0.12)) for sv in (-1, 1)])
        for j in range(5):
            bm.faces.new((rows[j][0], rows[j][1], rows[j + 1][1], rows[j + 1][0]))
    out.append(finish(new_ob("flower_stem", bm), uv_along, smooth=True))
    return out


# ------------------------------------------------------------- body parts
def fist_arm():
    """An R6 arm ending in a clenched fist, the arm axis along -Z (shoulder at
    the top): the afterimage piece of a punch barrage."""
    bm = bmesh.new()
    box(bm, (0, 0, -0.85), (0.92, 0.92, 1.7))                           # arm
    box(bm, (0, 0, -1.9), (1.0, 1.0, 0.45))                             # fist
    for i in range(4):
        box(bm, (-0.36 + i * 0.24, -0.3, -2.18), (0.2, 0.3, 0.14))      # knuckles
    box(bm, (0.5, -0.1, -1.8), (0.2, 0.35, 0.4))                        # thumb
    ob = new_ob("fist_arm", bm)
    return finish(ob, uv_box, smooth=False, scale=0.6)


# ------------------------------------------------------------- creatures and constructs
def chain_link():
    bm = bmesh.new()
    nu, nv, R, r = 24, 8, 0.32, 0.075
    rows = []
    for i in range(nu):
        a = 2 * math.pi * i / nu
        cx, cz = math.cos(a) * R * 0.75, math.sin(a) * R * 1.35          # oval link in the XZ plane
        tang = Vector((-math.sin(a) * 0.75, 0, math.cos(a) * 1.35)).normalized()
        nrm = Vector((math.cos(a) * 1.35, 0, math.sin(a) * 0.75)).normalized()
        ring = []
        for j in range(nv):
            b = 2 * math.pi * j / nv
            ring.append(bm.verts.new(Vector((cx, 0, cz)) + nrm * math.cos(b) * r + Vector((0, 1, 0)) * math.sin(b) * r))
        rows.append(ring)
    for i in range(nu):
        for j in range(nv):
            bm.faces.new((rows[i][j], rows[i][(j + 1) % nv], rows[(i + 1) % nu][(j + 1) % nv], rows[(i + 1) % nu][j]))
    ob = new_ob("chain_link", bm)
    return finish(ob, uv_along, smooth=True, axis="z")


def chain_spike():
    """The dagger weight on a chain's end, pointing -Y (forward along the chain)."""
    bm = bmesh.new()
    cyl(bm, (0, 0.1, 0), 0.16, 0.0, 0.8, seg=4, axis="y")
    cyl(bm, (0, -0.38, 0), 0.12, 0.12, 0.12, seg=10, axis="y")
    ob = new_ob("chain_spike", bm)
    return finish(ob, uv_along, smooth=False, axis="y")


def phoenix_parts():
    """Firebird: body (head/beak/crest at +Y forward), one wing (mirror for the
    other side by negative Size X is NOT allowed in Roblox, so both are built),
    and a fan of long tail plumes."""
    out = []

    def solid_uv(bm, vs_before):
        """Body solids (head, neck, beak, crest) sample the solid orange band of feather_blade."""
        layer = bm.loops.layers.uv.active or bm.loops.layers.uv.new("UVMap")
        for f in bm.faces:
            for loop in f.loops:
                if loop[layer].uv.length == 0:
                    loop[layer].uv = (0.5, 0.62)

    bm = bmesh.new()
    sphere(bm, (0, -0.1, 0), 0.42, (0.62, 1.25, 0.62), sub=3)           # torso (slimmer: the plumage adds bulk)
    sphere(bm, (0, 0.45, 0.12), 0.3, (0.75, 0.9, 0.8), sub=2)           # breast
    vs = cyl(bm, (0, 0.82, 0.38), 0.15, 0.11, 0.7, seg=10, axis="y")    # neck, rising forward
    for v in vs:
        v.co.z += (v.co.y - 0.82) * 0.55
    sphere(bm, (0, 1.22, 0.62), 0.22, (0.85, 1.15, 0.9), sub=2)         # head
    vs = cyl(bm, (0, 1.52, 0.58), 0.08, 0.0, 0.36, seg=6, axis="y")     # hooked beak
    for v in vs:
        v.co.z -= max(0.0, v.co.y - 1.5) * 0.45
    for s_ in (-1, 1):                                                  # eye ridges
        sphere(bm, (s_ * 0.13, 1.3, 0.7), 0.05, sub=1)
    for i in range(5):                                                  # crest plumes sweeping back off the head
        vs = cyl(bm, (0, 1.12 - i * 0.07, 0.8 + i * 0.03), 0.045, 0.0, 0.75 - i * 0.07, seg=4)
        for v in vs:
            v.co.y -= (v.co.z - (0.8 + i * 0.03)) * 1.1
    solid_uv(bm, None)
    # body plumage: rows of overlapping feather cards around the torso, sweeping
    # back (-Y). A bare ellipsoid read as a smooth orange EGG end-on in Studio
    # (round 5b); feathers give the body the same silhouette language as the wings.
    layer = bm.loops.layers.uv.active
    rx, ry, cy = 0.26, 0.525, -0.1
    rows = 6
    for r in range(rows):
        y = cy + ry * (0.75 - 1.5 * r / (rows - 1))
        rad = rx * max(0.25, (1 - ((y - cy) / ry) ** 2)) ** 0.5
        k = 9 - abs(r - 2)
        for j in range(k):
            a = 2 * math.pi * (j + 0.5 * (r % 2)) / k
            out_v = Vector((math.sin(a), 0, math.cos(a)))
            base = Vector((0, y, 0)) + out_v * rad * 0.92
            L = 0.42 + 0.06 * (rows - r)
            tip = base + Vector((0, -L, 0)) + out_v * 0.22 * L
            d = (tip - base).normalized()
            wv = d.cross(out_v).normalized() * 0.16
            q = [bm.verts.new(base + wv), bm.verts.new(base - wv), bm.verts.new(tip + wv * 0.7), bm.verts.new(tip - wv * 0.7)]
            fc = bm.faces.new((q[0], q[2], q[3], q[1]))
            for loop, uvv in zip(fc.loops, ((0, 0), (0, 1), (1, 1), (1, 0))):
                loop[layer].uv = uvv
    out.append(finish(new_ob("phoenix_body", bm), lambda ob, **k: None, smooth=True))
    def card_uv(bm, face, uvs):
        """Per-card UVs (U across the feather, V root 0 -> tip 1) so a feather
        texture draws ONE feather per card (Studio round 4: generic UVs merged
        the cards into a flat blob)."""
        layer = bm.loops.layers.uv.active or bm.loops.layers.uv.new("UVMap")
        for loop in face.loops:
            loop[layer].uv = uvs[loop.vert]

    no_uv = lambda ob, **k: None  # noqa: E731  (UVs already set per card)
    for side, nm in ((1, "phoenix_wing_r"), (-1, "phoenix_wing_l")):
        bm = bmesh.new()
        n = 9
        for i in range(n):                                              # primary feathers fanning out
            f = i / (n - 1)
            L = 1.2 + 1.3 * math.sin(math.pi * (0.25 + 0.6 * f))
            a = math.radians(-10 - 70 * f)
            base = Vector((side * (0.2 + 1.0 * f), 0.35 - 0.25 * f, 0))
            tip = base + Vector((side * math.cos(a) * 0.4 * L + side * 0.3 * L, math.sin(a) * L, 0.06 * L))
            w = 0.3 + 0.08 * (1 - f)
            side_v = Vector((0, 0, 1)).cross((tip - base).normalized()) * w
            q = [bm.verts.new(base + side_v), bm.verts.new(base - side_v), bm.verts.new(tip + side_v * 0.75), bm.verts.new(tip - side_v * 0.75)]
            fc = bm.faces.new((q[0], q[2], q[3], q[1]))
            card_uv(bm, fc, {q[0]: (0, 0), q[1]: (1, 0), q[2]: (0, 1), q[3]: (1, 1)})
        # coverts: a row of short feathers over the primaries' roots (a flat band read as a yellow strip in Studio)
        for i in range(7):
            f = i / 6
            L = 0.55 + 0.35 * math.sin(math.pi * (0.2 + 0.6 * f))
            a = math.radians(-25 - 50 * f)
            base = Vector((side * (0.08 + 1.15 * f), 0.42 - 0.12 * f, 0.03))
            tip = base + Vector((side * math.cos(a) * 0.35 * L + side * 0.2 * L, math.sin(a) * L, 0.05 * L))
            w = 0.24
            side_v = Vector((0, 0, 1)).cross((tip - base).normalized()) * w
            q = [bm.verts.new(base + side_v), bm.verts.new(base - side_v), bm.verts.new(tip + side_v * 0.75), bm.verts.new(tip - side_v * 0.75)]
            fc = bm.faces.new((q[0], q[2], q[3], q[1]))
            card_uv(bm, fc, {q[0]: (0, 0), q[1]: (1, 0), q[2]: (0, 1), q[3]: (1, 1)})
        out.append(finish(new_ob(nm, bm), no_uv, smooth=True))
    bm = bmesh.new()
    for i in range(7):
        a = math.radians(-36 + 12 * i)
        L = 2.2 + (0.8 if i == 3 else 0.3 * math.cos(a * 3))
        base = Vector((0, -0.4, 0))
        tip = base + Vector((math.sin(a) * L * 0.6, -L, -0.15 * L))
        side_v = Vector((math.cos(a), math.sin(a) * 0.2, 0)) * 0.13
        q = [bm.verts.new(base + side_v * 0.4), bm.verts.new(base - side_v * 0.4), bm.verts.new(tip + side_v), bm.verts.new(tip - side_v)]
        mid = [bm.verts.new((base + tip) / 2 + side_v * 1.6), bm.verts.new((base + tip) / 2 - side_v * 1.6)]
        f1 = bm.faces.new((q[0], mid[0], mid[1], q[1]))
        f2 = bm.faces.new((mid[0], q[2], q[3], mid[1]))
        uvs = {q[0]: (0, 0), q[1]: (1, 0), mid[0]: (0, 0.5), mid[1]: (1, 0.5), q[2]: (0, 1), q[3]: (1, 1)}
        card_uv(bm, f1, uvs)
        card_uv(bm, f2, uvs)
    out.append(finish(new_ob("phoenix_tail", bm), no_uv, smooth=True))
    return out


def portal_ring():
    """Golden gate ring: an outer band with teeth and an inner ripple disc."""
    bm = bmesh.new()
    nu, R, w = 48, 1.0, 0.1
    for k, (rr, th) in enumerate(((R, 0.06), (R * 0.78, 0.03))):
        rows = []
        for i in range(nu):
            a = 2 * math.pi * i / nu
            rows.append([bm.verts.new((math.cos(a) * (rr + dw), th * s, math.sin(a) * (rr + dw))) for dw in (-w / 2, w / 2) for s in (-1, 1)])
        for i in range(nu):
            a, b = rows[i], rows[(i + 1) % nu]
            for (p, q) in ((0, 2), (2, 3), (3, 1), (1, 0)):
                bm.faces.new((a[p], a[q], b[q], b[p]))
    for i in range(12):
        a = 2 * math.pi * i / 12
        box(bm, (math.cos(a) * 1.12, 0, math.sin(a) * 1.12), (0.08, 0.06, 0.2), rz=0)
    ob = new_ob("portal_ring", bm)
    return finish(ob, uv_along, smooth=False, axis="y")


def main():
    reset()
    for i, s in enumerate(((1, 0.8, 0.9), (1.2, 0.7, 0.6), (0.8, 0.9, 1.1), (1.3, 1.0, 0.5), (0.9, 0.6, 0.8))):
        export(rock(f"rock_{i}", i + 1, s))
    for fn in (crater_rim, rock_spire, rock_fist, ice_cluster, ice_block, asta_sword, light_sword, spear, axe, water_spear,
               wave_blade, fist_arm, chain_link, chain_spike, portal_ring):
        export(fn())
    export(katana("katana"))
    for ob in book_parts() + flowers() + phoenix_parts():
        bpy.ops.object.select_all(action="DESELECT")
        # finish() may leave several objects in the scene; export one at a time
    for nm in [o.name for o in bpy.data.objects]:
        ob = bpy.data.objects.get(nm)
        if ob:
            others = [o for o in bpy.data.objects if o != ob]
            path = os.path.join(OUT, ob.name + ".obj")
            activate(ob)
            bpy.ops.wm.obj_export(filepath=path, export_selected_objects=True, export_uv=True, export_normals=True,
                                  export_materials=False, forward_axis="NEGATIVE_Z", up_axis="Y")
            cs = [v.co for v in ob.data.vertices]
            mn = Vector((min(c.x for c in cs), min(c.y for c in cs), min(c.z for c in cs)))
            mx = Vector((max(c.x for c in cs), max(c.y for c in cs), max(c.z for c in cs)))
            sz, c = mx - mn, (mn + mx) / 2
            MANIFEST[ob.name] = {"size": [round(sz.x, 4), round(sz.z, 4), round(sz.y, 4)], "centre": [round(c.x, 4), round(c.z, 4), round(-c.y, 4)],
                                 "tris": sum(len(p.vertices) - 2 for p in ob.data.polygons)}
            print(f"MESH {ob.name}: {MANIFEST[ob.name]}")
    man = os.path.join(OUT, "props.json")
    old = json.load(open(man)) if os.path.exists(man) else {}
    old.update(MANIFEST)
    json.dump(old, open(man, "w"), indent=1)


main()
