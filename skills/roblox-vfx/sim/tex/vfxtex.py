"""Toolkit for programmatic VFX textures, written against the measured rules of
a 2026-10-26 study of pro VFX textures:

- shape lives in ALPHA, shading in GREY (white-ish, tintable), colour only for
  an explicit "hot" variant;
- cel edges are ~1 px hard; "soft" = hard core + a separate halo holding
  12-45 % of the alpha, never one wide blur;
- 2-3 flat grey levels, a darker rim band, light from the top-left, grey
  drifting darker with age;
- nothing is symmetric: every spike, bump and strand is jittered;
- 4-11 % padding, the shape never touches the frame edge;
- 16-frame flipbooks grow, peak at t 0.13-0.33, erode from ~t 0.4 into 5-16
  pieces and are gone by t 0.8-0.9.

All coordinates are in [-1, 1] per frame (y up). Frames are rendered at 4x and
downsampled with premultiplied filtering, so edges are clean anti-aliased.
"""
from __future__ import annotations

import math
from pathlib import Path

import numpy as np
from PIL import Image
from scipy import ndimage

SS = 4
OUT = Path(__file__).resolve().parent.parent / "textures"


# ------------------------------------------------------------------ grids
def grid(n, ss=SS):
    m = n * ss
    c = (np.arange(m) + 0.5) / m * 2 - 1
    x, y = np.meshgrid(c, -c)
    return x, y


def px(n, ss=SS):
    """Width of one OUTPUT pixel in frame units, at render resolution."""
    return 2.0 / n


# ------------------------------------------------------------------ noise
def _hash(ix, iy, seed):
    h = (ix.astype(np.int64) * 374761393 + iy.astype(np.int64) * 668265263 + int(seed) * 1442695041) & 0xFFFFFFFF
    h = ((h ^ (h >> 13)) * 1274126177) & 0xFFFFFFFF
    return ((h ^ (h >> 16)) & 0xFFFF) / 65535.0


def vnoise(x, y, seed=0, period=None):
    """Value noise in [0,1], quintic fade. period=(px, py) wraps the lattice."""
    ix, iy = np.floor(x), np.floor(y)
    fx, fy = x - ix, y - iy
    ux = fx * fx * fx * (fx * (fx * 6 - 15) + 10)
    uy = fy * fy * fy * (fy * (fy * 6 - 15) + 10)
    ix, iy = ix.astype(np.int64), iy.astype(np.int64)
    ix1, iy1 = ix + 1, iy + 1
    if period:
        pxp, pyp = period
        if pxp:
            ix, ix1 = ix % pxp, ix1 % pxp
        if pyp:
            iy, iy1 = iy % pyp, iy1 % pyp
    a = _hash(ix, iy, seed)
    b = _hash(ix1, iy, seed)
    c = _hash(ix, iy1, seed)
    d = _hash(ix1, iy1, seed)
    return a + (b - a) * ux + (c - a) * uy + (a - b - c + d) * ux * uy


def fbm(x, y, freq=2.0, octaves=5, seed=0, gain=0.5, lac=2.0, period=None):
    tot, amp, norm = 0.0, 1.0, 0.0
    f = freq
    for o in range(octaves):
        per = None
        if period:
            per = (int(round(period[0] * f)) if period[0] else None, int(round(period[1] * f)) if period[1] else None)
        tot = tot + amp * vnoise(x * f, y * f, seed + o * 101, per)
        norm += amp
        amp *= gain
        f *= lac
    return tot / norm


def warp(x, y, amp=0.15, freq=2.0, seed=0, octaves=4, swirl=0.0):
    """Domain warp (0.1-0.2 of the frame per the study); swirl rotates the
    offset with radius so eroding pieces curl into C shapes."""
    dx = (fbm(x, y, freq, octaves, seed + 7) - 0.5) * 2 * amp
    dy = (fbm(x, y, freq, octaves, seed + 13) - 0.5) * 2 * amp
    if swirl:
        r = np.hypot(x, y)
        a = swirl * r
        c, s = np.cos(a), np.sin(a)
        x, y = x * c - y * s, x * s + y * c
    return x + dx, y + dy


# ------------------------------------------------------------------ shaping
def smooth(e0, e1, v):
    t = np.clip((v - e0) / (e1 - e0), 0, 1)
    return t * t * (3 - 2 * t)


def hard(sd, n, width_px=1.0):
    """Signed distance (frame units, negative inside) -> ~1 px anti-aliased
    alpha at output resolution n."""
    w = px(n) * width_px
    return np.clip(0.5 - sd / w, 0, 1)


