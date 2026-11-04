"""Brush engine: paint VFX textures from many tapered, irregular strokes, the
way a VFX artist paints them, instead of from exact geometry.

Why (blind review 2026-10-27, twice): every SDF texture "looks like a
parameter preset, not a drawing": exact discs, evenly spaced spikes,
concentric rings, ruler-straight lines, flat slab fills. Pro textures are
built from STROKES: each one tapers, wanders, overlaps its neighbours and has
its own weight and value. This module stamps soft round brushes along jittered
paths at 4x resolution, composites stroke-over-stroke, and downsamples.

    from vfxpaint import Canvas
    c = Canvas(256)                                  # one frame, output px
    c.stroke(path, width=0.05, taper=(0.3, 1.1), alpha=1, grey=1)
    grey, alpha = c.result()                         # render-res arrays for vfxtex.assemble()

Coordinates are frame units [-1, 1], y up (same as vfxtex.grid).
"""
from __future__ import annotations

import math

import numpy as np
from PIL import Image, ImageDraw
from scipy import ndimage

SS = 4


class Canvas:
    def __init__(self, n, ss=SS):
        self.n, self.ss = n, ss
        self.m = n * ss
        self.a = np.zeros((self.m, self.m), np.float32)
        self.g = np.zeros((self.m, self.m), np.float32)

    def _px(self, p):
        return ((p[0] + 1) / 2 * self.m, (1 - (p[1] + 1) / 2) * self.m)

    def stroke(self, pts, width, taper=(0.35, 1.0), alpha=1.0, grey=1.0, alpha_profile=None, feather=0.35, grain=None):
        """pts: (N,2) path in frame units. width: max width (frame units, the
        full diameter). taper: exponents (head, tail) of x^a (1-x)^b, so the
        stroke is thick near the head and runs out to a point. feather:
        softness of the brush edge as a fraction of its radius."""
        pts = np.asarray(pts, float)
        if len(pts) < 2:
            return
        seg = np.linalg.norm(np.diff(pts, axis=0), axis=1)
        L = np.concatenate([[0], np.cumsum(seg)])
        if L[-1] <= 1e-6:
            return
        x = L / L[-1]
        ha, tb = taper
        prof = (np.clip(x, 1e-4, 1) ** ha) * (np.clip(1 - x, 1e-4, 1) ** tb)
        prof = prof / max(prof.max(), 1e-6)
        rad = width / 2 * prof * self.m / 2           # px radius at render res
        ap = alpha_profile(x) if alpha_profile else np.ones_like(x)
        # resample so stamps are ~0.3 radius apart
        out = []
        for i in range(len(pts) - 1):
            r0 = max(rad[i], rad[i + 1], 0.5)
            k = max(1, int(seg[i] * self.m / 2 / (0.3 * r0)))
            for j in range(k):
                f = j / k
                out.append((pts[i] * (1 - f) + pts[i + 1] * f, rad[i] * (1 - f) + rad[i + 1] * f, ap[i] * (1 - f) + ap[i + 1] * f))
        if not out:
            return
        # bounding box of the stroke, drawn into a small layer
        xs = [self._px(p)[0] for p, _, _ in out]
        ys = [self._px(p)[1] for p, _, _ in out]
        rmax = max(r for _, r, _ in out) + 3
        x0, x1 = int(max(0, min(xs) - rmax)), int(min(self.m, max(xs) + rmax + 1))
        y0, y1 = int(max(0, min(ys) - rmax)), int(min(self.m, max(ys) + rmax + 1))
        if x1 <= x0 or y1 <= y0:
            return
        lay = Image.new("L", (x1 - x0, y1 - y0), 0)
        d = ImageDraw.Draw(lay)
        for p, r, av in out:
            if r < 0.4:
                continue
            cx, cy = self._px(p)
            v = int(255 * max(0, min(1, av)))
            d.ellipse([cx - x0 - r, cy - y0 - r, cx - x0 + r, cy - y0 + r], fill=v)
        sa = np.asarray(lay, np.float32) / 255.0
        if feather > 0:
            sa = ndimage.gaussian_filter(sa, max(0.6, rmax * feather * 0.25))
        if grain is not None:
            sa = sa * grain[y0:y1, x0:x1]
        sa = np.clip(sa * alpha, 0, 1)
        A = self.a[y0:y1, x0:x1]
        G = self.g[y0:y1, x0:x1]
        gval = grey if np.isscalar(grey) else grey[y0:y1, x0:x1]
        newA = sa + A * (1 - sa)
        G[:] = np.where(newA > 1e-5, (gval * sa + G * A * (1 - sa)) / np.maximum(newA, 1e-5), G)
        A[:] = newA

    def result(self):
        return self.g, self.a


# ---------------------------------------------------------------- paths
def arc_path(r0, r1, a0, a1, n=48, wobble=0.0, rng=None, freq=3.0):
    """Arc from angle a0 to a1 (radians), radius easing r0 -> r1, with a
    low-frequency wobble so no stroke is a perfect circle."""
    t = np.linspace(0, 1, n)
    a = a0 + (a1 - a0) * t
    r = r0 + (r1 - r0) * t
    if wobble and rng is not None:
        ph = rng.uniform(0, 6.28, 2)
        r = r * (1 + wobble * (0.6 * np.sin(freq * 2 * np.pi * t + ph[0]) + 0.4 * np.sin(freq * 4.7 * np.pi * t + ph[1])))
    return np.stack([np.cos(a) * r, np.sin(a) * r], 1)


def curl_path(p0, heading, length, curl, n=32, rng=None, jitter=0.0):
    """A path that starts at p0 going `heading` (radians) and bends by `curl`
    radians over its length: tongues, wisps, flame licks."""
    pts = [np.array(p0, float)]
    h = heading
    step = length / (n - 1)
    for i in range(n - 1):
        h += curl / (n - 1) + (rng.normal(0, jitter) if rng is not None and jitter else 0)
        pts.append(pts[-1] + step * np.array([math.cos(h), math.sin(h)]))
    return np.array(pts)


def grain_field(m, seed, scale=6, amount=0.25):
    """Paper/brush grain: multiplies stroke alpha so fills are not flat."""
    rng = np.random.default_rng(seed)
    g = rng.random((m // 8 + 2, m // 8 + 2)).astype(np.float32)
    g = np.asarray(Image.fromarray((g * 255).astype(np.uint8)).resize((m, m), Image.BICUBIC), np.float32) / 255
    g = ndimage.gaussian_filter(g, scale)
    g = (g - g.min()) / (g.max() - g.min() + 1e-6)
    return 1 - amount + amount * g
