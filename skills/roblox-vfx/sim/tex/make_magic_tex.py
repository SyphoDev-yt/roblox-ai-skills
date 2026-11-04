"""Textures for the magic-move batch (build_moves2.py), on the vfxtex rules:
hard 1 px edges plus a halo, values not flat, irregular on purpose.

    python make_magic_tex.py      # hex_shield, hex_cell, petal_2x2, glyph_2x2
"""
import json

import numpy as np
from PIL import Image, ImageDraw

import vfxtex as vt
from vfxtex import hard, add_halo, single, save, smooth


def _hex(px_, py_):
    """Distance field of a pointy hex grid (cell radius 0.5). Returns
    (edge distance, cell id x, cell id y)."""
    sx, sy = 1.0, 1.7320508
    ax = np.floor(px_ / sx) + 0.5
    ay = np.floor(py_ / sy) + 0.5
    bx = np.floor((px_ - 0.5) / sx) + 0.5
    by = np.floor((py_ - 1.0) / sy) + 0.5
    hax, hay = px_ - ax * sx, py_ - ay * sy
    hbx, hby = px_ - (bx + 0.5) * sx, py_ - (by + 0.5) * sy
    use_a = hax * hax + hay * hay < hbx * hbx + hby * hby
    hx, hy = np.where(use_a, hax, hbx), np.where(use_a, hay, hby)
    cx, cy = np.where(use_a, ax, bx + 0.5), np.where(use_a, ay, by + 0.5)
    d = np.maximum(np.abs(hx) * 0.5 + np.abs(hy) * 0.8660254, np.abs(hx))
    return 0.5 - d, cx, cy


def hex_shield():
    """Dome ColorMap: thin bright hex edges, a faint uneven fill per cell and
    a few brighter 'charged' cells. U wraps (8 cells across)."""
    n = 512
    x, y = vt.grid(n)
    u, v = (x + 1) / 2, (y + 1) / 2
    e, cx, cy = _hex(u * 8, v * 9)
    edge_sd = e - 0.035                             # negative only inside the line band
    line = hard(edge_sd * 0.25, n, 1.2)
    line = add_halo(line, n, ((0.006, 0.4), (0.02, 0.12)))
    cell_r = vt._hash(np.floor(cx * 2).astype(np.int64) % 16, np.floor(cy * 2).astype(np.int64), 7)
    fill = 0.1 + 0.18 * cell_r + 0.35 * (cell_r > 0.86)
    inner = smooth(0.0, 0.35, e) * 0.25            # brighter towards each cell's edge
    a = np.clip(np.maximum(line, fill + (0.25 - inner)), 0, 1)
    grey = np.clip(0.55 + 0.45 * line, 0, 1)
    single("hex_shield", grey, a, n, {"use": "barrier dome ColorMap/EmissiveMask (hex grid, U wraps)", "mesh": "dome", "grey": True})


def hex_cell():
    n = 256
    x, y = vt.grid(n)
    e, _, _ = _hex(x * 0.5 / 0.92 + 0.0, y * 0.5 / 0.92 * 1.0)
    d = np.maximum(np.abs(x) * 0.5 + np.abs(y) * 0.8660254, np.abs(x)) - 0.82
    rim = hard(np.abs(d + 0.04) - 0.035, n, 1.0)
    fill = hard(d, n, 1.0) * 0.35
    a = add_halo(np.maximum(rim, fill), n, ((0.02, 0.3),))
    single("hex_cell", np.clip(0.6 + 0.4 * rim, 0, 1), a, n, {"use": "single hex plate sprite (shield hits, cracks)", "grey": True})


def petal_2x2():
    """Four petal silhouettes: teardrop with a notch, a darker vein and a
    lighter tip. Grid2x2, start random."""
    n = 256
    frames = []
    rng = np.random.default_rng(31)
    for k in range(4):
        x, y = vt.grid(n)
        ang = rng.uniform(-0.5, 0.5)
        c, s = np.cos(ang), np.sin(ang)
        xr, yr = c * x - s * y, s * x + c * y
        w = 0.38 + 0.08 * k / 3
        t = (yr + 0.85) / 1.6                       # 0 at base, 1 at tip
        half = w * np.sin(np.clip(t, 0, 1) * np.pi) ** 0.7 * (1 - 0.25 * t)
        sd = np.abs(xr) - half
        sd = np.where((t < 0) | (t > 1), 1, sd)
        notch = (t > 0.88) & (np.abs(xr) < 0.06 + 0.02 * k)
        body = hard(sd, n, 1.0) * (~notch)
        vein = np.exp(-(xr / 0.025) ** 2) * (t > 0.08) * (t < 0.7)
        grey = np.clip(0.78 + 0.22 * t - 0.25 * vein, 0, 1)
        frames.append((grey, body))
    rgb, a = vt.assemble(frames, 2, n)
    save("petal_2x2", rgb, a, {"use": "flower petals, Grid2x2 start random, tint per spell", "flipbook": "Grid2x2", "grey": True})