def halo(alpha, n, sigma_frac, gain):
    """Gaussian of the core; sigma as a fraction of the frame."""
    s = sigma_frac * alpha.shape[0]
    return ndimage.gaussian_filter(alpha, s) * gain


def add_halo(alpha, n, sigmas=((0.012, 0.35), (0.05, 0.15))):
    a = alpha.copy()
    for s, g in sigmas:
        a = np.maximum(a, halo(alpha, n, s, g * 2.2))
    return np.clip(a, 0, 1)


def cel_levels(v, levels):
    """Snap 0..1 shading to flat levels, e.g. (0.55, 0.77, 1.0)."""
    levels = sorted(levels)
    cuts = [(levels[i] + levels[i + 1]) / 2 for i in range(len(levels) - 1)]
    out = np.full(v.shape, levels[0])
    for c, lv in zip(cuts, levels[1:]):
        out = np.where(v >= c, lv, out)
    return out


def lambert_from_height(h, light=(-0.6, 0.7)):
    """Shade a height field with a top-left light (screen space)."""
    gy, gx = np.gradient(h)
    k = h.shape[0] / 2.0
    nx, ny = -gx * k, gy * k
    nz = np.ones_like(h)
    ln = np.hypot(np.hypot(nx, ny), nz)
    lx, ly = light
    lz = 0.6
    ll = math.sqrt(lx * lx + ly * ly + lz * lz)
    return np.clip((nx * lx + ny * ly + nz * lz) / (ln * ll), 0, 1)


def rim_band(mask_alpha, n, frac=0.03):
    """1 inside a band of width frac (of frame) just inside the silhouette."""
    inside = mask_alpha > 0.5
    d = ndimage.distance_transform_edt(inside) / mask_alpha.shape[0]
    return inside & (d < frac)


# ------------------------------------------------------------------ output
def downsample(grey, alpha, n):
    """Premultiplied downsample to n x n, then dilate grey into transparent
    pixels so bilinear filtering in-engine never pulls in black."""
    m = alpha.shape[0]
    f = m // n
    a = alpha.reshape(n, f, n, f).mean(axis=(1, 3))
    if np.ndim(grey) == 0:
        g = np.full((n, n, 3), float(grey))
    else:
        gg = grey if grey.ndim == 3 else grey[..., None]
        pm = (gg * alpha[..., None]).reshape(n, f, n, f, gg.shape[2]).mean(axis=(1, 3))
        g = pm / np.maximum(a[..., None], 1e-5)
        if g.shape[2] == 1:
            g = np.repeat(g, 3, axis=2)
        empty = a < 1e-3
        if empty.any() and (~empty).any():
            idx = ndimage.distance_transform_edt(empty, return_distances=False, return_indices=True)
            g = g[idx[0], idx[1]]
    return np.clip(g, 0, 1), np.clip(a, 0, 1)


def assemble(frames, grid_n, n):
    """frames: list of (grey(HxW or HxWx3 or scalar), alpha) at render res."""
    W = n * grid_n
    rgb = np.ones((W, W, 3))
    a = np.zeros((W, W))
    for i, (g, al) in enumerate(frames):
        gy, gx = divmod(i, grid_n)  # left-to-right, top-to-bottom
        gg, aa = downsample(g, al, n)
        rgb[gy * n:(gy + 1) * n, gx * n:(gx + 1) * n] = gg
        a[gy * n:(gy + 1) * n, gx * n:(gx + 1) * n] = aa
    return rgb, a


MANIFEST = {}


def save(name, rgb, a, meta):
    OUT.mkdir(parents=True, exist_ok=True)
    img = np.dstack([rgb, a])
    Image.fromarray((np.clip(img, 0, 1) * 255 + 0.5).astype(np.uint8), "RGBA").save(OUT / f"{name}.png")
    m = dict(meta)
    m["size"] = [img.shape[1], img.shape[0]]
    MANIFEST[name] = m
    return OUT / f"{name}.png"


def single(name, grey, alpha, n, meta):
    g, a = downsample(grey, alpha, n)
    return save(name, g, a, meta)


# ------------------------------------------------------------------ timing
# Coverage template measured on a pro cel fire flipbook (fraction of peak).
FIRE_COVERAGE = [0.52, 0.99, 1, 0.95, 0.91, 0.83, 0.72, 0.52, 0.37, 0.25, 0.16, 0.10, 0.05, 0.03, 0.01, 0]


def lognorm(rng, n, spread=0.25):
    v = np.exp(rng.normal(0, spread, n))
    return v / v.max()
