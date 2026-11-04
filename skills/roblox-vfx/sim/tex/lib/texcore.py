"""Shared core for the texture library: grids, signed distances (analytic or
rasterised with PIL then EDT), the four render styles, erosion for flipbooks,
and output.

Everything a family returns is a SIGNED DISTANCE `sd` in frame units (the frame
spans [-1, 1], negative inside) or a density `f` in [0, 1]. A style turns that
into grey + alpha following the measured texture rules (vfxtex.py docstring):
shape in alpha, tintable grey shading, ~1 px cel edges, a darker rim band,
top-left light, padding so nothing touches the frame edge.

Styles
  cel   hard 1 px edge, 3 flat grey levels from a top-left light, darker rim
  soft  solid core with an exponential falloff, white-to-light-grey
  glow  thin hard white core + wide gaussian halo (for LightEmission 1 layers)
  ink   noise-warped ragged edge with dry-brush gaps, flat grey with patches
"""
from __future__ import annotations

import math
import sys
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw
from scipy import ndimage

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from vfxtex import fbm, vnoise, smooth, cel_levels, lambert_from_height, downsample  # noqa: E402

LIB = Path(__file__).resolve().parent.parent.parent / "textures" / "lib"
STYLES = ("cel", "soft", "glow", "ink")


# ------------------------------------------------------------------ grids
def grid(m):
    c = (np.arange(m) + 0.5) / m * 2 - 1
    x, y = np.meshgrid(c, -c)
    return x, y


def polar(x, y):
    return np.hypot(x, y), np.arctan2(y, x)


def rot(x, y, a):
    c, s = math.cos(a), math.sin(a)
    return x * c - y * s, x * s + y * c


def ang_noise(th, k, seed, oct=3):
    """Periodic noise around the circle, in [-1, 1]."""
    u = (th / (2 * math.pi) + 0.5) * k
    return (fbm(u, np.zeros_like(u) + seed * 0.37, 1.0, oct, seed=seed, period=(k, 0)) - 0.5) * 2


# ------------------------------------------------------------------ distances
def seg_sd(x, y, a, b):
    ax, ay = a
    bx, by = b
    px, py = x - ax, y - ay
    dx, dy = bx - ax, by - ay
    L = dx * dx + dy * dy + 1e-12
    h = np.clip((px * dx + py * dy) / L, 0, 1)
    return np.hypot(px - dx * h, py - dy * h)


def path_sd(x, y, pts, width, width1=None):
    """Distance to a polyline with linear width taper (width -> width1), as sd."""
    if width1 is None:
        width1 = width
    d = np.full(x.shape, 9.0)
    n = len(pts) - 1
    for i in range(n):
        w = width + (width1 - width) * (i + 0.5) / n
        d = np.minimum(d, seg_sd(x, y, pts[i], pts[i + 1]) - w / 2)
    return d


def raster(m, draw_fn):
    """draw_fn(draw, to_px) paints white on black at m x m; returns bool mask."""
    im = Image.new("L", (m, m), 0)
    dr = ImageDraw.Draw(im)
    to_px = lambda p: ((p[0] + 1) * m / 2, (1 - p[1]) * m / 2)
    draw_fn(dr, to_px)
    return np.asarray(im) > 127


def mask_sd(mask):
    """Signed distance (frame units) from a boolean mask."""
    m = mask.shape[0]
    if not mask.any():
        return np.full(mask.shape, 9.0)
    out = ndimage.distance_transform_edt(~mask)
    inn = ndimage.distance_transform_edt(mask)
    return (out - inn) * (2.0 / m)


def union(*s):
    return np.minimum.reduce(s)


def smin(a, b, k=0.05):
    h = np.clip(0.5 + 0.5 * (b - a) / k, 0, 1)
    return b * (1 - h) + a * h - k * h * (1 - h)


def f_to_sd(f, thr=0.5, scale=0.25):
    return (thr - f) * scale


# ------------------------------------------------------------------ styles
def _aa(sd, pw):
    return np.clip(0.5 - sd / pw, 0, 1)