def glyph_2x2():
    """Four original rune glyphs (thin strokes + halo) that drift off a magic
    circle. Drawn with PIL at 4x then softened."""
    n, ss = 256, 4
    m = n * ss
    strokes = [
        [((0.5, 0.15), (0.5, 0.85)), ((0.25, 0.35), (0.75, 0.35)), ((0.3, 0.7), (0.5, 0.55), (0.7, 0.7))],
        [((0.3, 0.2), (0.7, 0.2), (0.3, 0.8), (0.7, 0.8)), ((0.5, 0.2), (0.5, 0.5))],
        [((0.2, 0.5), (0.5, 0.2), (0.8, 0.5), (0.5, 0.8), (0.2, 0.5)), ((0.5, 0.35), (0.5, 0.65))],
        [((0.3, 0.15), (0.3, 0.85)), ((0.3, 0.5), (0.72, 0.25)), ((0.3, 0.5), (0.72, 0.8))],
    ]
    frames = []
    for strk in strokes:
        im = Image.new("L", (m, m), 0)
        dr = ImageDraw.Draw(im)
        for path in strk:
            pts = [(px_ * m, py_ * m) for px_, py_ in path]
            dr.line(pts, fill=255, width=int(0.06 * m), joint="curve")
            for p in (pts[0], pts[-1]):
                r = 0.03 * m
                dr.ellipse([p[0] - r, p[1] - r, p[0] + r, p[1] + r], fill=255)
        a = np.asarray(im, dtype=float) / 255
        a = add_halo(a, n, ((0.015, 0.4), (0.05, 0.12)))
        frames.append((1.0, a))
    rgb, a = vt.assemble(frames, 2, n)
    save("glyph_2x2", rgb, a, {"use": "rune glyphs drifting off a circle, Grid2x2 start random", "flipbook": "Grid2x2", "grey": True})


def water_skin():
    """Dragon / creature water skin (U around the body, V along it, U wraps).
    water_body: three cel levels of current streaking along V (deep, mid,
    crest) with foam flecks; alpha high so the body reads solid but never
    opaque-flat. water_foam: a shell layer of broken white foam streaks with
    transparent gaps, worn 4-6% larger than the body."""
    n = 512
    m = n * 2
    c = (np.arange(m) + 0.5) / m
    u, v = np.meshgrid(c, c[::-1])
    # streaks run along V: low frequency across U, stretched along V
    su = u * 6.0
    sv = v * 1.4
    wx = vt.fbm(su * 0.5, sv * 2, 1.0, 3, seed=5, period=(3, 0)) - 0.5
    f = vt.fbm(su + wx * 1.5, sv, 1.0, 5, seed=11, period=(6, 0))
    lev = np.where(f < 0.47, 0.3, np.where(f < 0.6, 0.58, 0.88))
    edge = np.abs(f - 0.6) < 0.012
    lev = np.where(edge, 1.0, lev)                       # thin bright line where crest meets mid
    fleck_n = vt.fbm(u * 40, v * 14, 1.0, 2, seed=31, period=(40, 0))
    flecks = fleck_n > 0.74
    grey = np.where(flecks, 1.0, lev)
    alpha = np.clip(0.82 + 0.18 * (grey > 0.5), 0, 1)
    g, a = vt.downsample(grey, alpha, n)
    save("water_body", g, a, {"use": "creature water skin ColorMap/EmissiveMask (U around, V along, U wraps); tint deep blue", "grey": True})
    # foam shell
    f2 = vt.fbm(u * 10 + wx * 2, v * 1.8, 1.0, 5, seed=47, period=(10, 0))
    band = np.abs(np.sin((u * 10 + f2 * 2.5) * np.pi))
    foam = (band > 0.93) & (vt.fbm(u * 10, v * 5, 1.0, 3, seed=53, period=(10, 0)) > 0.5)
    foam_a = vt.add_halo(foam.astype(float), n, ((0.004, 0.5),))
    g2, a2 = vt.downsample(np.ones_like(foam_a), foam_a, n)
    save("water_foam", g2, a2, {"use": "foam streak shell over a water body (mostly transparent), U wraps", "grey": True})


if __name__ == "__main__":
    hex_shield(); hex_cell(); petal_2x2(); glyph_2x2(); water_skin()
    man = vt.OUT / "manifest.json"
    old = json.loads(man.read_text()) if man.exists() else {}
    old.update(vt.MANIFEST)
    man.write_text(json.dumps(old, indent=1))
    print("made", list(vt.MANIFEST))
