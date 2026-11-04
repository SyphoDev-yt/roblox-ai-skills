"""Eastern water dragon meshes for spell effects (Sea Dragon's Roar), built in
Blender and exported as OBJ for the sim and for upload to Roblox.

    "C:/Program Files/Blender Foundation/Blender 4.3/blender.exe" -b -P make_dragon.py

Built in Blender axes: +Y is the dragon's forward (Roblox -Z after export),
+Z up (Roblox +Y). Meshes:
  dragon_head   cranium, long snout, carved mouth roof, brow ridges, nostrils,
                cheek frills, swept horns, mane spikes, whiskers, upper teeth
  dragon_jaw    lower jaw with teeth and chin barbels; its hinge is the BACK-TOP
                edge of its bounding box (see HINGE printout)
  dragon_seg    one body section: tapered tube + dorsal fin + side frills,
                overlaps the next section so a chain reads as one body
  dragon_tail   tapering tail with a forked fan fin
UVs: U around the body, V along it (0 = back, 1 = front), so a water texture
with streaks along V reads as water flowing back over the dragon.
Prints each mesh's bounding-box size: use it as the MeshPart Size ratio.
"""
import math
import os

import bmesh
import bpy
from mathutils import Vector

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "meshes")


def reset():
    bpy.ops.wm.read_factory_settings(use_empty=True)


def activate(ob):
    bpy.ops.object.select_all(action="DESELECT")
    ob.select_set(True)
    bpy.context.view_layer.objects.active = ob


def metaball(name, elems, res=0.03, thresh=0.25):
    mb = bpy.data.metaballs.new(name)
    mb.resolution = res
    mb.render_resolution = res
    mb.threshold = thresh
    ob = bpy.data.objects.new(name, mb)
    bpy.context.collection.objects.link(ob)
    for e in elems:
        el = mb.elements.new(type=e.get("type", "ELLIPSOID"))
        el.co = Vector(e["co"])
        el.radius = e["r"]
        s = e.get("s", (1, 1, 1))
        el.size_x, el.size_y, el.size_z = s
        el.use_negative = e.get("neg", False)
        el.stiffness = e.get("stiff", 2.0)
        if "rot" in e:
            from mathutils import Euler
            el.rotation = Euler([math.radians(a) for a in e["rot"]]).to_quaternion()
    activate(ob)
    bpy.ops.object.convert(target="MESH")
    return bpy.context.view_layer.objects.active


def tube_curve(name, pts, radius, taper_end=0.05, res=10):
    """A tapered tube along a poly-bezier through pts (horns, whiskers)."""
    cu = bpy.data.curves.new(name, "CURVE")
    cu.dimensions = "3D"
    cu.bevel_depth = radius
    cu.bevel_resolution = 3
    cu.resolution_u = res
    sp = cu.splines.new("NURBS")
    sp.points.add(len(pts) - 1)
    for i, p in enumerate(pts):
        sp.points[i].co = (p[0], p[1], p[2], 1)
        sp.points[i].radius = 1.0 + (taper_end - 1.0) * (i / (len(pts) - 1)) ** 0.8
    sp.use_endpoint_u = True
    sp.order_u = 3
    cu.use_fill_caps = True
    ob = bpy.data.objects.new(name, cu)
    bpy.context.collection.objects.link(ob)
    activate(ob)
    bpy.ops.object.convert(target="MESH")
    return bpy.context.view_layer.objects.active


def spike(name, base, tip, w, flat=0.35):
    """A flattened cone (fin spike / tooth) from base to tip."""
    bm = bmesh.new()
    seg = 6
    b, t = Vector(base), Vector(tip)
    axis = (t - b).normalized()
    side = axis.cross(Vector((0, 0, 1)))
    if side.length < 1e-3:
        side = axis.cross(Vector((0, 1, 0)))
    side.normalize()
    up = side.cross(axis).normalized()
    ring = []
    for k in range(seg):
        a = 2 * math.pi * k / seg
        ring.append(bm.verts.new(b + side * math.cos(a) * w + up * math.sin(a) * w * flat))
    apex = bm.verts.new(t)
    cap = bm.verts.new(b)
    for k in range(seg):
        bm.faces.new((ring[k], ring[(k + 1) % seg], apex))
        bm.faces.new((ring[(k + 1) % seg], ring[k], cap))
    me = bpy.data.meshes.new(name)
    bm.to_mesh(me)
    bm.free()
    ob = bpy.data.objects.new(name, me)
    bpy.context.collection.objects.link(ob)
    return ob


