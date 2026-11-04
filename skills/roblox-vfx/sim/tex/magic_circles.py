"""Original magic-circle textures, in separable layers so each can rotate
and appear on its own schedule (outline first, glyph band later, core last).

Everything is generated: a seeded rune ALPHABET (strokes on a small grid,
so every set is our own script, not anyone's lettering), ring hierarchy,
star polygons, tick bands. White on transparent, tint in engine.

    python magic_circles.py --seed 5 --name sigil      # -> ../textures/sigil_{outer,band,inner,core}.png

Line-weight hierarchy (fractions of the 1024 px radius, measured as drawn):
one heavy rim 1.6%, paired thin rings 0.45%, rune band height 7%,
polygon strokes 0.7%, node circles 0.5%. Supersampled 4x, so every edge is
anti-aliased and thin rings never shimmer when scaled down in game.
"""
import argparse
import math
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFilter

OUT = Path(__file__).resolve().parent.parent / "textures"
N = 1024
SS = 4
M = N * SS
C = M / 2


def canvas():
    return Image.new("L", (M, M), 0)


def ring(d, r, w):
    d.ellipse([C - r, C - r, C + r, C + r], outline=255, width=max(1, int(w)))


def polar(r, a):
    return (C + r * math.cos(a), C + r * math.sin(a))


def rune_alphabet(seed, n=24):
    """Each rune: 2-4 strokes between points of a 3x4 grid, plus an optional
    dot or arc. Rejects near-duplicates so the script reads as varied."""
    rng = np.random.default_rng(seed)
    pts = [(x, y) for y in range(4) for x in range(3)]
    runes, seen = [], set()
    while len(runes) < n:
        k = rng.integers(2, 5)
        cur = pts[rng.integers(len(pts))]
        strokes = []
        for _ in range(k):
            nxt = pts[rng.integers(len(pts))]
            if nxt == cur:
                continue
            strokes.append((cur, nxt))
            cur = nxt if rng.random() < 0.7 else pts[rng.integers(len(pts))]
        if len(strokes) < 2:
            continue
        key = tuple(sorted(tuple(sorted(s)) for s in strokes))
        if key in seen:
            continue
        seen.add(key)
        extra = rng.choice(["none", "dot", "arc"], p=[0.5, 0.3, 0.2])
        runes.append((strokes, extra, pts[rng.integers(len(pts))]))
    return runes


def draw_rune(d, rune, cx, cy, h, ang, w):
    """Draw a rune centred at (cx,cy), height h, rotated so its 'up' points
    outward from the circle centre (ang = radial angle)."""
    strokes, extra, ep = rune
    sw = h * 0.62 / 2
    up = (math.cos(ang), math.sin(ang))
    rt = (-up[1], up[0])

    def tp(p):
        gx = (p[0] - 1) / 1.0 * sw
        gy = (1.5 - p[1]) / 1.5 * (h / 2)
        return (cx + rt[0] * gx + up[0] * gy, cy + rt[1] * gx + up[1] * gy)

    for a, b in strokes:
        d.line([tp(a), tp(b)], fill=255, width=int(w))
        for q in (tp(a), tp(b)):
            d.ellipse([q[0] - w / 2, q[1] - w / 2, q[0] + w / 2, q[1] + w / 2], fill=255)
    if extra == "dot":
        q = tp(ep)
        d.ellipse([q[0] - w * 1.1, q[1] - w * 1.1, q[0] + w * 1.1, q[1] + w * 1.1], fill=255)
    elif extra == "arc":
        q = tp(ep)
        rr = h * 0.18
        d.arc([q[0] - rr, q[1] - rr, q[0] + rr, q[1] + rr], 0, 200, fill=255, width=int(w * 0.8))


def star_polygon(d, r, n, k, w, rot):
    pts = [polar(r, rot + 2 * math.pi * i / n) for i in range(n)]
    for i in range(n):
        d.line([pts[i], pts[(i + k) % n]], fill=255, width=int(w))
    return pts


def dashed_ring(d, r, w, segs, duty, rot=0.0):
    """Ring broken into segs arcs, each covering `duty` of its slot."""
    for i in range(segs):
        a0 = math.degrees(rot) + 360 * i / segs
        d.arc([C - r, C - r, C + r, C + r], a0, a0 + 360 * duty / segs, fill=255, width=max(1, int(w)))


def finish(img, name, meta):
    from scipy import ndimage
    a = img.resize((N, N), Image.LANCZOS)
    core = np.asarray(a, dtype=np.float32) / 255.0
    # bloom baked in: core + G(1%)*0.35 + G(5%)*0.15 (study target: 30-45 % of alpha in the halo)
    h1 = ndimage.gaussian_filter(core, N * 0.01) * 0.35 * 2.4
    h2 = ndimage.gaussian_filter(core, N * 0.05) * 0.15 * 3.0
    arr = np.clip(np.maximum(core, h1 + h2), 0, 1)
    rgba = np.dstack([np.ones_like(arr), np.ones_like(arr), np.ones_like(arr), arr])
    OUT.mkdir(parents=True, exist_ok=True)
    Image.fromarray((rgba * 255 + 0.5).astype(np.uint8), "RGBA").save(OUT / f"{name}.png")
    return meta


