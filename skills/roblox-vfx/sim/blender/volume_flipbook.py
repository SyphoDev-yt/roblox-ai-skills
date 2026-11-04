"""Render a stylised (cel) volumetric flipbook in Blender: fireballs, smoke
billows, dust puffs. No fluid sim: a procedural density field grows, boils
and erodes over the animation, then is drawn with STEPPED (constant-ramp)
density and colour so it reads as anime cel art, not soft realistic smoke.

    blender -b -P volume_flipbook.py -- --preset fireball --frames 16 --size 256 --out ../textures/explo_fireball_4x4.png

Presets live in PRESETS below; each is a few numbers, so new variants are
cheap. Frames are assembled left-to-right, top-to-bottom into a square grid.
"""
import argparse
import math
import os
import sys

import bpy

PRESETS = {
    # bright anime fireball: white-cream core, yellow, orange, red rim,
    # turning to dark smoke as it cools; grows fast, then erodes inside-out
    "fireball": dict(grow=0.25, r0=0.25, r1=0.95, noise=2.2, rough=0.62, boil=1.6,
                     cool_start=0.35, erode_start=0.62, smoke=True, emit=8.0, rise=0.25,
                     ramp=[(0.0, (0.10, 0.07, 0.07)), (0.18, (0.45, 0.08, 0.04)), (0.36, (1.0, 0.32, 0.05)),
                           (0.56, (1.0, 0.72, 0.18)), (0.76, (1.0, 0.95, 0.72))]),
    # dark rolling smoke billow (lit, 3 tones)
    "smoke": dict(grow=0.4, r0=0.3, r1=0.9, noise=1.8, rough=0.55, boil=0.9, cool_start=0.0,
                  erode_start=0.55, smoke=True, emit=0.0, rise=0.3,
                  ramp=[(0.0, (0.2, 0.19, 0.2))]),
    # pale dust puff for ground walls (lit)
    "dust": dict(grow=0.3, r0=0.25, r1=0.95, noise=2.4, rough=0.6, boil=0.8, cool_start=0.0,
                 erode_start=0.5, smoke=True, emit=0.0, rise=0.12,
                 ramp=[(0.0, (0.72, 0.63, 0.5))]),
}


def args():
    a = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    p = argparse.ArgumentParser()
    p.add_argument("--preset", default="fireball")
    p.add_argument("--frames", type=int, default=16)
    p.add_argument("--size", type=int, default=256)
    p.add_argument("--samples", type=int, default=24)
    p.add_argument("--out", required=True)
    p.add_argument("--seed", type=float, default=3.0)
    return p.parse_args(a)


def node(nt, kind, loc, **kw):
    n = nt.nodes.new(kind)
    n.location = loc
    for k, v in kw.items():
        setattr(n, k, v)
    return n


def math_node(nt, op, loc, a=None, b=None):
    n = node(nt, "ShaderNodeMath", loc)
    n.operation = op
    if a is not None:
        n.inputs[0].default_value = a
    if b is not None:
        n.inputs[1].default_value = b
    return n


