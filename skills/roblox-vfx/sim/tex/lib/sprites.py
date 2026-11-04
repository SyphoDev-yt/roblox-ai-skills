"""Single-sprite families. Each takes (rng, x, y, m) at render resolution and
returns {"sd": signed distance, "thick": shading depth} or {"f": density}.
Parameters are drawn from rng so every seed is a visibly different variant.
Shapes stay inside ~|0.9| so the frame keeps its padding.
"""
import math

import numpy as np
from scipy import ndimage

from texcore import (polar, rot, ang_noise, seg_sd, path_sd, raster, mask_sd, union, smin, f_to_sd, fbm, vnoise, smooth)

TAU = 2 * math.pi
INDEX = 0  # variant index, set by the builder before each call (families that need a per-index choice read it)


def U(rng, a, b):
    return float(rng.uniform(a, b))


# ================================================================ rings
def ring(rng, x, y, m):
    r, th = polar(x, y)
    R = U(rng, 0.45, 0.78)
    w = U(rng, 0.03, 0.22)
    k = int(rng.integers(3, 14))
    wob = U(rng, 0, 0.06)
    Rt = R + wob * ang_noise(th, k, int(rng.integers(1e6)))
    wt = w * (1 + U(rng, 0, 0.8) * ang_noise(th, k, int(rng.integers(1e6))))
    sd = np.abs(r - Rt) - np.maximum(wt, 0.01) / 2
    gaps = int(rng.integers(0, 5))
    if gaps:
        ph = U(rng, 0, TAU)
        cut = np.cos((th + ph) * gaps) > U(rng, 0.55, 0.9)
        sd = np.where(cut, np.maximum(sd, 0.6), sd)
    if rng.random() < 0.35:
        R2 = R * U(rng, 0.6, 0.85)
        sd = np.minimum(sd, np.abs(r - R2) - w * U(rng, 0.2, 0.5) / 2)
    return {"sd": sd, "thick": max(w / 2, 0.03)}


def ring_spiked(rng, x, y, m):
    r, th = polar(x, y)
    R = U(rng, 0.4, 0.62)
    w = U(rng, 0.03, 0.1)
    n = int(rng.integers(8, 28))
    L = U(rng, 0.12, 0.3)
    jitter = rng.uniform(0.4, 1.0, n)
    sec = (th / TAU + 0.5) * n
    i = np.floor(sec).astype(int) % n
    f = sec - np.floor(sec)
    spike = (1 - np.abs(f - 0.5) * 2) ** U(rng, 1.5, 4) * L * jitter[i]
    outward = rng.random() < 0.7
    edge = R + w / 2 + (spike if outward else 0)
    inner = R - w / 2 - (0 if outward else spike)
    sd = np.maximum(r - edge, inner - r)
    return {"sd": sd, "thick": 0.06}


def ring_dashed(rng, x, y, m):
    r, th = polar(x, y)
    R = U(rng, 0.5, 0.8)
    w = U(rng, 0.03, 0.1)
    n = int(rng.integers(6, 40))
    duty = U(rng, 0.3, 0.75)
    sec = ((th / TAU + 0.5) * n) % 1
    sd = np.abs(r - R) - w / 2
    sd = np.where(sec > duty, np.maximum(sd, (sec - duty) * TAU * R / n), sd)
    if rng.random() < 0.5:
        R2 = R * U(rng, 0.55, 0.8)
        sd = np.minimum(sd, np.abs(r - R2) - w * 0.4)
    return {"sd": sd, "thick": 0.04}


def ripple(rng, x, y, m):
    r, th = polar(x, y)
    k = int(rng.integers(2, 6))
    R0 = U(rng, 0.25, 0.4)
    gap = (0.85 - R0) / k
    sd = np.full(x.shape, 9.0)
    for i in range(k):
        R = R0 + gap * i
        w = U(rng, 0.015, 0.05) * (1 - i / (k + 1))
        sd = np.minimum(sd, np.abs(r - R - 0.02 * ang_noise(th, 6, i + 5)) - w / 2)
    return {"sd": sd, "thick": 0.03}


# ================================================================ slashes
def _crescent_sd(x, y, cx, cy, R, a0, span, W, p=1.3, rough=0.0, seed=0):
    xx, yy = x - cx, y - cy
    r = np.hypot(xx, yy)
    th = np.arctan2(yy, xx)
    u = ((th - a0) % TAU) / span
    w = W * np.clip(np.sin(math.pi * np.clip(u, 0, 1)), 0, 1) ** p
    if rough:
        w = w * (1 + rough * (fbm(u * 6, r * 4, 1.0, 3, seed=seed) - 0.5) * 2)
    off = (r - R) - w * 0.25  # bulge outward like a sword arc
    sd = np.abs(off) - w / 2
    return np.where((u >= 0) & (u <= 1), sd, 9.0)


def slash(rng, x, y, m):
    R = U(rng, 0.5, 1.4)
    span = U(rng, 0.6, 2.2)
    span = min(span, 1.7 / R)
    a0 = U(rng, 0, TAU)
    mid = a0 + span / 2
    cx, cy = -math.cos(mid) * R * U(rng, 0.85, 1.05), -math.sin(mid) * R * U(rng, 0.85, 1.05)
    W = U(rng, 0.06, 0.3)
    sd = _crescent_sd(x, y, cx, cy, R, a0, span, W, U(rng, 0.8, 2.2), U(rng, 0, 0.5), int(rng.integers(1e6)))
    extra = int(rng.choice([0, 0, 1, 2, 3]))
    for k in range(extra):
        d = (k + 1) * U(rng, 0.08, 0.18)
        sd = np.minimum(sd, _crescent_sd(x, y, cx, cy, R - d, a0 + span * 0.08 * (k + 1), span * U(rng, 0.6, 0.9), W * U(rng, 0.3, 0.7)))
    return {"sd": sd, "thick": max(W / 2, 0.03)}


def slash_cross(rng, x, y, m):
    n = int(rng.choice([2, 2, 3, 4]))
    sd = np.full(x.shape, 9.0)
    base = U(rng, 0, math.pi)
    for i in range(n):
        a = base + i * math.pi / n + U(rng, -0.15, 0.15)
        L = U(rng, 0.7, 0.88)
        W = U(rng, 0.05, 0.16)
        xr, yr = rot(x, y, -a)
        u = (xr / L + 1) / 2
        w = W * np.clip(np.sin(math.pi * np.clip(u, 0, 1)), 0, 1) ** 1.2
        curve = U(rng, -0.15, 0.15) * (1 - (xr / L) ** 2)
        s = np.abs(yr - curve) - w / 2
        sd = np.minimum(sd, np.where(np.abs(xr) <= L, s, 9.0))
    return {"sd": sd, "thick": 0.05}