def make(seed, name):
    rng = np.random.default_rng(seed)
    R = M * 0.49
    runes = rune_alphabet(seed)
    metas = {}

    # OUTER: heavy rim, paired thin rings, tick band (appears first)
    im = canvas(); d = ImageDraw.Draw(im)
    ring(d, R, M * 0.01440)
    dashed_ring(d, R * 0.955, M * 0.004, int(rng.integers(18, 30)), 0.72, rng.uniform(0, 1))
    ring(d, R * 0.80, M * 0.004)
    ring(d, R * 0.77, M * 0.00630)
    nt = int(rng.choice([72, 96, 120]))
    for i in range(nt):
        a = 2 * math.pi * i / nt
        L = 0.028 if i % 6 == 0 else 0.014
        d.line([polar(R * 0.77, a), polar(R * (0.77 - L), a)], fill=255, width=int(M * 0.00288))
    metas[f"{name}_outer"] = finish(im, f"{name}_outer", {})

    # BAND: rune band between the thin rings (fills in second, rotates)
    im = canvas(); d = ImageDraw.Draw(im)
    band_r = R * 0.877
    h = R * 0.11
    count = int(rng.integers(28, 38))
    for i in range(count):
        a = 2 * math.pi * i / count
        cx, cy = polar(band_r, a)
        draw_rune(d, runes[int(rng.integers(len(runes)))], cx, cy, h, a, M * 0.00504)
    # separators: small diamonds every few runes
    for i in range(0, count, 7):
        a = 2 * math.pi * (i + 0.5) / count
        cx, cy = polar(band_r, a)
        s = h * 0.18
        d.polygon([polar(band_r + s, a), polar(band_r, a + s / band_r), polar(band_r - s, a), polar(band_r, a - s / band_r)], fill=255)
    metas[f"{name}_band"] = finish(im, f"{name}_band", {})

    # INNER: star polygon(s) with node circles (counter-rotates)
    im = canvas(); d = ImageDraw.Draw(im)
    n = int(rng.choice([6, 7, 8, 9]))
    k = 2 if n < 7 else int(rng.choice([2, 3]))
    ri = R * 0.66
    rot = -math.pi / 2
    pts = star_polygon(d, ri, n, k, M * 0.01080, rot)
    ring(d, ri, M * 0.00810)
    dashed_ring(d, ri * 0.93, M * 0.0036, int(rng.integers(40, 64)), 0.5)
    for p in pts:
        rr = R * 0.045
        d.ellipse([p[0] - rr, p[1] - rr, p[0] + rr, p[1] + rr], outline=255, width=int(M * 0.00720))
        d.ellipse([p[0] - rr * 0.35, p[1] - rr * 0.35, p[0] + rr * 0.35, p[1] + rr * 0.35], fill=255)
    # inner small rune ring
    for i in range(n * 2):
        a = rot + 2 * math.pi * (i + 0.5) / (n * 2)
        cx, cy = polar(ri * 0.82, a)
        draw_rune(d, runes[int(rng.integers(len(runes)))], cx, cy, R * 0.07, a, M * 0.00396)
    metas[f"{name}_inner"] = finish(im, f"{name}_inner", {})

    # CORE: concentric rings + a central compound glyph (appears last)
    im = canvas(); d = ImageDraw.Draw(im)
    rc = R * 0.33
    ring(d, rc, M * 0.00900)
    ring(d, rc * 0.86, M * 0.00360)
    star_polygon(d, rc * 0.86, 4, 1, M * 0.00540, rot)
    star_polygon(d, rc * 0.86, 4, 1, M * 0.00540, rot + math.pi / 4)
    # compound core glyph: three of our runes overlaid at 120 degrees + a dot ring
    for j in range(3):
        draw_rune(d, runes[(j * 7) % len(runes)], C, C, rc * 0.95, -math.pi / 2 + j * 2 * math.pi / 3, M * 0.009)
    for j in range(12):
        q = polar(rc * 0.62, 2 * math.pi * j / 12)
        rr = rc * 0.035
        d.ellipse([q[0] - rr, q[1] - rr, q[0] + rr, q[1] + rr], fill=255)
    metas[f"{name}_core"] = finish(im, f"{name}_core", {})
    return metas


def preview(name):
    """Composite the layers in a hot palette over night sky, for eyeballing."""
    bg = Image.new("RGBA", (N, N), (30, 40, 70, 255))
    cols = {"outer": (255, 120, 120), "band": (255, 205, 140), "inner": (255, 150, 110), "core": (255, 240, 180)}
    for layer, col in cols.items():
        a = Image.open(OUT / f"{name}_{layer}.png").split()[3]
        glow = a.filter(ImageFilter.GaussianBlur(10))
        for src, k in ((glow, 0.6), (a, 1.0)):
            tint = Image.new("RGBA", (N, N), col + (0,))
            tint.putalpha(src.point(lambda v: int(v * k)))
            bg.alpha_composite(tint)
    bg.convert("RGB").resize((512, 512), Image.LANCZOS).save(OUT.parent / "tex" / f"{name}_preview.png")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--seed", type=int, default=5)
    ap.add_argument("--name", default="sigil")
    a = ap.parse_args()
    make(a.seed, a.name)
    preview(a.name)
    print("wrote", a.name, "layers")