def build(P, seed):
    bpy.ops.wm.read_factory_settings(use_empty=True)
    sc = bpy.context.scene
    sc.render.engine = "CYCLES"
    sc.cycles.device = "CPU"
    sc.render.film_transparent = True
    sc.view_settings.view_transform = "Standard"
    sc.cycles.volume_step_rate = 0.5
    sc.cycles.volume_max_steps = 512
    sc.world = bpy.data.worlds.new("w")
    sc.world.use_nodes = True
    sc.world.node_tree.nodes["Background"].inputs[1].default_value = 0.35

    bpy.ops.mesh.primitive_cube_add(size=2.4)
    dom = bpy.context.object
    mat = bpy.data.materials.new("vol")
    mat.use_nodes = True
    nt = mat.node_tree
    nt.nodes.clear()
    out = node(nt, "ShaderNodeOutputMaterial", (1400, 0))

    tc = node(nt, "ShaderNodeTexCoord", (-1400, 0))
    tval = node(nt, "ShaderNodeValue", (-1400, -300))  # animation phase 0..1
    tval.name = "PHASE"
    # rise: shift sampling down as phase grows so the mass drifts up
    rise = math_node(nt, "MULTIPLY", (-1200, -300), b=P["rise"])
    nt.links.new(tval.outputs[0], rise.inputs[0])
    comb = node(nt, "ShaderNodeCombineXYZ", (-1050, -300))
    nt.links.new(rise.outputs[0], comb.inputs[2])
    pos = node(nt, "ShaderNodeVectorMath", (-900, 0))
    pos.operation = "SUBTRACT"
    nt.links.new(tc.outputs["Object"], pos.inputs[0])
    nt.links.new(comb.outputs[0], pos.inputs[1])
    rlen = node(nt, "ShaderNodeVectorMath", (-700, 150))
    rlen.operation = "LENGTH"
    nt.links.new(pos.outputs[0], rlen.inputs[0])

    # radius over phase: fast ease-out growth to r1 at `grow`, then slow creep
    # R(t) = r0 + (r1-r0) * (1 - (1-min(t/grow,1))^3) + 0.08*t
    tg = math_node(nt, "DIVIDE", (-1200, -500), b=P["grow"])
    nt.links.new(tval.outputs[0], tg.inputs[0])
    tgc = math_node(nt, "MINIMUM", (-1050, -500), b=1.0)
    nt.links.new(tg.outputs[0], tgc.inputs[0])
    om = math_node(nt, "SUBTRACT", (-900, -500), a=1.0)
    nt.links.new(tgc.outputs[0], om.inputs[1])
    cube = math_node(nt, "POWER", (-750, -500), b=3.0)
    nt.links.new(om.outputs[0], cube.inputs[0])
    ease = math_node(nt, "SUBTRACT", (-600, -500), a=1.0)
    nt.links.new(cube.outputs[0], ease.inputs[1])
    R = math_node(nt, "MULTIPLY_ADD", (-450, -500))
    nt.links.new(ease.outputs[0], R.inputs[0])
    R.inputs[1].default_value = P["r1"] - P["r0"]
    R.inputs[2].default_value = P["r0"]

    # boiling noise (4D, W advances with phase)
    noise = node(nt, "ShaderNodeTexNoise", (-700, 450))
    noise.noise_dimensions = "4D"
    noise.inputs["Scale"].default_value = P["noise"]
    noise.inputs["Detail"].default_value = 6.0
    noise.inputs["Roughness"].default_value = P["rough"]
    nt.links.new(pos.outputs[0], noise.inputs["Vector"])
    wmul = math_node(nt, "MULTIPLY_ADD", (-900, 450), b=P["boil"])
    wmul.inputs[2].default_value = seed
    nt.links.new(tval.outputs[0], wmul.inputs[0])
    nt.links.new(wmul.outputs[0], noise.inputs["W"])

    # field = (R - r)/R + (noise - 0.5) * 0.9  -> >0 inside
    rr = math_node(nt, "SUBTRACT", (-300, 150))
    nt.links.new(R.outputs[0], rr.inputs[0])
    nt.links.new(rlen.outputs["Value"], rr.inputs[1])
    rn = math_node(nt, "DIVIDE", (-150, 150))
    nt.links.new(rr.outputs[0], rn.inputs[0])
    nt.links.new(R.outputs[0], rn.inputs[1])
    nz = math_node(nt, "MULTIPLY_ADD", (-300, 450), b=0.9)
    nz.inputs[2].default_value = -0.45
    nt.links.new(noise.outputs["Fac"], nz.inputs[0])
    field = math_node(nt, "ADD", (0, 300))
    nt.links.new(rn.outputs[0], field.inputs[0])
    nt.links.new(nz.outputs[0], field.inputs[1])

    # erosion: after erode_start a threshold climbs, centre first (inside-out)
    er_t = math_node(nt, "SUBTRACT", (-300, -150), b=P["erode_start"])
    nt.links.new(tval.outputs[0], er_t.inputs[0])
    er_c = math_node(nt, "MAXIMUM", (-150, -150), b=0.0)
    nt.links.new(er_t.outputs[0], er_c.inputs[0])
    er_k = math_node(nt, "MULTIPLY", (0, -150), b=1.0 / max(0.05, 1 - P["erode_start"]) * 1.25)
    nt.links.new(er_c.outputs[0], er_k.inputs[0])
    # centre weighting: subtract er_k * (1.2 - rn*0.6)  (rn ~1 at centre)
    cw = math_node(nt, "MULTIPLY_ADD", (0, -300), b=0.7)
    cw.inputs[2].default_value = 0.5
    nt.links.new(rn.outputs[0], cw.inputs[0])
    erode = math_node(nt, "MULTIPLY", (150, -200))
    nt.links.new(er_k.outputs[0], erode.inputs[0])
    nt.links.new(cw.outputs[0], erode.inputs[1])
    f2 = math_node(nt, "SUBTRACT", (300, 200))
    nt.links.new(field.outputs[0], f2.inputs[0])
    nt.links.new(erode.outputs[0], f2.inputs[1])

    # HARD edge: density = step(field2 > 0)
    dens = math_node(nt, "GREATER_THAN", (450, 200), b=0.0)
    nt.links.new(f2.outputs[0], dens.inputs[0])
    dmul = math_node(nt, "MULTIPLY", (600, 200), b=300.0)
    nt.links.new(dens.outputs[0], dmul.inputs[0])

    vol = node(nt, "ShaderNodeVolumePrincipled", (1100, 0))
    nt.links.new(dmul.outputs[0], vol.inputs["Density"])
    vol.inputs["Anisotropy"].default_value = 0.0

    ramp_pts = P["ramp"]
    if P["emit"] > 0:
        # heat = field2 * 1.6 - cool(t); stepped colour ramp (CONSTANT)
        cool = math_node(nt, "SUBTRACT", (450, -100), b=P["cool_start"])
        nt.links.new(tval.outputs[0], cool.inputs[0])
        coolc = math_node(nt, "MAXIMUM", (600, -100), b=0.0)
        nt.links.new(cool.outputs[0], coolc.inputs[0])
        coolk = math_node(nt, "MULTIPLY", (750, -100), b=1.4)
        nt.links.new(coolc.outputs[0], coolk.inputs[0])
        # heat is keyed to SCREEN-space radius (camera looks along +Y), so the
        # disc reads white-hot in the middle and red at the rim, as anime
        # fireballs are painted; the noise breaks the bands into tongues.
        sep = node(nt, "ShaderNodeSeparateXYZ", (-700, -750))
        nt.links.new(pos.outputs[0], sep.inputs[0])
        c2 = node(nt, "ShaderNodeCombineXYZ", (-550, -750))
        nt.links.new(sep.outputs[0], c2.inputs[0])
        nt.links.new(sep.outputs[2], c2.inputs[2])
        rho = node(nt, "ShaderNodeVectorMath", (-400, -750))
        rho.operation = "LENGTH"
        nt.links.new(c2.outputs[0], rho.inputs[0])
        q = math_node(nt, "DIVIDE", (-250, -750))
        nt.links.new(rho.outputs["Value"], q.inputs[0])
        nt.links.new(R.outputs[0], q.inputs[1])
        omq = math_node(nt, "SUBTRACT", (-100, -750), a=1.0)
        nt.links.new(q.outputs[0], omq.inputs[1])
        heat0 = math_node(nt, "MULTIPLY_ADD", (600, 50), b=0.95)
        nt.links.new(omq.outputs[0], heat0.inputs[0])
        nzh = math_node(nt, "MULTIPLY", (450, 0), b=1.6)
        nt.links.new(nz.outputs[0], nzh.inputs[0])
        nt.links.new(nzh.outputs[0], heat0.inputs[2])
        heat = math_node(nt, "SUBTRACT", (800, 50))
        nt.links.new(heat0.outputs[0], heat.inputs[0])
        nt.links.new(coolk.outputs[0], heat.inputs[1])
        cr = node(nt, "ShaderNodeValToRGB", (900, -250))
        cr.color_ramp.interpolation = "CONSTANT"
        els = cr.color_ramp.elements
        els[0].position, els[0].color = ramp_pts[0][0], (*ramp_pts[0][1], 1)
        els[1].position, els[1].color = ramp_pts[1][0], (*ramp_pts[1][1], 1)
        for pos_, col in ramp_pts[2:]:
            e = els.new(pos_)
            e.color = (*col, 1)
        nt.links.new(heat.outputs[0], cr.inputs[0])
        nt.links.new(cr.outputs[0], vol.inputs["Emission Color"])
        # emission only where hot enough; cooled parts render as lit smoke
        hot = math_node(nt, "GREATER_THAN", (900, 100), b=ramp_pts[1][0])
        nt.links.new(heat.outputs[0], hot.inputs[0])
        # Principled Volume emission is density-weighted, so for an optically
        # thick (cel) volume the visible radiance is ~ strength itself
        estr = math_node(nt, "MULTIPLY", (1000, 100), b=P["emit"] * 0.17)
        nt.links.new(hot.outputs[0], estr.inputs[0])
        nt.links.new(estr.outputs[0], vol.inputs["Emission Strength"])
        vol.inputs["Color"].default_value = (*ramp_pts[0][1], 1)
    else:
        vol.inputs["Color"].default_value = (*ramp_pts[0][1], 1)
    nt.links.new(vol.outputs[0], out.inputs["Volume"])
    dom.data.materials.append(mat)

    # key light from upper left gives the cel smoke its 2-3 tones
    bpy.ops.object.light_add(type="SUN", rotation=(math.radians(50), math.radians(-35), 0))
    bpy.context.object.data.energy = 3.0
    bpy.ops.object.camera_add(location=(0, -6, 0), rotation=(math.radians(90), 0, 0))
    cam = bpy.context.object
    cam.data.type = "ORTHO"
    cam.data.ortho_scale = 2.4
    sc.camera = cam
    return sc, tval


