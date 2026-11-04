"""Programmatic VFX texture set, v2: written against the measured reference
study of pro VFX textures (its rules are summarised in vfxtex.py). Every texture
is generated from maths; no reference image is ever read.

    python make_textures.py                 # all
    python make_textures.py slash fire      # only names starting with these
    python make_textures.py --sheet         # also a contact sheet

Then measure against your own reference set, if you keep one (a measure script
that reads <category>_* names from the output folder).

Naming: <category>_<variant>[_<g>x<g>] so measure.py finds the category and
the flipbook grid. Two families:
  * particle textures (radial sprites / flipbooks), 1024 sheets;
  * MESH textures (mesh_*), laid out in UV space for the Blender meshes:
    U runs around / along the motion and TILES, V across (ring: inner->outer,
    sphere/cylinder: bottom->top). Use them in a SurfaceAppearance ColorMap.
"""
from __future__ import annotations

import json
import math
import sys

import numpy as np
from PIL import Image
from scipy import ndimage
from scipy.spatial import ConvexHull

import vfxtex as vt
from vfxtex import fbm, warp, smooth, hard, add_halo, cel_levels, lambert_from_height, rim_band, assemble, save, single

FR = 256      # frame size for 4x4 sheets
T16 = [i / 15 for i in range(16)]


def polar(x, y):
    return np.hypot(x, y), np.arctan2(y, x)


# =================================================================== slash
def slash(seed=1, style="cel"):
    """Comma-shaped crescent: hard outer edge, thick near the head, long
    tapering tail, inner edge torn into wisps, 2-3 streak lines along the arc,
    white leading band over a mid-grey body. Head at the right, arc over the
    top, sweeping clockwise (positive RotSpeed in Roblox)."""
    rng = np.random.default_rng(seed)
    frames = []
    x, y = vt.grid(FR)
    r, th = polar(x, y)
    head = math.radians(-12 + rng.uniform(-6, 6))
    span_pk = math.radians(rng.uniform(200, 222))
    for t in T16:
        R = 0.78 * (1 + 0.14 * t)
        span_f = 0.42 + 0.58 * smooth(0.0, 0.27, t)
        tail_cut = smooth(0.85, 1.0, t)                         # collapse from the tail
        span = span_pk * span_f * (1 - 0.85 * tail_cut)
        W = R * (0.58 - 0.52 * smooth(0.27, 0.9, t))            # thickness falls to ~0.05R
        s = ((th - head) % (2 * math.pi)) / max(span, 1e-3)     # 0 at head -> 1 at tail (over the top)
        s = np.where(((th - head) % (2 * math.pi)) <= span, s, 2.0)
        sc = np.clip(s, 0, 1)
        # thick near the head but tapering to a POINT at both ends (a blunt head reads as a cut-off sprite)
        prof = np.where(s <= 1, (sc + 1e-4) ** 0.35 * (1 - sc) ** 1.2 * smooth(0.0, 0.3, sc), 0) / 0.37
        jag = fbm(sc * 9 + seed, r * 3, 1.0, 4, seed + 3)
        teeth = np.maximum(0, fbm(sc * 38, r * 2, 1.0, 2, seed + 9) - 0.55) * 2.2
        w = W * prof * (1 + 0.22 * (jag - 0.5) * 2) * (1 - 0.22 * teeth)
        r_in = R - w
        sd = np.maximum(r - R, r_in - r)
        sd = np.where(s <= 1, sd, 1.0)
        a = hard(sd, FR)
        # erosion after t 0.45: arc-stretched noise eats the body into pieces
        if t > 0.45:
            en = fbm(sc * 6 + 3, (r - R) * 8, 1.0, 4, seed + 21)
            a = a * smooth(-0.02, 0.02, en - (t - 0.45) * 1.25 + 0.05 * (1 - prof))
        d = np.clip((R - r) / np.maximum(w, 1e-4), 0, 1)        # 0 outer edge -> 1 inner edge
        streak_n = fbm(sc * 4.5, d * 24, 1.0, 3, seed + 31)
        streak = np.abs(streak_n - 0.5) < 0.045
        if style == "cel":
            g = np.where(d < 0.2, 1.0, 0.62)
            g = np.where(streak & (d >= 0.2), 0.88, g)
            g = np.where((d > 0.82), 0.48, g)
        else:  # inked: dark body, white rim + white streaks
            g = np.where(d < 0.14, 1.0, 0.12)
            g = np.where(streak & (d >= 0.14), 0.9, g)
        g = g * (1 - 0.25 * t)
        frames.append((g, a))
    rgb, al = assemble(frames, 4, FR)
    save(f"slash_{style}_4x4", rgb, al, {"use": f"crescent slash ({style}), head at right, OneShot Grid4x4, VelocityPerpendicular", "flipbook": "Grid4x4", "grey": True})