def style(sd, n, kind, seed=0, thick=0.08, grey_lv=(0.62, 0.82, 1.0), shade=None, levels=None):
    """sd at render res (m = n * ss) -> (grey, alpha) at render res."""
    m = sd.shape[0]
    pw = 2.0 / n
    x, y = grid(m)
    if kind == "cel":
        a = _aa(sd, pw)
        depth = np.clip(-sd / thick, 0, 1)
        h = ndimage.gaussian_filter(depth, m * 0.008) if shade is None else shade
        lam = lambert_from_height(h)
        g = cel_levels(0.5 + 0.5 * lam, grey_lv) if levels is None else levels
        g = np.where((sd > -pw * 2.2) & (sd <= 0.0), g * 0.8, g)
        return g, a
    if kind == "soft":
        core = _aa(sd + pw, pw * 2)
        fs = max(thick * 0.6, pw * 3)
        fall = np.exp(-np.maximum(sd, 0) / fs) * 0.85 * np.clip(1 - sd / (fs * 1.6), 0, 1)
        a = np.maximum(core * 0.95, fall * (sd > 0))
        g = 0.82 + 0.18 * np.clip(-sd / thick, 0, 1)
        return g, np.clip(a, 0, 1)
    if kind == "glow":
        core = _aa(sd + thick * 0.25, pw)
        base = _aa(sd, pw)
        s1 = ndimage.gaussian_filter(base, m * 0.012) * 0.9
        s2 = ndimage.gaussian_filter(base, m * 0.04) * 0.5
        a = np.clip(np.maximum.reduce([core, s1 * 1.6, s2 * 1.6, base * 0.55]), 0, 1)
        g = np.clip(0.88 + 0.12 * core, 0, 1)
        return g, a
    if kind == "ink":
        nz = fbm(x * 9 + seed, y * 9, 1.0, 4, seed=seed + 5) - 0.5
        sd2 = sd + nz * pw * 9
        a = _aa(sd2, pw)
        streak = fbm(x * 3 + seed, y * 40, 1.0, 3, seed=seed + 9)
        edge = np.clip(1 + sd2 / (thick * 0.7), 0, 1)
        a = a * np.where((streak > 0.62) & (edge > 0.35), 0.0, 1.0)
        patch = fbm(x * 4, y * 4 + seed, 1.0, 3, seed=seed + 11)
        g = np.where(patch > 0.55, 0.78, 0.95) if levels is None else np.where(patch > 0.6, levels * 0.85, levels)
        return g, a
    raise ValueError(kind)


def density_style(f, n, kind, seed=0):
    """For naturally soft families (smoke, clouds): f in [0,1] density."""
    m = f.shape[0]
    if kind in ("soft", "glow"):
        a = np.clip(f, 0, 1) ** (1.2 if kind == "soft" else 0.9)
        h = ndimage.gaussian_filter(f, m * 0.01)
        g = 0.72 + 0.28 * lambert_from_height(h) if kind == "soft" else 0.9 + 0.1 * a
        return g, a
    return style(f_to_sd(f, 0.45, 0.3), n, kind, seed, thick=0.12)


# ------------------------------------------------------------------ flipbooks
def erode(a, t, seed, x, y, t0=0.42, t1=0.9, scale=5.0):
    """Break the shape into pieces after t0 and be gone by t1."""
    if t <= t0:
        return a
    k = smooth(t0, t1, t)
    nz = fbm(x * scale + seed, y * scale, 1.0, 4, seed=seed + 77)
    return a * np.clip((nz - (0.25 + 0.8 * k)) / 0.04 + 0.5, 0, 1)


def pad_ok(a, frac=0.03):
    m = a.shape[0]
    b = max(1, int(m * frac))
    border = np.concatenate([a[:b].ravel(), a[-b:].ravel(), a[:, :b].ravel(), a[:, -b:].ravel()])
    return float(border.mean()) < 0.02


def fade_border(a, frac=0.06):
    """Force padding: alpha ramps to 0 over the outer frac of the frame."""
    m = a.shape[0]
    x, y = grid(m)
    e = np.maximum(np.abs(x), np.abs(y))
    return a * smooth(1.0, 1.0 - frac * 2, e)


# ------------------------------------------------------------------ output
def save_png(path, rgb, a):
    path.parent.mkdir(parents=True, exist_ok=True)
    if rgb.ndim == 2:
        rgb = np.repeat(rgb[..., None], 3, axis=2)
    img = np.dstack([rgb, a])
    Image.fromarray((np.clip(img, 0, 1) * 255 + 0.5).astype(np.uint8), "RGBA").save(path, optimize=True)


def to_rgb(g, colour=None):
    if colour is None:
        return g
    gg = g if g.ndim == 3 else g[..., None]
    return np.clip(gg * np.array(colour), 0, 1)