def main():
    a = args()
    P = PRESETS[a.preset]
    sc, tval = build(P, a.seed)
    sc.render.resolution_x = sc.render.resolution_y = a.size
    sc.cycles.samples = a.samples
    tmp = os.path.join(os.path.dirname(os.path.abspath(a.out)), "_frames_" + a.preset)
    os.makedirs(tmp, exist_ok=True)
    files = []
    for i in range(a.frames):
        tval.outputs[0].default_value = i / max(1, a.frames - 1)
        f = os.path.join(tmp, f"f{i:03d}.png")
        sc.render.filepath = f
        bpy.ops.render.render(write_still=True)
        files.append(f)
        print(f"FRAME {i + 1}/{a.frames}")
    # assemble with Blender's own image API (no PIL inside Blender)
    g = int(math.ceil(math.sqrt(a.frames)))
    W = g * a.size
    import numpy as np
    sheet = np.zeros((W, W, 4), dtype=np.float32)
    for i, f in enumerate(files):
        im = bpy.data.images.load(f)
        px = np.array(im.pixels[:], dtype=np.float32).reshape(a.size, a.size, 4)[::-1]
        gy, gx = divmod(i, g)
        sheet[gy * a.size:(gy + 1) * a.size, gx * a.size:(gx + 1) * a.size] = px
        bpy.data.images.remove(im)
    out = bpy.data.images.new("sheet", W, W, alpha=True)
    out.pixels = sheet[::-1].ravel()
    out.filepath_raw = os.path.abspath(a.out)
    out.file_format = "PNG"
    out.save()
    print("SHEET", os.path.abspath(a.out))


main()