def slash_glow(seed=1):
    """Single-frame soft copy for the glow layer: hard thin core + halo."""
    x, y = vt.grid(512)
    r, th = polar(x, y)
    head, span = math.radians(-12), math.radians(212)
    s = ((th - head) % (2 * math.pi)) / span
    inside = ((th - head) % (2 * math.pi)) <= span
    sc = np.clip(s, 0, 1)
    prof = np.where(inside, (sc + 1e-4) ** 0.35 * (1 - sc) ** 1.2, 0) / 0.437
    R = 0.8
    w = 0.35 * prof
    sd = np.where(inside, np.maximum(r - R, R - w - r), 1.0)
    core = hard(sd, 512) * 0.55
    a = add_halo(core, 512, ((0.02, 0.45), (0.06, 0.2)))
    single("slash_glow", 1.0, a, 512, {"use": "slash glow copy (single)", "grey": True})


# =================================================================== impact
def impact_burst(seed=2):
    rng = np.random.default_rng(seed)
    k = int(rng.integers(13, 18))
    base = np.sort(rng.uniform(0, 2 * math.pi, 1))[0]
    ang = base + 2 * math.pi * (np.arange(k) + rng.uniform(-0.35, 0.35, k)) / k
    L = 0.94 * vt.lognorm(rng, k, 0.3)
    L = 0.47 + (L - L.min()) / (L.max() - L.min() + 1e-6) * (0.94 - 0.47)
    hw = (2 * math.pi / k) * rng.uniform(0.32, 0.5, k)
    x, y = vt.grid(FR)
    r, th = polar(x, y)
    frames = []
    for t in T16:
        grow = 1 - (1 - min(1, t / 0.2)) ** 2
        valley = 0.16 * (0.6 + 0.4 * grow)
        rl = np.full(r.shape, valley)
        for i in range(k):
            dth = np.abs((th - ang[i] + math.pi) % (2 * math.pi) - math.pi)
            prof = np.clip(1 - dth / hw[i], 0, 1) ** 1.5
            rl = np.maximum(rl, valley + (L[i] * grow - valley) * prof)
        hole = (0.1 + 0.7 * smooth(0.3, 1.0, t)) * rl
        hole = hole * (1 + 0.15 * (fbm(x * 3, y * 3, 1.0, 3, seed + t * 7) - 0.5))
        sd = np.maximum(r - rl, hole - r)
        a = hard(sd, FR)
        band = (r - hole) / np.maximum(rl - hole, 1e-4)
        g = np.where(band < 0.25, 0.78, 1.0) * (1 - 0.3 * t)
        frames.append((g, a))
    rgb, al = assemble(frames, 4, FR)
    save("impact_burst_4x4", rgb, al, {"use": "cel impact burst, hollows out into spike tips, OneShot Grid4x4", "flipbook": "Grid4x4", "grey": True})


def impact_star():
    """Four 4-point star variants (curved-in arms, unequal lengths) + halo."""
    frames = []
    rng = np.random.default_rng(4)
    for v in range(4):
        x, y = vt.grid(512)
        rot = rng.uniform(-0.2, 0.2)
        xr, yr = x * math.cos(rot) - y * math.sin(rot), x * math.sin(rot) + y * math.cos(rot)
        lx, ly = rng.uniform(0.82, 0.92), rng.uniform(0.55, 0.8)
        p = rng.uniform(0.38, 0.48)
        val = (np.abs(xr) / lx) ** p + (np.abs(yr) / ly) ** p
        core = np.clip((1 - val) / 0.08, 0, 1)
        a = add_halo(core, 512, ((0.015, 0.3), (0.05, 0.12)))
        frames.append((1.0, a))
    rgb, al = assemble(frames, 2, 512)
    save("impact_star4_2x2", rgb, al, {"use": "4-point glint variants, Grid2x2 + FlipbookStartRandom, framerate 0", "flipbook": "Grid2x2", "grey": True})


# =================================================================== rings
def ring_cel(seed=5):
    rng = np.random.default_rng(seed)
    x, y = vt.grid(FR)
    r, th = polar(x, y)
    phi = rng.uniform(0, 2 * math.pi)
    T0 = rng.uniform(0.45, 0.6)
    frames = []
    mod = 1 + 0.35 * np.sin(th + phi) + 0.3 * (fbm(np.cos(th) * 2 + 3, np.sin(th) * 2 + 3, 1.5, 3, seed) - 0.5)
    for t in T16:
        thick = T0 * max(0.0, 1 - t / 0.62) ** 1.3 + 0.012
        outer = 0.86 + 0.03 * (fbm(np.cos(th) * 3, np.sin(th) * 3, 2, 3, seed + 1) - 0.5)
        inner = outer - thick * mod * 0.86
        inner = inner + 0.05 * (fbm(np.cos(th) * 4 + 9, np.sin(th) * 4, 2, 3, seed + 2) - 0.5)
        sd = np.maximum(r - outer, inner - r)
        a = hard(sd, FR)
        if t > 0.4:
            cut = fbm(np.cos(th) * 3 + t, np.sin(th) * 3, 2.0, 3, seed + 5)
            a = a * smooth(-0.01, 0.01, cut - (t - 0.4) * 1.3)
        if t > 0.8:
            a = a * 0
        d = np.clip((outer - r) / np.maximum(outer - inner, 1e-4), 0, 1)
        g = np.where(d < 0.3, 1.0, 0.78) * (1 - 0.25 * t)
        frames.append((g, a))
    rgb, al = assemble(frames, 4, FR)
    save("ring_cel_4x4", rgb, al, {"use": "cel shock ring, outer radius fixed, Size does the expansion, OneShot Grid4x4", "flipbook": "Grid4x4", "grey": True})