def fin_sheet(name, pts_root, pts_tip, thick=0.02):
    """A thin fin: a quad strip between a root line and a tip line, given a
    little thickness so it renders from both sides with a solid edge."""
    bm = bmesh.new()
    n = len(pts_root)
    A = [bm.verts.new(Vector(p) + Vector((thick, 0, 0))) for p in pts_root]
    B = [bm.verts.new(Vector(p) + Vector((thick * 0.3, 0, 0))) for p in pts_tip]
    C = [bm.verts.new(Vector(p) - Vector((thick * 0.3, 0, 0))) for p in pts_tip]
    D = [bm.verts.new(Vector(p) - Vector((thick, 0, 0))) for p in pts_root]
    for i in range(n - 1):
        bm.faces.new((A[i], A[i + 1], B[i + 1], B[i]))
        bm.faces.new((C[i], C[i + 1], D[i + 1], D[i]))
        bm.faces.new((B[i], B[i + 1], C[i + 1], C[i]))
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
    bpy.ops.object.join()
    ob = bpy.context.view_layer.objects.active
    ob.name = name
    ob.data.name = name
    return ob


def uv_along(ob):
    """U = angle around the forward (Y) axis, V = position along Y."""
    me = ob.data
    ys = [v.co.y for v in me.vertices]
    y0, y1 = min(ys), max(ys)
    # joined curve parts bring their own UV layer: drop every old layer so
    # ours is the only (and active) one, or the OBJ exports the junk layer
    while me.uv_layers:
        me.uv_layers.remove(me.uv_layers[0])
    uv = me.uv_layers.new(name="UVMap")
    me.uv_layers.active = uv
    for poly in me.polygons:
        us = []
        for li in poly.loop_indices:
            co = me.vertices[me.loops[li].vertex_index].co
            u = (math.atan2(co.x, co.z) / (2 * math.pi)) + 0.5
            us.append(u)
        # keep a face from wrapping across the seam
        if max(us) - min(us) > 0.5:
            us = [u + 1 if u < 0.5 else u for u in us]
        for li, u in zip(poly.loop_indices, us):
            co = me.vertices[me.loops[li].vertex_index].co
            uv.data[li].uv = (u, (co.y - y0) / max(y1 - y0, 1e-6))


def finish(ob, decimate=None):
    activate(ob)
    bpy.ops.object.transform_apply(location=False, rotation=True, scale=True)
    if decimate:
        m = ob.modifiers.new("dec", "DECIMATE")
        m.ratio = decimate
        bpy.ops.object.modifier_apply(modifier="dec")
    bpy.ops.object.mode_set(mode="EDIT")
    bpy.ops.mesh.select_all(action="SELECT")
    bpy.ops.mesh.remove_doubles(threshold=0.002)
    bpy.ops.mesh.normals_make_consistent(inside=False)
    bpy.ops.object.mode_set(mode="OBJECT")
    bpy.ops.object.shade_smooth()
    uv_along(ob)


def export(ob):
    activate(ob)
    path = os.path.join(OUT, ob.name + ".obj")
    bpy.ops.wm.obj_export(filepath=path, export_selected_objects=True, export_uv=True, export_normals=True,
                          export_materials=False, forward_axis="NEGATIVE_Z", up_axis="Y")
    xs = [v.co for v in ob.data.vertices]
    mn = Vector((min(c.x for c in xs), min(c.y for c in xs), min(c.z for c in xs)))
    mx = Vector((max(c.x for c in xs), max(c.y for c in xs), max(c.z for c in xs)))
    size = mx - mn
    tris = sum(len(p.vertices) - 2 for p in ob.data.polygons)
    # Roblox Size = (x, z_blender, y_blender); centre offset in Roblox axes
    c = (mn + mx) / 2
    print(f"MESH {ob.name}: {tris} tris  roblox_size=({size.x:.3f}, {size.z:.3f}, {size.y:.3f})  "
          f"centre_roblox=({c.x:.3f}, {c.z:.3f}, {-c.y:.3f})")
    return mn, mx


