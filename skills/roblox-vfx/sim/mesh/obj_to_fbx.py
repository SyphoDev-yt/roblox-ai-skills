"""Convert assets/meshes/*.obj to assets/meshes_fbx/*.fbx for Open Cloud (which rejects
model/obj). Keeps Y-up (Roblox) axes, UVs and normals; prints each mesh's bounds so the
round trip can be checked against the .obj.

    blender -b --python obj_to_fbx.py
"""
import math
from pathlib import Path

import bpy

HERE = Path(__file__).resolve().parent
SRC = HERE / "assets" / "meshes"
DST = HERE / "assets" / "meshes_fbx"
DST.mkdir(exist_ok=True)

for obj_path in sorted(SRC.glob("*.obj")):
    bpy.ops.wm.read_factory_settings(use_empty=True)
    bpy.ops.wm.obj_import(filepath=str(obj_path), forward_axis="NEGATIVE_Z", up_axis="Y")
    objs = [o for o in bpy.context.scene.objects if o.type == "MESH"]
    for o in objs:
        o.select_set(True)
        # Measured in Studio 2026-10-27 (round 6 orientation probe): without this, OBJ -Z
        # (our meshes' front) lands on Roblox +Z, i.e. every mesh arrived turned 180 deg
        # about Y and the phoenix flew tail-first. Turn it back before export.
        o.rotation_euler[2] += math.pi
    bpy.context.view_layer.objects.active = objs[0]
    bpy.ops.object.transform_apply(location=False, rotation=True, scale=True)
    if len(objs) > 1:
        bpy.ops.object.join()
    o = bpy.context.view_layer.objects.active
    xs = [v.co for v in o.data.vertices]
    lo = [min(c[i] for c in xs) for i in range(3)]
    hi = [max(c[i] for c in xs) for i in range(3)]
    out = DST / (obj_path.stem + ".fbx")
    bpy.ops.export_scene.fbx(
        filepath=str(out), use_selection=False, object_types={"MESH"},
        axis_forward="-Z", axis_up="Y", apply_unit_scale=True, apply_scale_options="FBX_SCALE_NONE",
        bake_space_transform=True, mesh_smooth_type="FACE", path_mode="STRIP", embed_textures=False,
    )
    # Blender Z-up bounds; Roblox Y-up = (x, z, -y)
    print(f"FBX {obj_path.stem}: verts {len(xs)} uvs {len(o.data.uv_layers)} "
          f"size(xyz roblox) {hi[0]-lo[0]:.3f} {hi[2]-lo[2]:.3f} {hi[1]-lo[1]:.3f}")