def ring_energy(seed=6):
    x, y = vt.grid(512)
    r, th = polar(x, y)
    rng = np.random.default_rng(seed)
    core = np.zeros_like(r)
    for rad in (0.58, 0.73, 0.87):
        a0 = rng.uniform(0, 2 * math.pi)
        span = rng.uniform(0.6, 1.0) * 2 * math.pi
        along = ((th - a0) % (2 * math.pi)) / span
        on = along <= 1
        taper = np.where(on, np.sin(np.clip(along, 0, 1) * math.pi) ** 0.7, 0)
        w = 0.022 * taper * (0.7 + 0.6 * fbm(np.cos(th) * 3, np.sin(th) * 3, 2, 3, int(rad * 100)))
        core = np.maximum(core, hard(np.abs(r - rad) - w, 512))
    a = add_halo(core, 512, ((0.012, 0.35), (0.04, 0.15)))
    single("ring_energy", 1.0, a, 512, {"use": "energy ring strands + halo (single), LightEmission 1", "grey": True})


# =================================================================== puffs
SMOKE_COVERAGE = [0.35, 0.6, 0.8, 0.92, 1, 1, 0.97, 0.9, 0.74, 0.54, 0.36, 0.2, 0.1, 0.05, 0.02, 0]


def puff_sheet(name, seed, coverage, levels, rim_dark, age_dark, hot=False, soft=False, rise=0.18, blobs=13, upbias=0.18, meta=None):
    """Union of jittered blobs, eroded by warped swirling fbm. The erosion
    threshold of each frame is SOLVED so the coverage follows the measured
    template exactly (frame 0 small, peak early, gone by the last frame)."""
    rng = np.random.default_rng(seed)
    B = []
    for i in range(blobs):
        ang = rng.uniform(0, 2 * math.pi)
        dist = rng.uniform(0, 0.5) ** 0.9
        B.append((math.cos(ang) * dist, math.sin(ang) * dist * 0.85 + upbias * rng.uniform(0, 1), rng.uniform(0.32, 0.52)))
    x, y = vt.grid(FR)
    peak_cov = None
    frames = []
    for i, t in enumerate(T16):
        sc = 0.7 + 0.3 * smooth(0.0, 0.2, t) + 0.12 * t
        yy = y - rise * t + 0.05
        f = np.full_like(x, -1.0)                                # negative outside, so noise
        for bx, by, br in B:                                     # can rag the edge but never
            rr = br * sc                                         # fill empty space
            d2 = ((x - bx * sc) ** 2 + (yy - by * sc) ** 2) / (rr * rr)
            f = np.maximum(f, 1 - d2)
        f = np.maximum(f, -1.0) - 1.6 * smooth(0.8, 0.92, np.hypot(x, y))   # ~8 % padding
        wx, wy = warp(x, yy, 0.16, 1.6, seed + 1, 4, swirl=1.8 * t)
        n = fbm(wx, wy, 2.4, 5, seed + 2)
        field = f + (n - 0.5) * 0.55
        target = coverage[i]
        if i == 0:
            peak_cov = None
        # erosion: inside where field - e > 0, solve e for the target coverage
        if peak_cov is None:
            # coverage of the un-eroded peak shape defines 1.0
            ftmp = []
            for tp in T16:
                pass
        frames.append((t, field, f, n, yy))
    # peak coverage = coverage with e=0 at the template's peak frame
    pk = int(np.argmax(coverage))
    pcov = float(((frames[pk][1]) > 0).mean())
    out = []
    for i, (t, field, f, n, yy) in enumerate(frames):
        target = coverage[i] * pcov
        lo, hi = -0.6, 1.2
        for _ in range(22):
            mid = (lo + hi) / 2
            if ((field - mid) > 0).mean() > target:
                lo = mid
            else:
                hi = mid
        e = (lo + hi) / 2 if coverage[i] > 0 else 9.0
        sd = -(field - e) * 0.35
        if soft:
            a = np.clip((field - e) / 0.06, 0, 1)
            a = a * (0.75 + 0.25 * fbm(x * 3, y * 3, 2, 4, seed + 5)) if False else a
        else:
            a = hard(sd, FR)
        h = np.clip(np.maximum(f, 0) + (n - 0.5) * 0.6 + (fbm(x, yy, 5.0, 3, seed + 9) - 0.5) * 0.35, 0, 1)
        lam = lambert_from_height(ndimage.gaussian_filter(h, 3))
        if soft:
            g = 0.55 + 0.45 * lam
            wisp = np.abs(fbm(x * 2, yy * 2, 2.5, 4, seed + 8) - 0.5) < 0.04
            g = np.where(wisp, np.maximum(g, 0.85), g)
        else:
            g = cel_levels(0.35 + 0.75 * lam, levels)
            rim = rim_band(a, FR, 0.028)
            g = np.where(rim, g - rim_dark, g)
        g = g * (1 - (1 - age_dark) * smooth(0.0, 1.0, t))
        if hot:
            cols = {levels[-1]: (1.0, 0.95, 0.72), levels[1] if len(levels) > 2 else levels[0]: (1.0, 0.6, 0.16), levels[0]: (0.86, 0.32, 0.08)}
            rgb = np.zeros(g.shape + (3,))
            base = cel_levels(0.35 + 0.75 * lam, levels)
            for lv, c in cols.items():
                rgb[base == lv] = c
            rim = rim_band(a, FR, 0.028)
            rgb[rim] = (0.55, 0.13, 0.06)
            cool = smooth(0.35, 0.95, t)
            smoke = np.array([0.32, 0.27, 0.26])
            rgb = rgb * (1 - cool)[..., None] + smoke * cool[..., None] * (0.6 + 0.4 * base[..., None])
            out.append((rgb, a))
        else:
            out.append((np.clip(g, 0, 1), a))
    rgb, al = assemble(out, 4, FR)
    save(name, rgb, al, meta or {})