# ------------------------------------------------------------------ head
def head():
    E = []
    # cranium and snout (forward = +Y)
    E += [{"co": (0, -0.05, 0.25), "r": 0.62, "s": (0.95, 1.15, 0.8)},
          {"co": (0, 0.55, 0.2), "r": 0.42, "s": (0.95, 1.2, 0.75)},
          {"co": (0, 0.95, 0.14), "r": 0.36, "s": (0.95, 1.2, 0.7)},
          {"co": (0, 1.32, 0.1), "r": 0.3, "s": (1.0, 1.1, 0.7)},
          {"co": (0, 1.62, 0.12), "r": 0.25, "s": (1.15, 0.9, 0.75)},
          {"type": "CAPSULE", "co": (0, 0.95, 0.12), "r": 0.27, "s": (0.75, 1, 1), "rot": (0, 0, 90)}]
    # nostril bulbs, brow ridges, cheek bones, back of skull
    E += [{"co": (s * 0.13, 1.66, 0.26), "r": 0.11} for s in (-1, 1)]
    E += [{"co": (s * 0.27, 0.42, 0.48), "r": 0.2, "s": (1, 1.6, 0.7)} for s in (-1, 1)]
    E += [{"co": (s * 0.38, 0.1, 0.02), "r": 0.26, "s": (0.9, 1.3, 0.8)} for s in (-1, 1)]
    E += [{"co": (0, -0.55, 0.3), "r": 0.42, "s": (0.9, 1.1, 0.9)}]
    # carve the mouth roof under the snout and the eye sockets
    E += [{"co": (0, 1.0, -0.2), "r": 0.42, "s": (0.75, 1.9, 0.45), "neg": True}]
    E += [{"co": (s * 0.32, 0.35, 0.33), "r": 0.1, "neg": True} for s in (-1, 1)]
    E += [{"co": (s * 0.3, 0.36, 0.32), "r": 0.11, "stiff": 4.0} for s in (-1, 1)]
    skull = metaball("skull", E)
    parts = [skull]
    # horns: two long swept antler-horns with a short tine each
    for s in (-1, 1):
        parts.append(tube_curve(f"horn{s}", [(s * 0.22, -0.05, 0.62), (s * 0.35, -0.55, 0.95), (s * 0.48, -1.15, 1.12), (s * 0.55, -1.75, 1.0)], 0.1, 0.05))
        parts.append(tube_curve(f"tine{s}", [(s * 0.37, -0.65, 0.98), (s * 0.55, -0.7, 1.3), (s * 0.62, -0.85, 1.45)], 0.05, 0.08))
    # mane: a crest of spikes down the back of the head and swept frills on the cheeks
    for i in range(6):
        y = -0.35 - i * 0.22
        h = 0.55 - i * 0.05
        parts.append(spike(f"mane{i}", (0, y, 0.55 - i * 0.03), (0, y - 0.45, 0.55 + h), 0.12, flat=0.3))
    for s in (-1, 1):
        for i in range(4):
            parts.append(spike(f"frill{s}{i}", (s * 0.45, 0.05 - i * 0.15, 0.1 - i * 0.05), (s * (0.95 + i * 0.08), -0.55 - i * 0.2, 0.25 - i * 0.15), 0.1, flat=0.25))
    # whiskers: long waving barbels from the snout tip
    for s in (-1, 1):
        parts.append(tube_curve(f"whisk{s}", [(s * 0.22, 1.5, 0.02), (s * 0.6, 1.3, -0.12), (s * 0.95, 0.7, 0.05), (s * 1.25, 0.05, -0.25), (s * 1.4, -0.7, -0.05)], 0.045, 0.1, res=14))
    # upper teeth: fangs at the front, smaller teeth behind
    for s in (-1, 1):
        for i, y in enumerate((1.58, 1.4, 1.22, 1.04, 0.86, 0.68)):
            L = 0.24 if i == 0 else 0.12
            parts.append(spike(f"ut{s}{i}", (s * (0.2 - i * 0.004), y, -0.04), (s * (0.19 - i * 0.004), y - 0.03, -0.04 - L), 0.045, flat=1.0))
    ob = join("dragon_head", parts)
    finish(ob, decimate=0.55)
    return ob


def jaw():
    # closely spaced ellipsoids (0.12 apart) taper from a wide hinge to a narrow
    # chin, so they merge into one smooth jaw instead of a row of beads
    E = []
    n = 13
    for i in range(n):
        f = i / (n - 1)
        y = 0.05 + f * 1.55
        r = 0.3 - 0.15 * f
        E.append({"co": (0, y, -0.2 - 0.06 * math.sin(f * math.pi)), "r": r, "s": (1.25 - 0.35 * f, 0.9, 0.55), "stiff": 2.5})
    E.append({"co": (0, 0.85, -0.08), "r": 0.24, "s": (0.6, 2.6, 0.3), "neg": True})   # mouth floor
    parts = [metaball("jawbone", E)]
    parts.append(metaball("tongue", [{"type": "CAPSULE", "co": (0, 0.75, -0.14), "r": 0.12, "s": (0.55, 1, 1), "rot": (0, 0, 90)},
                                     {"co": (-0.07, 1.32, -0.12), "r": 0.08}, {"co": (0.07, 1.32, -0.12), "r": 0.08}]))
    for s in (-1, 1):
        for i, y in enumerate((1.5, 1.32, 1.14, 0.96, 0.78)):
            L = 0.2 if i == 0 else 0.1
            parts.append(spike(f"lt{s}{i}", (s * 0.16, y, -0.12), (s * 0.15, y + 0.02, -0.12 + L), 0.04, flat=1.0))
    for i, (x, y) in enumerate(((0, 1.2), (-0.12, 0.95), (0.12, 0.95))):
        parts.append(tube_curve(f"barbel{i}", [(x, y, -0.38), (x * 1.5, y - 0.3, -0.75), (x * 2, y - 0.75, -0.88)], 0.04, 0.1))
    ob = join("dragon_jaw", parts)
    finish(ob, decimate=0.6)
    return ob


