"""VFX meshes built in Blender, exported as OBJ for the sim AND for upload to
Roblox (same file, so what you previewed is what ships).

    "C:/Program Files/Blender Foundation/Blender 4.3/blender.exe" -b -P make_meshes.py

UV rule for VFX meshes: U runs ALONG the motion (around a ring, along an arc,
up a swirl) and V ACROSS it, using the whole 0..1 square. A gradient texture
then reads as a stroke whose leading edge is at V=1, and nothing is wasted.
Roblox has no mesh UV scrolling, so motion comes from scale/rotate/fade.
"""
import math
import os
import bmesh
import bpy

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "meshes")
os.makedirs(OUT, exist_ok=True)


def reset():
    bpy.ops.wm.read_factory_settings(use_empty=True)


def mesh_from(name, verts, faces, uvs):
    """verts: list of (x,y,z) Roblox axes (Y up). faces: vertex index tuples.
    uvs: per-vertex (u,v)."""
    me = bpy.data.meshes.new(name)
    ob = bpy.data.objects.new(name, me)
    bpy.context.collection.objects.link(ob)
    bm = bmesh.new()
    # Blender is Z-up: store Roblox (x, y, z) as Blender (x, -z, y)
    bv = [bm.verts.new((x, -z, y)) for (x, y, z) in verts]
    bm.verts.ensure_lookup_table()
    uv_layer = bm.loops.layers.uv.new("UVMap")
    for f in faces:
        try:
            face = bm.faces.new([bv[i] for i in f])
        except ValueError:
            continue
        for loop, i in zip(face.loops, f):
            loop[uv_layer].uv = uvs[i]
    bm.normal_update()
    bm.to_mesh(me)
    bm.free()
    return ob


def strip(name, n_u, n_v, fn):
    """Grid surface: fn(u, v) -> (x, y, z) with u, v in [0, 1]."""
    verts, uvs, faces = [], [], []
    for j in range(n_v + 1):
        for i in range(n_u + 1):
            u, v = i / n_u, j / n_v
            verts.append(fn(u, v))
            uvs.append((u, v))
    w = n_u + 1
    for j in range(n_v):
        for i in range(n_u):
            a = j * w + i
            faces.append((a, a + 1, a + w + 1, a + w))
    return mesh_from(name, verts, faces, uvs)


def export(ob):
    bpy.ops.object.select_all(action="DESELECT")
    ob.select_set(True)
    bpy.context.view_layer.objects.active = ob
    path = os.path.join(OUT, ob.name + ".obj")
    bpy.ops.wm.obj_export(filepath=path, export_selected_objects=True, export_uv=True, export_normals=True,
                          export_materials=False, forward_axis="NEGATIVE_Z", up_axis="Y")
    tris = sum(len(p.vertices) - 2 for p in ob.data.polygons)
    print(f"MESH {ob.name}: {len(ob.data.vertices)} verts, {tris} tris -> {path}")


def main():
    reset()
    # flat crescent arc in the XZ plane (lies on the ground / slash plane):
    # 200 degrees, thick in the middle, pointed ends; V=1 is the outer edge
    span = math.radians(200)

    def crescent(u, v):
        a = -span / 2 + span * u
        taper = math.sin(math.pi * u) ** 0.8
        r = 1.0 - 0.28 * taper * (1 - v)
        return (math.sin(a) * r, 0.0, -math.cos(a) * r)
    export(strip("crescent", 64, 2, crescent))

    # flat ring (annulus), U around, V from inner (0) to outer (1)
    export(strip("ring", 96, 1, lambda u, v: (math.cos(u * 2 * math.pi) * (0.55 + 0.45 * v), 0.0, math.sin(u * 2 * math.pi) * (0.55 + 0.45 * v))))

    # open cone, apex down at y=0, rim at y=1 (funnel), U around, V up
    export(strip("cone", 64, 8, lambda u, v: (math.cos(u * 2 * math.pi) * v, v, math.sin(u * 2 * math.pi) * v)))

    # open cylinder (pillar / beam shell), V up
    export(strip("cylinder", 64, 4, lambda u, v: (math.cos(u * 2 * math.pi), v, math.sin(u * 2 * math.pi))))

    # dome (hemisphere), U around, V from rim (0) to top (1)
    export(strip("dome", 64, 16, lambda u, v: (math.cos(u * 2 * math.pi) * math.cos(v * math.pi / 2), math.sin(v * math.pi / 2), math.sin(u * 2 * math.pi) * math.cos(v * math.pi / 2))))

    # swirl: a ribbon spiralling up and outward (tornado / wind wrap)
    def swirl(u, v):
        a = u * 2 * math.pi * 1.5
        r = 0.35 + 0.65 * u
        y = u + 0.12 * (v - 0.5)
        return (math.cos(a) * r, y, math.sin(a) * r)
    export(strip("swirl", 96, 1, swirl))

    # crescent wall: a vertical curved sheet (rising slash / wind wall)
    def wall(u, v):
        a = -span / 2 + span * u
        return (math.sin(a), v * math.sin(math.pi * u) ** 0.6, -math.cos(a))
    export(strip("crescent_wall", 64, 4, wall))

    # flat quad in XZ (magic circles, ground decals as meshes), full 0..1 UV
    export(strip("plane", 1, 1, lambda u, v: (u - 0.5, 0.0, v - 0.5)))

    # torus: U around the major circle, V around the tube (vortex ring of a
    # mushroom cloud, rolling smoke ring)
    def torus(u, v, R=1.0, r=0.38):
        a, b = u * 2 * math.pi, v * 2 * math.pi
        return ((R + r * math.cos(b)) * math.cos(a), r * math.sin(b), (R + r * math.cos(b)) * math.sin(a))
    export(strip("torus", 96, 24, torus))

    # lumpy sphere: a fireball / cloud shell, low-frequency bulges baked in so
    # the silhouette is not a perfect ball (U around, V pole to pole)
    def lumpy(u, v):
        a, b = u * 2 * math.pi, (v - 0.5) * math.pi
        bump = 1 + 0.09 * math.sin(3 * a + 1.3) * math.cos(2 * b) + 0.06 * math.sin(5 * a + 2 * b) + 0.05 * math.cos(4 * b + a)
        return (math.cos(a) * math.cos(b) * bump, math.sin(b) * bump, math.sin(a) * math.cos(b) * bump)
    export(strip("lumpy_sphere", 72, 36, lumpy))

    # mushroom stem: tapered column, wider at the base and flaring at the top
    def stem(u, v):
        a = u * 2 * math.pi
        r = 0.55 - 0.3 * math.sin(v * math.pi * 0.9) + 0.25 * v ** 6
        return (math.cos(a) * r, v, math.sin(a) * r)
    export(strip("stem", 48, 16, stem))

    # crystal shard: 6-sided bipyramid, faceted
    verts = [(0, 1.0, 0), (0, -0.25, 0)]
    for k in range(6):
        a = k / 6 * 2 * math.pi
        verts.append((math.cos(a) * 0.22, 0.15, math.sin(a) * 0.22))
    faces, uvs = [], [(0.5, 1), (0.5, 0)] + [(k / 6, 0.5) for k in range(6)]
    for k in range(6):
        a, b = 2 + k, 2 + (k + 1) % 6
        faces.append((0, b, a))
        faces.append((1, a, b))
    export(mesh_from("shard", verts, faces, uvs))


main()