# =================================================================== sparks
def spark_needle():
    x, y = vt.grid(256)
    L, w = 0.82, 0.04
    core = hard((np.abs(x) / w + np.abs(y) / L - 1) * w, 256)
    a = add_halo(core, 256, ((0.022, 0.22),))
    single("spark_needle", 1.0, a, 256, {"use": "spark streak, VelocityParallel (long axis = V)", "grey": True})


def spark_star():
    x, y = vt.grid(256)
    p = 0.42
    val = (np.abs(x) / 0.88) ** p + (np.abs(y) / 0.7) ** p
    core = np.clip((1 - val) / 0.07, 0, 1)
    a = add_halo(core, 256, ((0.02, 0.3), (0.06, 0.1)))
    single("spark_star4", 1.0, a, 256, {"use": "small 4-point twinkle", "grey": True})


def ember_8x8():
    frames = []
    for k in range(64):
        x, y = vt.grid(128)
        r, th = polar(x, y)
        a0 = 2 * math.pi * k / 64
        span = math.radians(48)
        along = ((th - a0) % (2 * math.pi)) / span
        on = along <= 1
        w = 0.07 * np.where(on, np.sin(np.clip(along, 0, 1) * math.pi) ** 0.8, 0) * (1 + 0.15 * math.sin(k * 0.7))
        core = hard(np.where(on, np.abs(r - 0.5) - w, 1), 128)
        frames.append((1.0, add_halo(core, 128, ((0.03, 0.25),))))
    rgb, al = assemble(frames, 8, 128)
    save("spark_ember_8x8", rgb, al, {"use": "curling ember, Loop Grid8x8", "flipbook": "Grid8x8", "grey": True})