# ------------------------------------------------------------------ body
def segment(name="dragon_seg", L=1.5, r0=0.5, r1=0.45):
    """Tube along +Y from y=0 (back, radius r1) to y=L (front, radius r0),
    slightly flattened belly, plus a dorsal fin and two side frills."""
    bm = bmesh.new()
    nu, nv = 24, 8
    rows = []
    for j in range(nv + 1):
        v = j / nv
        y = v * L
        r = r1 + (r0 - r1) * v
        row = []
        for i in range(nu):
            a = 2 * math.pi * i / nu
            x, z = math.sin(a) * r * 1.05, math.cos(a) * r * (0.92 if math.cos(a) < 0 else 1.0)
            row.append(bm.verts.new((x, y, z)))
        rows.append(row)
    for j in range(nv):
        for i in range(nu):
            bm.faces.new((rows[j][i], rows[j][(i + 1) % nu], rows[j + 1][(i + 1) % nu], rows[j + 1][i]))
    me = bpy.data.meshes.new(name + "_tube")
    bm.to_mesh(me)
    bm.free()
    tube = bpy.data.objects.new(name + "_tube", me)
    bpy.context.collection.objects.link(tube)
    # dorsal fin: root along the spine, tip swept back with a wavy edge
    n = 7
    root = [(0, 0.1 + i * (L - 0.3) / (n - 1), r0 * 0.92) for i in range(n)]
    tip = []
    for i in range(n):
        f = i / (n - 1)
        hgt = (0.14 + 0.3 * math.sin(math.pi * (0.15 + 0.85 * f)) ** 1.2) * (1 + 0.15 * math.sin(f * 9))
        tip.append((0, root[i][1] - 0.35, r0 * 0.92 + hgt))
    parts = [tube, fin_sheet(name + "_fin", root, tip, 0.025)]
    # side frills: short swept fins low on each flank
    for s in (-1, 1):
        rr = [(s * r0 * 0.95, 0.4 + i * 0.25, -0.1) for i in range(4)]
        tt = [(s * (r0 * 0.95 + 0.35 - 0.05 * i), 0.05 + i * 0.25, -0.3) for i in range(4)]
        ob = fin_sheet(name + f"_side{s}", rr, tt, 0.02)
        parts.append(ob)
    ob = join(name, parts)
    finish(ob)
    return ob


def tail():
    bm = bmesh.new()
    nu, nv, L = 20, 10, 2.2
    rows = []
    for j in range(nv + 1):
        v = j / nv
        r = 0.04 + 0.4 * v ** 0.9
        row = [bm.verts.new((math.sin(2 * math.pi * i / nu) * r, v * L, math.cos(2 * math.pi * i / nu) * r)) for i in range(nu)]
        rows.append(row)
    for j in range(nv):
        for i in range(nu):
            bm.faces.new((rows[j][i], rows[j][(i + 1) % nu], rows[j + 1][(i + 1) % nu], rows[j + 1][i]))
    me = bpy.data.meshes.new("tail_tube")
    bm.to_mesh(me)
    bm.free()
    tube = bpy.data.objects.new("tail_tube", me)
    bpy.context.collection.objects.link(tube)
    parts = [tube]
    # forked fan: two lobes, top and bottom, flaring back
    for sgn in (1, -1):
        root = [(0, 0.1 + i * 0.25, sgn * 0.1) for i in range(5)]
        tip = [(0, -0.9 + i * 0.32, sgn * (1.2 - i * 0.2)) for i in range(5)]
        parts.append(fin_sheet(f"lobe{sgn}", root, tip, 0.025))
    root = [(0, 0.3 + i * 0.35, 0.38) for i in range(5)]
    tip = [(0, 0.0 + i * 0.35, 0.75 - 0.05 * i) for i in range(5)]
    parts.append(fin_sheet("tailfin", root, tip, 0.02))
    ob = join("dragon_tail", parts)
    finish(ob)
    return ob


def main():
    reset()
    for fn in (head, jaw, segment, tail):
        ob = fn()
        export(ob)
        bpy.ops.object.select_all(action="SELECT")
        bpy.ops.object.delete()


main()