def claw(rng, x, y, m):
    n = int(rng.integers(3, 6))
    a = U(rng, -0.9, 0.9)
    xr, yr = rot(x, y, -a)
    sd = np.full(x.shape, 9.0)
    gap = U(rng, 0.14, 0.24)
    for i in range(n):
        off = (i - (n - 1) / 2) * gap
        L = U(rng, 0.55, 0.85)
        W = U(rng, 0.04, 0.1)
        u = (xr / L + 1) / 2
        w = W * np.clip(np.sin(math.pi * np.clip(u, 0, 1)), 0, 1) ** 1.6
        curve = U(rng, 0.05, 0.25) * (1 - (xr / L) ** 2)
        s = np.abs(yr - off - curve) - w / 2
        sd = np.minimum(sd, np.where(np.abs(xr) <= L, s, 9.0))
    return {"sd": sd, "thick": 0.04}


# ================================================================ sigils
def _glyph(rng, cx, cy, s, ang):
    """A real Elder Futhark rune for the sigil band, upright to the band."""
    import runes as R
    nm = R.NAMES[int(rng.integers(len(R.NAMES)))]
    return R.place(R.FUTHARK[nm], cx, cy, s * 1.1, ang, 0.9)


def sigil(rng, x, y, m):
    """Magic circle: concentric rings, a rune band, an inscribed star/polygon,
    ticks and an inner core motif; drawn with PIL then distance-fielded."""
    lw = U(rng, 0.008, 0.018)
    r_out = U(rng, 0.8, 0.9)
    band = U(rng, 0.1, 0.17)
    nstar = int(rng.choice([3, 4, 5, 6, 7, 8, 12]))
    skip = int(rng.choice([1, 2, 2, 3])) if nstar >= 5 else 1
    nglyph = int(rng.integers(12, 30))
    ticks = int(rng.choice([0, 24, 36, 48, 60, 72]))
    inner = int(rng.integers(0, 4))

    def draw(dr, P):
        W = max(1, int(lw * m / 2))
        def circ(R, w=W):
            c = P((0, 0))
            rr = R * m / 2
            dr.ellipse([c[0] - rr, c[1] - rr, c[0] + rr, c[1] + rr], outline=255, width=w)
        circ(r_out, int(W * 1.6))
        circ(r_out - band)
        if rng.random() < 0.5:
            circ(r_out - band - 0.04)
        rm = r_out - band / 2
        for i in range(nglyph):
            a = TAU * i / nglyph
            for poly in _glyph(rng, math.cos(a) * rm, math.sin(a) * rm, band * 0.55, a - math.pi / 2):
                dr.line([P(p) for p in poly], fill=255, width=W, joint="curve")
        rs = r_out - band - 0.05
        verts = [(math.cos(TAU * i / nstar + math.pi / 2) * rs, math.sin(TAU * i / nstar + math.pi / 2) * rs) for i in range(nstar)]
        order = [(i * skip) % nstar for i in range(nstar + 1)]
        if math.gcd(nstar, skip) != 1:
            for st in range(math.gcd(nstar, skip)):
                o = [((st + i * skip) % nstar) for i in range(nstar // math.gcd(nstar, skip) + 1)]
                dr.line([P(verts[j]) for j in o], fill=255, width=W)
        else:
            dr.line([P(verts[j]) for j in order], fill=255, width=W)
        for t in range(ticks):
            a = TAU * t / ticks
            r0, r1 = r_out + 0.01, r_out + (0.05 if t % 6 == 0 else 0.025)
            dr.line([P((math.cos(a) * r0, math.sin(a) * r0)), P((math.cos(a) * r1, math.sin(a) * r1))], fill=255, width=W)
        for k in range(inner):
            ri = rs * U(rng, 0.2, 0.55)
            circ(ri)
            if rng.random() < 0.5:
                nn = int(rng.choice([3, 4, 6]))
                vv = [P((math.cos(TAU * i / nn) * ri, math.sin(TAU * i / nn) * ri)) for i in range(nn + 1)]
                dr.line(vv, fill=255, width=W)
        for i in range(nstar):
            if rng.random() < 0.6:
                v = verts[i]
                rr = 0.035 * m / 2
                c = P(v)
                dr.ellipse([c[0] - rr, c[1] - rr, c[0] + rr, c[1] + rr], outline=255, width=W)
    mask = raster(m, draw)
    return {"sd": mask_sd(mask), "thick": 0.02}


def rune(rng, x, y, m):
    """Real runes (Elder Futhark). The variant index picks the letter, so the
    24 variants are the 24 different runes; the seed picks the treatment:
    carved strokes, inside a ring with studs, cut through a stone tablet, a
    bind-rune of 2-3 letters, or a short rune word."""
    import runes as R
    idx = int(rng.integers(1e6))
    treat = rng.choice(["carved", "carved", "ring", "stone", "bind", "word"])
    lw = U(rng, 0.05, 0.09)
    nm = R.NAMES[INDEX % len(R.NAMES)]

    def strokes_sd(strokes, w):
        sd = np.full(x.shape, 9.0)
        for poly in strokes:
            sd = np.minimum(sd, path_sd(x, y, poly, w, w * U(rng, 0.65, 1.0)))
        return sd

    if treat == "word":
        names = [R.NAMES[int(rng.integers(24))] for _ in range(int(rng.integers(2, 4)))]
        k = len(names)
        h = 1.0 if k == 2 else 0.8
        sd = np.full(x.shape, 9.0)
        for j, n2 in enumerate(names):
            cx = (j - (k - 1) / 2) * h * 0.62
            sd = np.minimum(sd, strokes_sd(R.place(R.FUTHARK[n2], cx, 0, h, 0, 0.9), lw * 0.75))
        if rng.random() < 0.6:
            wdt = k * h * 0.31 + 0.12
            sd = np.minimum(sd, np.minimum(np.abs(y - h * 0.62) - 0.012, np.abs(y + h * 0.62) - 0.012) + np.where(np.abs(x) < wdt, 0, 9))
        return {"sd": sd, "thick": 0.04}
    if treat == "bind":
        names = [nm] + [R.NAMES[int(rng.integers(24))] for _ in range(int(rng.integers(1, 3)))]
        sd = strokes_sd(R.place(R.bind(names), 0, 0, 1.45, 0, 1.0), lw)
        return {"sd": sd, "thick": 0.04}
    sd_r = strokes_sd(R.place(R.FUTHARK[nm], 0, 0, 1.25 if treat != "carved" else 1.55, 0, 1.0), lw)
    if treat == "carved":
        return {"sd": sd_r, "thick": 0.04}
    if treat == "ring":
        r = np.hypot(x, y)
        R0 = U(rng, 0.78, 0.86)
        sd = np.minimum(sd_r, np.abs(r - R0) - U(rng, 0.012, 0.03))
        k = int(rng.choice([0, 4, 6, 8]))
        for j in range(k):
            a = 2 * math.pi * j / k + math.pi / 2
            sd = np.minimum(sd, np.hypot(x - math.cos(a) * R0, y - math.sin(a) * R0) - 0.035)
        return {"sd": sd, "thick": 0.03}
    # stone tablet with the rune cut through it
    k = int(rng.integers(6, 10))
    pts = []
    for j in range(k):
        a = 2 * math.pi * j / k + math.pi / k
        rr = U(rng, 0.78, 0.88)
        pts.append((math.cos(a) * rr * 0.72, math.sin(a) * rr))
    stone = mask_sd(raster(m, lambda dr, P: dr.polygon([P(p) for p in pts], fill=255)))
    sd = np.maximum(stone, -(sd_r - 0.004))
    return {"sd": sd, "thick": 0.08}


def hex_grid(rng, x, y, m):
    s = U(rng, 0.08, 0.2)
    lw = U(rng, 0.008, 0.03)
    q = (x * math.sqrt(3) / 3 - y / 3) / s
    rr = (2 * y / 3) / s
    # cube round to nearest hex centre
    cx, cz = q, rr
    cy = -cx - cz
    rx, ry, rz = np.round(cx), np.round(cy), np.round(cz)
    dx, dy, dz = np.abs(rx - cx), np.abs(ry - cy), np.abs(rz - cz)
    rx = np.where((dx > dy) & (dx > dz), -ry - rz, rx)
    rz = np.where(~((dx > dy) & (dx > dz)) & ~(dy > dz), -rx - ry, rz)
    hx = s * math.sqrt(3) * (rx + rz / 2)
    hy = s * 1.5 * rz
    lx, ly = np.abs(x - hx), np.abs(y - hy)
    edge = np.maximum(lx * math.sqrt(3) / 2 + ly / 2, ly) - s * math.sqrt(3) / 2 * 0.98
    sd = np.abs(edge) - lw
    r = np.hypot(x, y)
    R = U(rng, 0.7, 0.88)
    sd = np.maximum(sd, r - R)
    if rng.random() < 0.6:
        sd = np.minimum(sd, np.abs(r - R) - lw * 1.5)
    return {"sd": sd, "thick": 0.02}


# ================================================================ elements
def _flame_sd(rng_vals, x, y, k=1.0):
    """One flame silhouette, scaled by k toward its base (for nested cores)."""
    base_y, bw, bh, tongues, flicks, seed, rough = rng_vals
    xs, ys = x / k, (y - base_y) / k + base_y
    sd = np.hypot(xs / bw, (ys - base_y) / bh) - 1.0
    sd = sd * min(bw, bh)
    for (rx, h, W, bend, freq, ph, lean) in tongues:
        pts = []
        for i in range(14):
            t = i / 13
            px = rx + bend * math.sin(t * math.pi * freq + ph) * t + lean * t * t
            py = base_y + bh * 0.3 + h * t
            pts.append((px, py))
        sd = smin(sd, path_sd(xs, ys, pts, W, 0.006), 0.06)
    for (fx, fy, fr) in flicks:
        sd = np.minimum(sd, smin(np.hypot(xs - fx, ys - fy) - fr, path_sd(xs, ys, [(fx, fy), (fx, fy + fr * 2.6)], fr * 1.6, 0.004), 0.02))
    nz = fbm(xs * 5 + seed, ys * 5 - seed, 1.0, 3, seed=seed) - 0.5
    return sd + nz * rough * np.clip(ys - base_y, 0, None)


def flame(rng, x, y, m):
    """A real cel flame: rounded base, 2-6 tongues licking upward with an
    S-bend and taper, detached flickers above, and nested middle/core layers
    (levels) so cel reads outer / middle / core and "hot" colours by layer."""
    base_y = U(rng, -0.72, -0.55)
    bw, bh = U(rng, 0.17, 0.28), U(rng, 0.17, 0.26)
    n = int(rng.integers(2, 7))
    tongues = []
    for j in range(n):
        centre = j == 0
        rx = 0.0 if centre else U(rng, -bw * 0.8, bw * 0.8)
        h = U(rng, 0.95, 1.45) if centre else U(rng, 0.45, 1.05)
        W = U(rng, 0.3, 0.46) if centre else U(rng, 0.1, 0.24)
        tongues.append((rx, h, W, U(rng, 0.04, 0.16) * rng.choice([-1, 1]), U(rng, 0.8, 2.2), U(rng, 0, 6.3), U(rng, -0.25, 0.25) - rx * 0.3))
    flicks = []
    for _ in range(int(rng.integers(0, 4))):
        t = tongues[int(rng.integers(len(tongues)))]
        flicks.append((t[0] + U(rng, -0.15, 0.15), base_y + bh * 0.3 + t[1] + U(rng, 0.05, 0.22), U(rng, 0.025, 0.06)))
    seed = int(rng.integers(1e6))
    vals = (base_y, bw, bh, tongues, flicks, seed, U(rng, 0.02, 0.09))
    sd = _flame_sd(vals, x, y)
    mid = _flame_sd(vals, x, y, U(rng, 0.62, 0.74))
    core = _flame_sd(vals, x, y, U(rng, 0.32, 0.45))
    levels = np.where(core < 0, 1.0, np.where(mid < 0, 0.78, 0.55))
    return {"sd": sd, "thick": 0.1, "levels": levels}


def droplet(rng, x, y, m):
    n = int(rng.choice([1, 1, 1, 3, 5]))
    sd = np.full(x.shape, 9.0)
    for i in range(n):
        s = U(rng, 0.35, 0.55) if n == 1 else U(rng, 0.12, 0.28)
        cx, cy = (0, -0.1) if n == 1 else (U(rng, -0.6, 0.6), U(rng, -0.6, 0.5))
        a = U(rng, -0.4, 0.4)
        xx, yy = rot(x - cx, y - cy, -a)
        r = np.hypot(xx, yy + s * 0.3)
        cone = np.maximum(np.abs(xx) * 1.6 + (yy - s * 1.4) * 0.9, -yy)
        sd = np.minimum(sd, smin(r - s, cone * 0.6, 0.15 * s))
    return {"sd": sd, "thick": 0.1}


def splash(rng, x, y, m):
    r, th = polar(x, y)
    n = int(rng.integers(6, 16))
    sd = r - U(rng, 0.18, 0.32) - 0.05 * ang_noise(th, 7, int(rng.integers(1e6)))
    for i in range(n):
        a = U(rng, 0, TAU)
        L = U(rng, 0.35, 0.8)
        w = U(rng, 0.03, 0.08)
        tip = (math.cos(a) * L, math.sin(a) * L)
        sd = smin(sd, path_sd(x, y, [(0, 0), tip], w, w * 0.3), 0.05)
        if rng.random() < 0.7:
            d = L + U(rng, 0.05, 0.12)
            rr = U(rng, 0.02, 0.05)
            sd = np.minimum(sd, np.hypot(x - math.cos(a) * d, y - math.sin(a) * d) - rr)
    return {"sd": sd, "thick": 0.07}


def leaf(rng, x, y, m):
    a = U(rng, -1, 1)
    xx, yy = rot(x, y, -a)
    L = U(rng, 0.7, 0.88)
    W = U(rng, 0.2, 0.42)
    u = xx / L
    prof = W * np.clip(1 - u ** 2, 0, 1) ** U(rng, 0.6, 1.2) * (1 + 0.15 * np.sin(u * U(rng, 6, 14)))
    curve = U(rng, -0.2, 0.2) * (1 - u ** 2)
    sd = (np.abs(yy - curve) - prof) * 0.8
    sd = np.where(np.abs(u) <= 1, sd, 9.0)
    sd = np.minimum(sd, path_sd(xx, yy, [(-L * 1.15, 0), (-L, 0)], 0.04))
    vein = np.abs(yy - curve) < 0.012
    sd = np.where(vein & (sd < 0), 0.01, sd)
    return {"sd": sd, "thick": 0.06}


def snowflake(rng, x, y, m):
    r, th = polar(x, y)
    arms = 6
    L = U(rng, 0.72, 0.88)
    lw = U(rng, 0.025, 0.06)
    pts_branch = [(U(rng, 0.25, 0.75), U(rng, 0.1, 0.3), U(rng, 0.4, 1.0)) for _ in range(int(rng.integers(1, 4)))]
    sd = np.full(x.shape, 9.0)
    for k in range(arms):
        a = TAU * k / arms + math.pi / 2
        c, s = math.cos(a), math.sin(a)
        sd = np.minimum(sd, path_sd(x, y, [(0, 0), (c * L, s * L)], lw, lw * 0.4))
        for (t, bl, ang) in pts_branch:
            bx, by = c * L * t, s * L * t
            for sg in (-1, 1):
                b = a + sg * ang
                sd = np.minimum(sd, path_sd(x, y, [(bx, by), (bx + math.cos(b) * bl, by + math.sin(b) * bl)], lw * 0.8, lw * 0.3))
    sd = np.minimum(sd, r - U(rng, 0.05, 0.14))
    return {"sd": sd, "thick": 0.03}


def bolt(rng, x, y, m):
    def jag(p0, p1, depth, disp):
        if depth == 0:
            return [p0, p1]
        mx, my = (p0[0] + p1[0]) / 2, (p0[1] + p1[1]) / 2
        dx, dy = p1[0] - p0[0], p1[1] - p0[1]
        L = math.hypot(dx, dy) + 1e-9
        o = rng.normal(0, disp) * L
        mid = (mx - dy / L * o, my + dx / L * o)
        return jag(p0, mid, depth - 1, disp)[:-1] + jag(mid, p1, depth - 1, disp)
    a = U(rng, -0.5, 0.5) + math.pi / 2
    p0 = (math.cos(a) * 0.85, math.sin(a) * 0.85)
    p1 = (-p0[0] * U(rng, 0.7, 1), -p0[1] * U(rng, 0.7, 1))
    main = jag(p0, p1, 6, U(rng, 0.15, 0.32))
    W = U(rng, 0.03, 0.08)
    sd = path_sd(x, y, main, W, W * 0.35)
    for _ in range(int(rng.integers(0, 5))):
        i = int(rng.integers(1, len(main) - 2))
        q = main[i]
        b = a + math.pi + U(rng, -1.1, 1.1)
        L = U(rng, 0.2, 0.5)
        end = (np.clip(q[0] + math.cos(b) * L, -0.85, 0.85), np.clip(q[1] + math.sin(b) * L, -0.85, 0.85))
        sd = np.minimum(sd, path_sd(x, y, jag(q, end, 4, 0.3), W * 0.5, W * 0.15))
    return {"sd": sd, "thick": 0.03}


def wind_curl(rng, x, y, m):
    n = int(rng.integers(1, 5))
    sd = np.full(x.shape, 9.0)
    for k in range(n):
        cx, cy = U(rng, -0.3, 0.3), U(rng, -0.4, 0.4)
        R = U(rng, 0.12, 0.3)
        pts = []
        L = U(rng, 0.6, 1.4)
        ang0 = U(rng, -0.3, 0.3)
        for i in range(48):
            t = i / 47
            if t < 0.6:
                px = -0.85 + t / 0.6 * L
                py = cy + math.sin(t * 6 + k) * 0.03
            else:
                s = (t - 0.6) / 0.4 * U(rng, 4, 6)
                rr = R * (1 - (t - 0.6) / 0.4 * 0.7)
                px = -0.85 + L + math.sin(s) * rr
                py = cy + rr - math.cos(s) * rr
            pts.append(rot(np.array(px), np.array(py), ang0))
        pts = [(float(a), float(b)) for a, b in pts]
        W = U(rng, 0.02, 0.06)
        sd = np.minimum(sd, path_sd(x, y, pts, W, W * 0.2))
    return {"sd": sd, "thick": 0.03}


def bubbles(rng, x, y, m):
    n = int(rng.integers(1, 12))
    sd = np.full(x.shape, 9.0)
    for _ in range(n):
        rr = U(rng, 0.08, 0.4) if n < 4 else U(rng, 0.05, 0.22)
        cx, cy = U(rng, -0.85 + rr, 0.85 - rr), U(rng, -0.85 + rr, 0.85 - rr)
        d = np.hypot(x - cx, y - cy)
        ring_ = np.abs(d - rr) - rr * U(rng, 0.06, 0.15)
        hl = np.hypot(x - cx + rr * 0.4, y - cy - rr * 0.4) - rr * 0.18
        sd = np.minimum(sd, np.minimum(ring_, hl))
    return {"sd": sd, "thick": 0.02}


def tendril(rng, x, y, m):
    n = int(rng.integers(2, 7))
    sd = np.full(x.shape, 9.0)
    for k in range(n):
        a = TAU * k / n + U(rng, -0.3, 0.3)
        pts = [(0.0, 0.0)]
        L = U(rng, 0.55, 0.85)
        curl = U(rng, -2.5, 2.5)
        for i in range(1, 30):
            t = i / 29
            b = a + curl * t ** 2
            pts.append((math.cos(b) * L * t, math.sin(b) * L * t))
        W = U(rng, 0.05, 0.12)
        sd = smin(sd, path_sd(x, y, pts, W, 0.005), 0.05)
    sd = smin(sd, np.hypot(x, y) - U(rng, 0.1, 0.2), 0.08)
    return {"sd": sd, "thick": 0.05}


def rays(rng, x, y, m):
    r, th = polar(x, y)
    n = int(rng.integers(6, 30))
    seed = int(rng.integers(1e6))
    sec = (th / TAU + 0.5) * n
    f = np.abs((sec % 1) - 0.5) * 2
    L = 0.55 + 0.3 * (fbm(np.floor(sec), np.zeros_like(sec), 1.0, 1, seed=seed) - 0.5) * 2
    width = U(rng, 0.2, 0.55)
    sd = np.maximum((f - width) * 0.3 * np.maximum(r, 0.05), r - L)
    sd = np.minimum(sd, r - U(rng, 0.08, 0.2))
    return {"sd": sd, "thick": 0.05}


def rock_chunk(rng, x, y, m):
    k = int(rng.integers(5, 10))
    pts = []
    for i in range(k):
        a = TAU * i / k + U(rng, -0.25, 0.25)
        rr = U(rng, 0.45, 0.8)
        pts.append((math.cos(a) * rr, math.sin(a) * rr))
    mask = raster(m, lambda dr, P: dr.polygon([P(p) for p in pts], fill=255))
    sd = mask_sd(mask)
    # facet shading: split into planes from a random interior point
    c = (U(rng, -0.15, 0.15), U(rng, -0.15, 0.15))
    th = np.arctan2(y - c[1], x - c[0])
    facet = np.floor((th + math.pi) / TAU * k)
    shade = 0.35 + 0.65 * ((facet * 0.37 + 0.2) % 1)
    return {"sd": sd, "thick": 0.1, "shade": shade * np.clip(-sd / 0.05, 0, 1)}


# ================================================================ impacts
def starburst(rng, x, y, m):
    r, th = polar(x, y)
    n = int(rng.integers(7, 22))
    Lr = rng.uniform(0.45, 1.0, n)
    sec = (th / TAU + 0.5) * n
    i = np.floor(sec).astype(int) % n
    f = sec - np.floor(sec)
    tri = np.abs(f - 0.5) * 2
    outer = 0.3 + (0.88 - 0.3) * Lr[i] * (1 - tri) ** U(rng, 0.8, 2.5)
    inner = U(rng, 0.22, 0.4)
    edge = np.maximum(outer, inner)
    sd = (r - edge) * 0.7
    if rng.random() < 0.4:
        sd = np.maximum(sd, U(rng, 0.08, 0.2) - r)
    return {"sd": sd, "thick": 0.12}


def comic_burst(rng, x, y, m):
    n = int(rng.integers(9, 20))
    pts = []
    for i in range(n * 2):
        a = TAU * i / (n * 2) + U(rng, -0.08, 0.08)
        rr = U(rng, 0.7, 0.88) if i % 2 == 0 else U(rng, 0.38, 0.55)
        pts.append((math.cos(a) * rr, math.sin(a) * rr * U(rng, 0.75, 1.0)))
    mask = raster(m, lambda dr, P: dr.polygon([P(p) for p in pts], fill=255))
    sd = mask_sd(mask)
    if rng.random() < 0.5:
        sd = np.maximum(sd, -(sd + U(rng, 0.05, 0.1)))
    return {"sd": sd, "thick": 0.08}


def speed_lines(rng, x, y, m):
    r, th = polar(x, y)
    n = int(rng.integers(20, 70))
    seed = int(rng.integers(1e6))
    sec = (th / TAU + 0.5) * n
    idx = np.floor(sec)
    f = sec - idx
    w = 0.12 + 0.3 * (fbm(idx * 1.7, np.zeros_like(idx), 1.0, 1, seed=seed))
    start = U(rng, 0.25, 0.5) + 0.25 * fbm(idx * 3.1, np.ones_like(idx), 1.0, 1, seed=seed + 1)
    on = fbm(idx * 5.3, np.zeros_like(idx) + 2, 1.0, 1, seed=seed + 2) > 0.35
    taper = np.clip((r - start) / 0.25, 0, 1)
    sd = (np.abs(f - 0.5) * 2 - w * taper) * r * 0.1
    sd = np.where(on & (r > start) & (r < 0.92), sd, 9.0)
    return {"sd": sd, "thick": 0.02}


def splat(rng, x, y, m):
    r, th = polar(x, y)
    seed = int(rng.integers(1e6))
    R = U(rng, 0.35, 0.5) + 0.12 * ang_noise(th, 9, seed)
    sd = r - R
    for _ in range(int(rng.integers(5, 14))):
        a = U(rng, 0, TAU)
        d = U(rng, 0.5, 0.82)
        rr = U(rng, 0.03, 0.1)
        cx, cy = math.cos(a) * d, math.sin(a) * d
        sd = smin(sd, np.hypot(x - cx, y - cy) - rr, 0.08 if d < 0.65 else 0.01)
    return {"sd": sd, "thick": 0.08}


def hit_cross(rng, x, y, m):
    a = U(rng, 0, math.pi / 4)
    xr, yr = rot(x, y, -a)
    L = U(rng, 0.7, 0.88)
    W = U(rng, 0.05, 0.12)
    def arm(u, v):
        return np.abs(v) - W * np.clip(1 - np.abs(u) / L, 0, 1) ** U(rng, 1, 2.5)
    sd = np.minimum(arm(xr, yr), arm(yr, xr))
    if rng.random() < 0.6:
        xr2, yr2 = rot(x, y, -a - math.pi / 4)
        sd = np.minimum(sd, np.minimum(np.abs(yr2) - W * 0.4 * np.clip(1 - np.abs(xr2) / (L * 0.6), 0, 1), np.abs(xr2) - W * 0.4 * np.clip(1 - np.abs(yr2) / (L * 0.6), 0, 1)))
    sd = np.minimum(sd, np.hypot(x, y) - W * 1.2)
    return {"sd": sd, "thick": 0.04}


# ================================================================ specks & wisps
def dot(rng, x, y, m):
    rr = U(rng, 0.2, 0.75)
    ax = U(rng, 0.6, 1.0)
    xr, yr = rot(x, y, -U(rng, 0, math.pi))
    sd = np.hypot(xr, yr / ax) - rr
    if rng.random() < 0.3:
        sd = np.abs(sd + rr * 0.3) - rr * 0.3
    return {"sd": sd, "thick": rr}


def speck_cluster(rng, x, y, m):
    n = int(rng.integers(5, 40))
    sd = np.full(x.shape, 9.0)
    for _ in range(n):
        rr = abs(rng.normal(0.035, 0.025)) + 0.008
        cx, cy = rng.normal(0, 0.35, 2).clip(-0.85, 0.85)
        sd = np.minimum(sd, np.hypot(x - cx, y - cy) - rr)
    return {"sd": sd, "thick": 0.02}


def streak(rng, x, y, m):
    a = U(rng, 0, math.pi)
    xr, yr = rot(x, y, -a)
    L = U(rng, 0.6, 0.9)
    W = U(rng, 0.02, 0.12)
    u = xr / L
    head = U(rng, 0.3, 0.8)
    w = W * np.where(u > head, np.sqrt(np.clip(1 - ((u - head) / (1 - head)) ** 2, 0, 1)), np.clip((u + 1) / (head + 1), 0, 1) ** 1.5)
    sd = np.abs(yr) - w
    sd = np.where(np.abs(u) <= 1, sd, 9.0)
    return {"sd": sd, "thick": 0.02}


def wisp(rng, x, y, m):
    sd = np.full(x.shape, 9.0)
    for k in range(int(rng.integers(1, 4))):
        pts = []
        a0 = U(rng, 0, TAU)
        amp = U(rng, 0.1, 0.35)
        fr = U(rng, 1.0, 3.0)
        for i in range(40):
            t = i / 39
            px = -0.8 + 1.6 * t
            py = amp * math.sin(t * fr * math.pi + a0) * (1 - abs(t - 0.5))
            pts.append(rot(np.array(px), np.array(py), U(rng, -0.1, 0.1) + k * 0.3))
        pts = [(float(p[0]), float(p[1])) for p in pts]
        W = U(rng, 0.06, 0.14)
        prof = path_sd(x, y, pts[:20], 0.004, W) if rng.random() < 0.5 else path_sd(x, y, pts, W, 0.004)
        sd = np.minimum(sd, prof)
    return {"sd": sd, "thick": 0.03}


def ember(rng, x, y, m):
    r, th = polar(x, y)
    R = U(rng, 0.3, 0.6) * (1 + 0.35 * ang_noise(th, int(rng.integers(3, 7)), int(rng.integers(1e6))))
    xr, yr = rot(x, y, -U(rng, 0, TAU))
    sd = np.hypot(xr * U(rng, 0.8, 1.6), yr) - R
    return {"sd": sd, "thick": 0.15}


# ================================================================ shards
def shard(rng, x, y, m):
    n = int(rng.choice([1, 1, 2, 3, 5]))
    sd = np.full(x.shape, 9.0)
    shade = np.zeros(x.shape)
    for k in range(n):
        L = U(rng, 0.55, 0.85) if n == 1 else U(rng, 0.25, 0.55)
        W = L * U(rng, 0.15, 0.4)
        a = U(rng, 0, TAU)
        cx, cy = (0, 0) if n == 1 else (U(rng, -0.4, 0.4), U(rng, -0.4, 0.4))
        tip_off = U(rng, -0.3, 0.3)
        poly = [(-L, U(rng, -0.3, 0.3) * W), (-L * 0.3, W), (L, tip_off * W), (-L * 0.1, -W * U(rng, 0.6, 1.0))]
        pts = []
        for px, py in poly:
            qx, qy = rot(np.array(px), np.array(py), a)
            pts.append((float(qx) + cx, float(qy) + cy))
        mask = raster(m, lambda dr, P, pts=pts: dr.polygon([P(p) for p in pts], fill=255))
        s = mask_sd(mask)
        ridge_x, ridge_y = rot(x - cx, y - cy, -a)
        side = (ridge_y > tip_off * W * (ridge_x + L) / (2 * L)).astype(float)
        shade = np.where(s < sd, 0.45 + 0.5 * side, shade)
        sd = np.minimum(sd, s)
    return {"sd": sd, "thick": 0.05, "shade": shade * np.clip(-sd / 0.03, 0, 1)}


def glass(rng, x, y, m):
    n = int(rng.integers(4, 12))
    sd = np.full(x.shape, 9.0)
    for _ in range(n):
        cx, cy = rng.normal(0, 0.35, 2).clip(-0.6, 0.6)
        s = U(rng, 0.06, 0.2)
        k = 3 if rng.random() < 0.7 else 4
        pts = [(cx + math.cos(TAU * i / k + U(rng, -0.4, 0.4)) * s * U(rng, 0.6, 1.4), cy + math.sin(TAU * i / k + U(rng, -0.4, 0.4)) * s * U(rng, 0.6, 1.4)) for i in range(k)]
        sd = np.minimum(sd, mask_sd(raster(m, lambda dr, P, pts=pts: dr.polygon([P(p) for p in pts], fill=255))))
    return {"sd": sd, "thick": 0.03}


# ================================================================ flares & stars
def star(rng, x, y, m):
    r, th = polar(x, y)
    n = int(rng.choice([4, 4, 5, 5, 6, 8]))
    inner = U(rng, 0.15, 0.5)
    R = U(rng, 0.7, 0.88)
    rot0 = U(rng, 0, TAU / n)
    sec = ((th + rot0) / TAU * n) % 1
    f = np.abs(sec - 0.5) * 2
    concave = U(rng, 0.6, 1.8)
    edge = inner + (R - inner) * (1 - f) ** concave
    sd = (r - edge) * 0.7
    if rng.random() < 0.3:
        sd = np.maximum(sd, -(sd + 0.06))
    return {"sd": sd, "thick": 0.1}


def flare(rng, x, y, m):
    r, th = polar(x, y)
    n = int(rng.choice([4, 6, 8, 12]))
    sd = np.hypot(x, y) - U(rng, 0.05, 0.14)
    for k in range(n):
        a = TAU * k / n + U(rng, -0.05, 0.05)
        L = U(rng, 0.45, 0.88) * (1 if k % 2 == 0 else U(rng, 0.4, 0.8))
        xr, yr = rot(x, y, -a)
        w = U(rng, 0.008, 0.03) * np.clip(1 - xr / L, 0, 1) ** 1.5
        sd = np.minimum(sd, np.where((xr > 0) & (xr < L), np.abs(yr) - w, 9.0))
    if rng.random() < 0.4:
        sd = np.minimum(sd, np.abs(r - U(rng, 0.3, 0.6)) - 0.006)
    return {"sd": sd, "thick": 0.02}


def anamorphic(rng, x, y, m):
    a = U(rng, -0.2, 0.2)
    xr, yr = rot(x, y, -a)
    L = U(rng, 0.75, 0.9)
    W = U(rng, 0.01, 0.05)
    sd = np.abs(yr) - W * np.clip(1 - (xr / L) ** 2, 0, 1) ** 2
    sd = np.minimum(sd, np.hypot(xr, yr * U(rng, 1, 2)) - U(rng, 0.06, 0.18))
    return {"sd": sd, "thick": 0.02}


def bokeh(rng, x, y, m):
    k = int(rng.choice([5, 6, 7, 8, 0]))
    R = U(rng, 0.55, 0.85)
    if k:
        r, th = polar(x, y)
        ap = math.pi / k
        d = r * np.cos(((th + U(rng, 0, TAU)) % (2 * ap)) - ap)
        sd = d - R * math.cos(ap)
    else:
        sd = np.hypot(x, y) - R
    ring_ = rng.random() < 0.5
    if ring_:
        sd = np.abs(sd + 0.04) - U(rng, 0.02, 0.06)
    return {"sd": sd, "thick": 0.2 if not ring_ else 0.03}


# ================================================================ swirls
def swirl(rng, x, y, m):
    r, th = polar(x, y)
    arms = int(rng.integers(1, 6))
    tight = U(rng, 2.0, 7.0) * (1 if rng.random() < 0.5 else -1)
    phase = (th * arms + tight * np.log(r + 0.05) * arms) / TAU
    f = np.abs((phase % 1) - 0.5) * 2
    width = U(rng, 0.25, 0.6)
    sd = (f - width) * 0.15 * (r + 0.1)
    R = U(rng, 0.72, 0.88)
    sd = np.maximum(sd, r - R * (1 - 0.05 * ang_noise(th, 5, 3)))
    sd = np.maximum(sd, U(rng, 0.0, 0.12) - r)
    return {"sd": sd, "thick": 0.03}


def vortex(rng, x, y, m):
    sd = np.full(x.shape, 9.0)
    n = int(rng.integers(3, 9))
    for k in range(n):
        pts = []
        a0 = TAU * k / n
        R0 = U(rng, 0.6, 0.85)
        turns = U(rng, 0.5, 1.4) * (1 if rng.random() < 0.8 else -1)
        for i in range(40):
            t = i / 39
            rr = R0 * (1 - t) + 0.06
            a = a0 + turns * TAU * t
            pts.append((math.cos(a) * rr, math.sin(a) * rr))
        W = U(rng, 0.02, 0.07)
        sd = np.minimum(sd, path_sd(x, y, pts, W, 0.004))
    return {"sd": sd, "thick": 0.03}


# ================================================================ cracks
def crack(rng, x, y, m):
    segs = []
    def walk(p, a, L, depth, w):
        n = int(L / 0.06) + 1
        for _ in range(n):
            a += rng.normal(0, 0.35)
            q = (p[0] + math.cos(a) * 0.06, p[1] + math.sin(a) * 0.06)
            if abs(q[0]) > 0.86 or abs(q[1]) > 0.86:
                return
            segs.append((p, q, w))
            if depth < 3 and rng.random() < 0.12:
                walk(q, a + rng.choice([-1, 1]) * U(rng, 0.4, 1.0), L * 0.5, depth + 1, w * 0.6)
            p = q
            w *= 0.97
    k = int(rng.integers(3, 9))
    for i in range(k):
        walk((0, 0), TAU * i / k + U(rng, -0.3, 0.3), U(rng, 0.5, 0.9), 0, U(rng, 0.015, 0.04))
    if rng.random() < 0.5:
        for ring_r in (U(rng, 0.25, 0.4), U(rng, 0.5, 0.7)):
            for i in range(int(rng.integers(3, 8))):
                a = U(rng, 0, TAU)
                da = U(rng, 0.2, 0.6)
                segs.append(((math.cos(a) * ring_r, math.sin(a) * ring_r), (math.cos(a + da) * ring_r * 1.05, math.sin(a + da) * ring_r * 1.05), 0.01))

    def draw(dr, P):
        for p, q, w in segs:
            dr.line([P(p), P(q)], fill=255, width=max(1, int(w * m / 2)))
    sd = mask_sd(raster(m, draw))
    sd = np.minimum(sd, np.hypot(x, y) - U(rng, 0.03, 0.1))
    return {"sd": sd, "thick": 0.02}


def fissure(rng, x, y, m):
    pts = [(-0.85, 0.0)]
    a = U(rng, -0.3, 0.3)
    for i in range(1, 24):
        px = -0.85 + 1.7 * i / 23
        pts.append((px, pts[-1][1] + rng.normal(0, 0.05)))
    pts = [(float(rot(np.array(p[0]), np.array(p[1]), a)[0]), float(rot(np.array(p[0]), np.array(p[1]), a)[1])) for p in pts]
    W = U(rng, 0.04, 0.12)
    n = len(pts)
    sd = np.full(x.shape, 9.0)
    for i in range(n - 1):
        w = W * math.sin(math.pi * (i + 0.5) / (n - 1)) ** 0.7
        sd = np.minimum(sd, seg_sd(x, y, pts[i], pts[i + 1]) - w / 2)
    return {"sd": sd, "thick": 0.04}


# ================================================================ more
def smoke_puff(rng, x, y, m):
    seed = int(rng.integers(1e6))
    r = np.hypot(x * U(rng, 0.8, 1.2), y)
    n = fbm(x * 2.5 + seed, y * 2.5, 1.0, 5, seed=seed)
    f = np.clip(1.3 - r * U(rng, 1.4, 1.9) + (n - 0.5) * 1.2, 0, 1)
    lumps = int(rng.integers(3, 8))
    for _ in range(lumps):
        cx, cy = U(rng, -0.4, 0.4), U(rng, -0.35, 0.4)
        f = np.maximum(f, np.clip(1 - np.hypot(x - cx, y - cy) / U(rng, 0.2, 0.38), 0, 1) ** 0.7)
    return {"f": np.clip(f, 0, 1)}


def cloud(rng, x, y, m):
    seed = int(rng.integers(1e6))
    f = np.zeros(x.shape)
    for _ in range(int(rng.integers(4, 9))):
        cx, cy = U(rng, -0.55, 0.55), U(rng, -0.15, 0.25)
        f = np.maximum(f, np.clip(1 - np.hypot(x - cx, (y - cy) * 1.4) / U(rng, 0.2, 0.35), 0, 1))
    f = np.where(y < -0.25, f * np.clip(1 - (-0.25 - y) * 8, 0, 1), f)
    f = f * (0.85 + 0.3 * (fbm(x * 4, y * 4, 1.0, 3, seed=seed) - 0.5))
    return {"f": np.clip(f * 1.6, 0, 1)}


def orb(rng, x, y, m):
    R = U(rng, 0.3, 0.8)
    r = np.hypot(x, y)
    sd = r - R
    bands = int(rng.integers(0, 4))
    for b in range(bands):
        a = U(rng, 0, math.pi)
        xr, yr = rot(x, y, -a)
        sd = np.where((np.abs(yr - U(rng, -0.4, 0.4) * R) < R * 0.04) & (sd < 0), np.maximum(sd, 0.004), sd)
    if rng.random() < 0.35:
        sd = np.minimum(sd, np.abs(r - min(R * U(rng, 1.12, 1.3), 0.84)) - U(rng, 0.01, 0.03))
    hl = np.clip(1 - np.hypot(x + R * 0.35, y - R * 0.35) / (R * 0.5), 0, 1)
    rim = np.clip((r - R * 0.75) / (R * 0.25), 0, 1)
    shade = np.clip(0.4 + 0.6 * hl + 0.5 * rim, 0, 1) * (sd < 0)
    return {"sd": sd, "thick": 0.1, "shade": shade}


def chevron(rng, x, y, m):
    n = int(rng.integers(1, 4))
    a = rng.choice([0, math.pi / 2, math.pi, -math.pi / 2]) + U(rng, -0.1, 0.1)
    xr, yr = rot(x, y, -a)
    W = U(rng, 0.08, 0.18)
    sd = np.full(x.shape, 9.0)
    for i in range(n):
        off = (i - (n - 1) / 2) * U(rng, 0.3, 0.45)
        v = np.abs(yr) * U(rng, 0.6, 1.1) + (xr - off)
        s = np.abs(v) - W / 2
        sd = np.minimum(sd, np.where(np.abs(yr) < 0.6, s, 9.0))
    return {"sd": sd, "thick": 0.05}


def heart(rng, x, y, m):
    s = U(rng, 0.4, 0.8)
    xr, yr = rot(x, y, -U(rng, -0.5, 0.5))
    xx, yy = xr / (s * U(rng, 0.8, 1.2)), yr / s + 0.15
    q = (xx * xx + yy * yy - 0.6) ** 3 - xx * xx * yy ** 3
    sd = np.cbrt(q) * s * 0.5
    kind = int(rng.integers(0, 4))
    if kind == 1:
        sd = np.abs(sd + 0.04) - U(rng, 0.015, 0.05)
    elif kind == 2:
        crack = np.abs(xx + 0.15 * np.sign(np.sin(yy * 9))) < 0.05
        sd = np.where(crack, np.maximum(sd, 0.01), sd)
    elif kind == 3:
        xx2, yy2 = (xr - 0.35) / (s * 0.55), (yr - 0.3) / (s * 0.55) + 0.15
        q2 = (xx2 * xx2 + yy2 * yy2 - 0.6) ** 3 - xx2 * xx2 * yy2 ** 3
        sd = np.minimum(sd, np.cbrt(q2) * s * 0.3)
    return {"sd": sd, "thick": 0.1}


def petal(rng, x, y, m):
    n = int(rng.choice([1, 1, 3, 5]))
    sd = np.full(x.shape, 9.0)
    for k in range(n):
        a = U(rng, 0, TAU) if n == 1 else TAU * k / n
        xr, yr = rot(x, y, -a)
        L = U(rng, 0.5, 0.82)
        W = L * U(rng, 0.3, 0.55)
        u = xr / L
        prof = W * np.clip(np.sin(math.pi * np.clip(u, 0, 1)), 0, 1) ** 0.7 * (1 - 0.4 * np.clip(u - 0.85, 0, 1) * 6)
        s = np.where((u >= 0) & (u <= 1), np.abs(yr) - prof, 9.0)
        notch = np.hypot(xr - L, yr) - W * 0.25
        sd = np.minimum(sd, np.maximum(s, -notch))
    return {"sd": sd, "thick": 0.06}


def feather(rng, x, y, m):
    a = U(rng, -1.2, 1.2)
    xr, yr = rot(x, y, -a)
    L = U(rng, 0.75, 0.88)
    W = U(rng, 0.15, 0.3)
    u = xr / L
    prof = W * np.clip(1 - u ** 2, 0, 1) ** 0.6
    barbs = np.abs((((xr - np.abs(yr) * U(rng, 0.6, 1.2)) * U(rng, 18, 35)) % 1) - 0.5) > 0.42
    s = np.abs(yr) - prof
    sd = np.where(np.abs(u) <= 1, np.where(barbs & (np.abs(yr) > 0.02), np.maximum(s, 0.004), s), 9.0)
    sd = np.minimum(sd, path_sd(xr, yr, [(-L * 1.1, 0), (L, 0)], 0.02, 0.006))
    return {"sd": sd, "thick": 0.03}


def noise_mask(rng, x, y, m):
    seed = int(rng.integers(1e6))
    kind = rng.integers(0, 3)
    fr = U(rng, 1.5, 6)
    if kind == 0:
        f = fbm(x * fr + seed, y * fr, 1.0, 5, seed=seed)
    elif kind == 1:
        f = 1 - np.abs(fbm(x * fr, y * fr + seed, 1.0, 5, seed=seed) - 0.5) * 2
        f = f ** 3
    else:
        # cellular
        k = int(fr * 3)
        pts = rng.uniform(-1, 1, (k * k, 2))
        d = np.full(x.shape, 9.0)
        for p in pts:
            d = np.minimum(d, np.hypot(x - p[0], y - p[1]))
        f = np.clip(d * k * 0.9, 0, 1)
    r = np.hypot(x, y)
    vign = smooth(0.92, U(rng, 0.4, 0.75), r)
    return {"f": np.clip((f - 0.2) * 1.4, 0, 1) * vign}


def gradient(rng, x, y, m):
    kind = rng.integers(0, 3)
    r = np.hypot(x, y)
    if kind == 0:
        f = np.clip(1 - r / U(rng, 0.6, 0.9), 0, 1) ** U(rng, 0.5, 3)
    elif kind == 1:
        R = U(rng, 0.4, 0.7)
        f = np.clip(1 - np.abs(r - R) / U(rng, 0.08, 0.3), 0, 1) ** 1.5
    else:
        a = U(rng, 0, TAU)
        xr, _ = rot(x, y, -a)
        f = np.clip((xr + 0.9) / 1.8, 0, 1) ** U(rng, 0.6, 2.5) * smooth(0.92, 0.6, r)
    return {"f": f}


SPRITES = {
    # category: [(family fn, styles, n_variants per style)]
    "rings": [(ring, "cel soft glow ink", 12), (ring_spiked, "cel glow ink", 10), (ring_dashed, "cel glow", 10), (ripple, "cel soft glow", 8)],
    "slashes": [(slash, "cel soft glow ink", 16), (slash_cross, "cel glow ink", 10), (claw, "cel glow ink", 10)],
    "sigils": [(sigil, "cel glow", 22), (rune, "cel glow ink", 24), (hex_grid, "cel glow", 8)],
    "elements": [(flame, "cel hot soft glow ink", 12), (droplet, "cel soft glow", 6), (splash, "cel glow ink", 8), (leaf, "cel ink", 8),
                 (snowflake, "cel glow", 8), (bolt, "cel glow ink", 10), (wind_curl, "cel glow ink", 8), (bubbles, "cel glow", 6),
                 (tendril, "cel soft ink", 8), (rays, "soft glow", 8), (rock_chunk, "cel ink", 10)],
    "impacts": [(starburst, "cel soft glow ink", 10), (comic_burst, "cel glow ink", 10), (speed_lines, "cel glow", 10), (splat, "cel ink", 10), (hit_cross, "cel glow", 8)],
    "specks": [(dot, "cel soft glow", 8), (speck_cluster, "cel glow", 8), (streak, "cel soft glow", 8), (wisp, "soft glow ink", 8), (ember, "cel soft glow", 8)],
    "shards": [(shard, "cel glow ink", 14), (glass, "cel glow", 10)],
    "flares": [(flare, "soft glow", 12), (anamorphic, "soft glow", 8), (bokeh, "cel soft glow", 8)],
    "swirls": [(swirl, "cel soft glow ink", 10), (vortex, "cel glow ink", 10)],
    "stars": [(star, "cel soft glow ink", 10)],
    "cracks": [(crack, "cel glow ink", 12), (fissure, "cel glow ink", 8)],
    "smoke": [(smoke_puff, "soft cel ink", 14), (cloud, "soft cel", 10)],
    "shapes": [(orb, "cel soft glow", 8), (chevron, "cel glow ink", 8), (heart, "cel soft glow", 6), (petal, "cel soft ink", 8), (feather, "cel soft ink", 8)],
    "masks": [(noise_mask, "soft", 30), (gradient, "soft", 24)],
}