# =================================================================== lightning
def bolt_2x2(seed=8):
    frames = []
    rng = np.random.default_rng(seed)
    for v in range(4):
        pts = [np.array([-0.82, rng.uniform(-0.2, 0.2)]), np.array([0.82, rng.uniform(-0.2, 0.2)])]
        disp = 0.25
        for _ in range(5):
            new = [pts[0]]
            for a, b in zip(pts[:-1], pts[1:]):
                m = (a + b) / 2
                d = b - a
                nrm = np.array([-d[1], d[0]]) / (np.linalg.norm(d) + 1e-6)
                new += [m + nrm * rng.normal(0, disp), b]
            pts = new
            disp *= 0.55
        paths = [pts]
        for _ in range(rng.integers(1, 3)):
            i0 = int(rng.integers(len(pts) // 4, 3 * len(pts) // 4))
            p0 = pts[i0]
            dirv = (pts[min(len(pts) - 1, i0 + 3)] - p0)
            ang = math.atan2(dirv[1], dirv[0]) + rng.choice([-1, 1]) * rng.uniform(0.5, 1.0)
            br = [p0]
            cur = p0.copy()
            for _ in range(10):
                ang += rng.normal(0, 0.45)
                cur = cur + np.array([math.cos(ang), math.sin(ang)]) * 0.045
                br.append(cur.copy())
            paths.append(br)
        img = Image.new("L", (512 * 4, 512 * 4), 0)
        from PIL import ImageDraw
        d = ImageDraw.Draw(img)
        S = 512 * 4
        for pi, path in enumerate(paths):
            n = len(path)
            for j in range(n - 1):
                tt = j / (n - 1)
                taper = min(1, tt / 0.1, (1 - tt) / 0.1)
                w0 = 0.022 if pi == 0 else 0.012
                w = w0 * (0.6 + 0.8 * rng.random()) * max(0.15, taper)
                p, q = path[j], path[j + 1]
                d.line([((p[0] + 1) / 2 * S, (1 - (p[1] + 1) / 2) * S), ((q[0] + 1) / 2 * S, (1 - (q[1] + 1) / 2) * S)], fill=255, width=max(2, int(w * S / 2)))
        core = np.asarray(img, dtype=np.float32) / 255
        if v >= 2:  # flicker variants: dashed
            x, y = vt.grid(512)
            core = core * (fbm(x * 3, y, 2, 2, v + 50) > 0.42)
        frames.append((1.0, add_halo(core, 512, ((0.02, 0.4), (0.045, 0.18)))))
    rgb, al = assemble(frames, 2, 512)
    save("bolt_2x2", rgb, al, {"use": "lightning bolt variants, Grid2x2 Random or StartRandom", "flipbook": "Grid2x2", "grey": True})


# =================================================================== wind
def wind_swirl(seed=9):
    x, y = vt.grid(FR)
    r, th = polar(x, y)
    frames = []
    for t in T16:
        a = np.zeros_like(r)
        g = np.ones_like(r)
        for k in range(3):
            # log spiral r = a * exp(b * theta), rotated per frame
            rot = k * 2 * math.pi / 3 + math.radians(24) * t * 15
            phase = ((th - rot) % (2 * math.pi))
            rs = 0.28 * np.exp(0.18 * phase)
            along = phase / (2 * math.pi)
            w = (0.09 * (1 - 0.6 * t)) * np.sin(np.clip(along, 0, 1) * math.pi) ** 0.7
            sd = np.abs(r - rs) - w
            on = (rs < 0.9)
            ak = hard(np.where(on, sd, 1), FR)
            if t > 0.4:
                ak = ak * smooth(-0.02, 0.02, fbm(along * 6 + k, r * 4, 1, 3, seed + k) - (t - 0.4) * 1.4)
            a = np.maximum(a, ak)
            inner = np.clip((r - rs) / np.maximum(w, 1e-4), -1, 1)
            g = np.where(ak > 0.5, np.where(inner > 0.3, 1.0, 0.78), g)
        frames.append((g * (1 - 0.2 * t), a))
    rgb, al = assemble(frames, 4, FR)
    save("wind_swirl_4x4", rgb, al, {"use": "3-arm wind spiral, Loop or OneShot Grid4x4", "flipbook": "Grid4x4", "grey": True})


# =================================================================== beams
def beam_energy(seed=10):
    """Beam strips. U runs Attachment0 -> Attachment1 and TILES (Wrap mode);
    V runs across. Streaks are stretched ALONG the beam (low frequency in U,
    high in V), the outer 5-10 % of the width fades, core width wanders."""
    W, H = 512, 128
    m_w, m_h = W * 4, H * 4
    U, Vv = np.meshgrid((np.arange(m_w) + 0.5) / m_w, (np.arange(m_h) + 0.5) / m_h)  # V = 0 at the TOP row
    across = np.abs(Vv - 0.5) * 2
    wob = 0.15 * (fbm(U, np.zeros_like(U) + 3.3, 3.0, 3, seed + 4, period=(1, None)) - 0.5)
    n = fbm(U, Vv * 5, 2.0, 5, seed, period=(1, None))
    core = 1 - smooth(0.25 + wob, 0.32 + wob, across)
    streak = smooth(0.46, 0.54, n) * (1 - smooth(0.82, 0.95, across))
    a = np.clip(np.maximum(core * 0.95, streak * 0.8), 0, 1)
    g = np.where(core > 0.5, 1.0, 0.72)
    save("beam_energy", *to_img(g, a, W, H), {"use": "beam strip, tiles along U (Wrap), streaky energy", "grey": True})
    # slash stroke: hard bright edge along the TOP row (+width side in the sim),
    # streaky body fading toward the other edge; tiles along U
    edge_v = 0.08 + 0.03 * (fbm(U, np.zeros_like(U), 4.0, 3, seed + 6, period=(1, None)) - 0.5)
    body = smooth(edge_v - 0.01, edge_v + 0.005, Vv) * (1 - smooth(0.35, 0.95, Vv))
    st = smooth(0.4, 0.6, fbm(U, Vv * 7, 2.0, 4, seed + 8, period=(1, None)))
    a2 = np.clip(body * (0.55 + 0.45 * st), 0, 1)
    a2 = np.maximum(a2, ndimage.gaussian_filter(a2, 6) * 0.35)
    g2 = np.where(Vv < edge_v + 0.07, 1.0, 0.7 + 0.25 * st)
    save("beam_slash", *to_img(g2, a2, W, H), {"use": "curved-beam slash stroke, hard edge on the +width side", "grey": True})


# =================================================================== crack
def crack_glow(seed=11):
    rng = np.random.default_rng(seed)
    S = 1024 * 2
    from PIL import ImageDraw
    img = Image.new("L", (S, S), 0)
    d = ImageDraw.Draw(img)
    c = S / 2
    k = int(rng.integers(9, 14))
    for i in range(k):
        ang = 2 * math.pi * i / k + rng.uniform(-0.2, 0.2)
        stack = [(c, c, ang, 0.0, 1.0)]
        while stack:
            px_, py_, a, dist, wf = stack.pop()
            while dist < S * 0.46 * rng.uniform(0.7, 1.0):
                a += math.radians(rng.uniform(-25, 25))
                step = S * 0.025
                nx, ny = px_ + math.cos(a) * step, py_ + math.sin(a) * step
                w = max(1, int(S * 0.008 * wf * (1 - dist / (S * 0.5))))
                d.line([(px_, py_), (nx, ny)], fill=255, width=w)
                px_, py_, dist = nx, ny, dist + step
                if rng.random() < 0.12 and wf > 0.4:
                    stack.append((px_, py_, a + rng.choice([-1, 1]) * 0.6, dist, wf * 0.6))
    core = np.asarray(img, dtype=np.float32) / 255
    a = add_halo(core, 1024, ((0.01, 0.4), (0.04, 0.18)))
    single("crack_glow", 1.0, a, 1024, {"use": "radial ground cracks + glow (decal / flat particle)", "grey": True})


# =================================================================== debris
def rocks_8x8(seed=12):
    rng = np.random.default_rng(seed)
    pts = rng.normal(0, 1, (11, 3)) * np.array([1.0, 0.75, 0.85])
    hull = ConvexHull(pts)
    light = np.array([-0.5, 0.7, 0.5]); light /= np.linalg.norm(light)
    frames = []
    from PIL import ImageDraw
    for k in range(64):
        a1, a2 = 2 * math.pi * k / 64, 2 * math.pi * k / 64 * 0.5 + 0.4
        Rx = np.array([[1, 0, 0], [0, math.cos(a1), -math.sin(a1)], [0, math.sin(a1), math.cos(a1)]])
        Ry = np.array([[math.cos(a2), 0, math.sin(a2)], [0, 1, 0], [-math.sin(a2), 0, math.cos(a2)]])
        P = pts @ (Ry @ Rx).T
        P = P / np.abs(P[:, :2]).max() * 0.78
        S = 128 * 4
        img_a = Image.new("L", (S, S), 0); img_g = Image.new("L", (S, S), 0)
        da, dg = ImageDraw.Draw(img_a), ImageDraw.Draw(img_g)
        faces = []
        for simp in hull.simplices:
            tri = P[simp]
            nrm = np.cross(tri[1] - tri[0], tri[2] - tri[0])
            cen = tri.mean(axis=0)
            if np.dot(nrm, cen) < 0:
                nrm = -nrm
            if nrm[2] <= 0:
                continue
            nrm /= np.linalg.norm(nrm)
            lv = float(np.dot(nrm, light))
            tone = 1.0 if lv > 0.55 else (0.72 if lv > 0.15 else 0.48)
            faces.append((cen[2], tri, tone))
        for _, tri, tone in sorted(faces, key=lambda f: f[0]):
            poly = [((p[0] + 1) / 2 * S, (1 - (p[1] + 1) / 2) * S) for p in tri]
            da.polygon(poly, fill=255)
            dg.polygon(poly, fill=int(tone * 255))
        a = np.asarray(img_a, dtype=np.float32) / 255
        g = np.asarray(img_g, dtype=np.float32) / 255
        edge = rim_band(a, 128, 0.02)
        g = np.where(edge, 0.25, g)
        frames.append((g, a))
    rgb, al = assemble(frames, 8, 128)
    save("debris_rock_8x8", rgb, al, {"use": "tumbling rock, Loop Grid8x8 (StartRandom for variety)", "flipbook": "Grid8x8", "grey": True})


# =================================================================== glow
def glow_orb():
    x, y = vt.grid(512)
    r, th = polar(x, y)
    lump = 1 + 0.012 * np.sin(5 * th + 1) + 0.008 * np.sin(7 * th + 2)
    R = 0.78 * lump
    inside = np.clip(0.3 + 0.3 * (r / R) ** 3, 0, 0.6)
    rim = np.exp(-((r - R * 0.96) / 0.03) ** 2)
    a = np.where(r < R, np.maximum(inside, rim), 0) * hard(r - R, 512)
    hl = np.exp(-(((x + 0.3) ** 2 + (y - 0.35) ** 2) / 0.02)) * 0.6
    a = np.clip(np.maximum(a, hl * (r < R)), 0, 1)
    a = add_halo(a, 512, ((0.02, 0.25),))
    single("glow_bubble", 1.0, a, 512, {"use": "energy bubble / shield sprite", "grey": True})
    core = np.clip(1 - r / (0.5 * lump), 0, 1) ** 1.5
    a2 = add_halo(hard(r - 0.22 * lump, 512) * 0.9 + core * 0.6, 512, ((0.05, 0.35), (0.12, 0.15)))
    single("glow_soft", 1.0, np.clip(a2, 0, 1), 512, {"use": "soft glow, hard-ish core + halo", "grey": True})
    # No core: a solid-core texture on a huge plane draws as a solid disc.
    fall = np.clip(1 - r, 0, 1) ** 2.35
    single("glow_falloff", 1.0, fall, 512, {"use": "pure radial falloff, no core, for huge glow planes and ColorMap/EmissiveMask", "grey": True})


def eclipse_disc():
    """Dark disc with a hot ragged rim and corona spikes: a hanging 'eclipse'
    residue glyph. Grey-on-white so the rim tints; the disc stays dark."""
    x, y = vt.grid(512)
    r, th = polar(x, y)
    rng = np.random.default_rng(13)
    R = 0.52 + 0.015 * (fbm(np.cos(th) * 3, np.sin(th) * 3, 2, 3, 13) - 0.5)
    disc = hard(r - R, 512)
    rim = np.exp(-((r - R) / 0.03) ** 2)
    k = 22
    ang = (th + math.pi) / (2 * math.pi) * k
    L = rng.uniform(0.08, 0.32, k)
    tri = 1 - np.abs(ang - np.floor(ang) - 0.5) * 2
    spike = (r > R) & (r < R + L[np.floor(ang).astype(int) % k] * tri ** 2.5)
    core = np.clip(np.maximum(rim, spike * 1.0), 0, 1)
    a = np.clip(np.maximum(disc * 0.92, add_halo(core, 512, ((0.015, 0.4), (0.05, 0.15)))), 0, 1)
    g = np.where((r < R - 0.03), 0.06, 1.0)
    single("eclipse_disc", g, a, 512, {"use": "dark disc + hot rim + corona (residue glyph); tint rim via Color", "grey": True})


# =================================================================== mesh textures
def strip_uv(W, H):
    m_w, m_h = W * 2, H * 2
    u = (np.arange(m_w) + 0.5) / m_w
    v = (np.arange(m_h) + 0.5) / m_h
    U, Vv = np.meshgrid(u, v[::-1])   # V = 0 at the BOTTOM row (OBJ/Blender UV)
    return U, Vv


def to_img(g, a, W, H):
    G = np.asarray(Image.fromarray((np.clip(g, 0, 1) * 255).astype(np.uint8)).resize((W, H), Image.LANCZOS), dtype=np.float32) / 255
    A = np.asarray(Image.fromarray((np.clip(a, 0, 1) * 255).astype(np.uint8)).resize((W, H), Image.LANCZOS), dtype=np.float32) / 255
    return np.repeat(G[..., None], 3, 2), A


def mesh_textures(seed=20):
    # shock ring (ring mesh: U around, V inner -> outer): bright hard outer
    # edge, streaky body fading inward, ragged inner edge. Tiles in U.
    W, H = 1024, 256
    U, Vv = strip_uv(W, H)
    n = fbm(U * 6, Vv * 1.5, 1.0, 5, seed, period=(6, None))
    rag = 0.25 + 0.2 * fbm(U * 8, Vv, 1.0, 3, seed + 1, period=(8, None))
    body = smooth(rag, rag + 0.35, Vv) * (1 - smooth(0.93, 0.95, Vv))
    streak = 0.7 + 0.3 * smooth(0.45, 0.6, fbm(U * 24, Vv * 0.5, 1.0, 3, seed + 2, period=(24, None)))
    a = body * streak * (0.55 + 0.45 * smooth(0.6, 0.9, Vv))
    g = np.where(Vv > 0.8, 1.0, 0.8 + 0.2 * n)
    save("mesh_shock_ring", *to_img(g, a, W, H), {"use": "ring mesh ColorMap (U around, V inner->outer), AlphaMode Transparency + EmissiveMask", "mesh": "ring"})

    # fire shell (lumpy_sphere / dome: U around, V bottom -> top): cel
    # blotches in 3 levels with burning holes; grey so SurfaceAppearance.Color tints
    W, H = 1024, 512
    U, Vv = strip_uv(W, H)
    wx, wy = warp(U * 4, Vv * 2, 0.35, 1.0, seed + 3, 4)
    n = fbm(wx, wy, 1.0, 5, seed + 4, period=(4, None))
    nn = np.clip((n - 0.5) * 2.6 + 0.5, 0, 1)
    g = cel_levels(nn, (0.55, 0.78, 1.0))
    a = smooth(0.12, 0.16, nn)
    save("mesh_fire_shell", *to_img(g, a, W, H), {"use": "fireball shell ColorMap, 3 cel levels, holes; tint via SurfaceAppearance.Color", "mesh": "lumpy_sphere"})

    # smoke shell: darker 2-level cel blotches, solid, ragged lower edge
    n2 = fbm(*warp(U * 3, Vv * 1.5, 0.3, 1.0, seed + 5, 4), 1.0, 5, seed + 6, period=(3, None))
    nn2 = np.clip((n2 - 0.5) * 2.4 + 0.5, 0, 1)
    g2 = cel_levels(nn2, (0.6, 0.82, 1.0))
    a2 = smooth(0.0, 0.08, Vv - 0.15 * nn2) * smooth(0.06, 0.1, nn2)
    save("mesh_smoke_shell", *to_img(g2, a2, W, H), {"use": "mushroom cap / column smoke ColorMap", "mesh": "lumpy_sphere, stem"})

    # pillar (cylinder: U around, V up): vertical streaks, fades at the top,
    # hard bright band at the bottom
    W, H = 512, 1024
    U, Vv = strip_uv(W, H)
    s = fbm(U * 10, Vv * 0.6, 1.0, 4, seed + 7, period=(10, None))
    a = smooth(0.35, 0.55, s + 0.2 * (1 - Vv)) * (1 - smooth(0.55, 1.0, Vv)) * smooth(0.0, 0.03, Vv)
    g = np.where(Vv < 0.12, 1.0, 0.75 + 0.25 * s)
    save("mesh_pillar", *to_img(g, a, W, H), {"use": "light/fire pillar ColorMap (cylinder), fades upward", "mesh": "cylinder"})

    # spike skirt (cone, apex down: V 0 apex -> 1 rim): downward teeth at the rim
    W, H = 1024, 512
    U, Vv = strip_uv(W, H)
    rng = np.random.default_rng(seed + 8)
    k = 28
    ph = (U * k + rng.uniform(0, 1)) % 1.0
    lens = rng.uniform(0.35, 1.0, k)
    jitter = lens[np.clip((U * k).astype(int), 0, k - 1)]
    tooth = 1 - np.abs(ph - 0.5) * 2
    reach = 1 - tooth ** 1.6 * (0.55 + 0.4 * jitter)
    a = smooth(reach - 0.01, reach + 0.01, Vv) * (1 - smooth(0.97, 1.0, Vv))
    g = np.where(Vv > 0.85, 1.0, 0.8)
    save("mesh_spike_skirt", *to_img(g, a, W, H), {"use": "downward spike skirt ColorMap (cone apex down)", "mesh": "cone"})

    # ground scorch decal (plane mesh, full UV): dark ragged disc
    W = H = 1024
    U, Vv = strip_uv(W, H)
    x, y = U * 2 - 1, Vv * 2 - 1
    r = np.hypot(x, y)
    n = fbm(x * 2, y * 2, 2.0, 5, seed + 10)
    a = (1 - smooth(0.55, 0.9, r + (n - 0.5) * 0.5)) * 0.85
    g = 0.15 + 0.15 * cel_levels(n, (0.0, 1.0))
    save("mesh_scorch", *to_img(g, a, W, H), {"use": "ground scorch decal (plane mesh)", "mesh": "plane"})


# =================================================================== sigils
def sigils():
    import magic_circles
    magic_circles.make(5, "sigil")


ALL = {
    "slash": lambda: (slash(1, "cel"), slash(3, "ink"), slash_glow()),
    "impact": lambda: (impact_burst(), impact_star()),
    "ring": lambda: (ring_cel(), ring_energy()),
    "fire": lambda: (puff_sheet("fire_cel_4x4", 31, vt.FIRE_COVERAGE, (0.55, 0.77, 1.0), 0.12, 0.5, meta={"use": "cel fire puff, grey, OneShot Grid4x4", "flipbook": "Grid4x4", "grey": True}),
                     puff_sheet("fire_hot_4x4", 32, vt.FIRE_COVERAGE, (0.55, 0.77, 1.0), 0.12, 0.5, hot=True, meta={"use": "cel fire puff, PRE-COLOURED hot (cream/orange/red -> smoke)", "flipbook": "Grid4x4", "grey": False})),
    "smoke": lambda: (puff_sheet("smoke_cel_4x4", 41, SMOKE_COVERAGE, (0.86, 1.0), 0.42, 0.5, rise=0.22, meta={"use": "cel smoke puff, inked rim, darkens with age, OneShot Grid4x4", "flipbook": "Grid4x4", "grey": True}),
                      puff_sheet("smoke_soft_4x4", 42, SMOKE_COVERAGE, (0.86, 1.0), 0.0, 0.55, soft=True, rise=0.22, meta={"use": "soft smoke puff with wisps, OneShot Grid4x4", "flipbook": "Grid4x4", "grey": True}),
                      puff_sheet("smoke_dust_4x4", 43, SMOKE_COVERAGE, (0.78, 1.0), 0.2, 0.7, rise=0.08, blobs=16, upbias=0.05, meta={"use": "dust wall puff (flatter, low rise), tint tan", "flipbook": "Grid4x4", "grey": True})),
    "spark": lambda: (spark_needle(), spark_star(), ember_8x8()),
    "bolt": lambda: bolt_2x2(),
    "wind": lambda: wind_swirl(),
    "beam": lambda: beam_energy(),
    "crack": lambda: crack_glow(),
    "debris": lambda: rocks_8x8(),
    "glow": lambda: glow_orb(),
    "eclipse": lambda: eclipse_disc(),
    "mesh": lambda: mesh_textures(),
    "sigil": lambda: sigils(),
}


def main():
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    for k, fn in ALL.items():
        if not args or any(k.startswith(a) or a.startswith(k) for a in args):
            fn()
            print("made", k)
    man = vt.OUT / "manifest.json"
    old = json.loads(man.read_text()) if man.exists() else {}
    old.update(vt.MANIFEST)
    man.write_text(json.dumps(old, indent=1))
    if "--sheet" in sys.argv:
        names = list(vt.MANIFEST)
        tiles = []
        for name in names:
            im = Image.open(vt.OUT / f"{name}.png").convert("RGBA")
            im.thumbnail((260, 260))
            bg = Image.new("RGBA", (280, 280), (52, 58, 70, 255))
            bg.paste(Image.new("RGBA", (140, 280), (14, 15, 18, 255)), (140, 0))
            bg.alpha_composite(im, ((280 - im.width) // 2, (280 - im.height) // 2))
            tiles.append(bg)
        cols = 6
        rows = math.ceil(len(tiles) / cols)
        sh = Image.new("RGB", (cols * 280, rows * 280), (0, 0, 0))
        for i, t in enumerate(tiles):
            sh.paste(t.convert("RGB"), ((i % cols) * 280, (i // cols) * 280))
        sh.save(vt.OUT.parent / "tex" / "contact_sheet.png")
        print("sheet written")


if __name__ == "__main__":
    main()
