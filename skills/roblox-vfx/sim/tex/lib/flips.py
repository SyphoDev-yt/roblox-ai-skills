"""Flipbook families. make(rng) fixes the variant's parameters and returns
frame(t, x, y, m) -> {"sd"| "f", "thick", ...} for t in [0, 1).
Loops (fire loops, portals, orbs) set "loop": True and are not eroded.
One-shots follow the measured timing: grow to a peak at t 0.13-0.33, erode
into pieces from ~t 0.4, gone by ~0.9 (texcore.erode applies that).
"""
import math

import numpy as np
from scipy import ndimage

from texcore import polar, rot, ang_noise, seg_sd, path_sd, raster, mask_sd, smin, fbm, smooth
import sprites as S

TAU = 2 * math.pi


def U(rng, a, b):
    return float(rng.uniform(a, b))


def ease_out(t, k=3):
    return 1 - (1 - min(max(t, 0), 1)) ** k


def grow(t, peak=0.25):
    return ease_out(min(t / peak, 1.0), 3)


# ================================================================ shockwaves
def shockwave(rng):
    R1 = U(rng, 0.7, 0.88)
    w0 = U(rng, 0.12, 0.3)
    k = int(rng.integers(4, 12))
    seed = int(rng.integers(1e6))
    wob = U(rng, 0, 0.05)
    double = rng.random() < 0.35
    def frame(t, x, y, m):
        r, th = polar(x, y)
        g = ease_out(t / 0.7, 3)
        R = 0.08 + (R1 - 0.08) * g
        w = w0 * (1 - 0.85 * smooth(0, 0.8, t)) + 0.01
        sd = np.abs(r - R - wob * ang_noise(th, k, seed)) - w / 2
        if double:
            sd = np.minimum(sd, np.abs(r - R * 0.7) - w * 0.3)
        return {"sd": sd, "thick": max(w / 2, 0.02), "erode_t0": 0.5}
    return frame


def shock_spiked(rng):
    n = int(rng.integers(10, 26))
    jit = rng.uniform(0.4, 1, n)
    L = U(rng, 0.15, 0.3)
    def frame(t, x, y, m):
        r, th = polar(x, y)
        g = ease_out(t / 0.6, 3)
        R = 0.1 + 0.55 * g
        sec = (th / TAU + 0.5) * n
        i = np.floor(sec).astype(int) % n
        f = sec - np.floor(sec)
        spike = (1 - np.abs(f - 0.5) * 2) ** 2.5 * L * jit[i] * (1 - 0.5 * t)
        w = 0.08 * (1 - 0.8 * t) + 0.01
        sd = np.maximum(r - (R + w / 2 + spike), (R - w / 2) - r)
        return {"sd": sd, "thick": 0.04}
    return frame


def ripple_fb(rng):
    k = int(rng.integers(1, 6))
    gap = U(rng, 0.06, 0.2)
    w0 = U(rng, 0.02, 0.12)
    wob = U(rng, 0, 0.06)
    seed = int(rng.integers(1e6))
    sq = U(rng, 0.45, 1.0)
    def frame(t, x, y, m):
        r, th = polar(x, y / sq)
        sd = np.full(x.shape, 9.0)
        for i in range(k):
            tt = t - i * gap
            if tt <= 0:
                continue
            R = 0.08 + 0.78 * ease_out(tt / 0.8, 2)
            w = w0 * (1 - tt) + 0.008
            sd = np.minimum(sd, np.abs(r - R - wob * ang_noise(th, 7, seed + i)) - w / 2)
        return {"sd": sd, "thick": 0.03, "erode_t0": 0.6}
    return frame


# ================================================================ impacts
def impact(rng):
    n = int(rng.integers(7, 18))
    Lr = rng.uniform(0.5, 1.0, n)
    sharp = U(rng, 1, 2.5)
    core = U(rng, 0.2, 0.35)
    def frame(t, x, y, m):
        r, th = polar(x, y)
        g = grow(t, U(rng, 0.15, 0.3) if False else 0.22)
        sec = (th / TAU + 0.5) * n
        i = np.floor(sec).astype(int) % n
        f = sec - np.floor(sec)
        outer = (core + (0.88 - core) * Lr[i] * (1 - np.abs(f - 0.5) * 2) ** sharp) * g
        sd = (r - np.maximum(outer, core * g)) * 0.7
        if t > 0.3:
            sd = np.maximum(sd, (0.6 * smooth(0.3, 0.9, t)) * 0.88 - r)
        return {"sd": sd, "thick": 0.1}
    return frame


def comic_pop(rng):
    n = int(rng.integers(9, 18))
    base = [(U(rng, 0.7, 0.88), U(rng, 0.35, 0.5), U(rng, -0.08, 0.08)) for _ in range(n)]
    def frame(t, x, y, m):
        s = grow(t, 0.15) * (1 + 0.05 * math.sin(t * 40))
        pts = []
        for i, (ro, ri, j) in enumerate(base):
            for k, rr in ((0, ro), (1, ri)):
                a = TAU * (2 * i + k) / (2 * n) + j
                pts.append((math.cos(a) * rr * s, math.sin(a) * rr * s))
        return {"sd": mask_sd(raster(m, lambda dr, P: dr.polygon([P(p) for p in pts], fill=255))), "thick": 0.06}
    return frame


def explosion(rng):
    seed = int(rng.integers(1e6))
    lumps = [(U(rng, -0.35, 0.35), U(rng, -0.3, 0.35), U(rng, 0.25, 0.42)) for _ in range(int(rng.integers(4, 8)))]
    def frame(t, x, y, m):
        g = grow(t, 0.3)
        f = np.zeros(x.shape)
        for cx, cy, rr in lumps:
            rise = 0.25 * t
            f = np.maximum(f, np.clip(1 - np.hypot(x - cx * g, y - (cy * g + rise)) / (rr * g + 1e-3), 0, 1) ** 0.6)
        nz = fbm(x * 3 + seed, y * 3 - t * 2, 1.0, 4, seed=seed) - 0.5
        f = np.clip(f + nz * 0.6 * np.clip(f * 4, 0, 1), 0, 1)
        return {"f": f, "hollow": 0.0}
    return frame


# ================================================================ fire
def fire_loop(rng):
    seed = int(rng.integers(1e6))
    w = U(rng, 0.22, 0.65)
    h = U(rng, 0.8, 1.6)
    tongues = U(rng, 1.5, 7)
    def frame(t, x, y, m):
        yy = (y + 0.82) / h
        # scrolling noise that loops: sample a circle in a third noise axis
        cx, cy = math.cos(TAU * t) * 1.5, math.sin(TAU * t) * 1.5
        nz = fbm(x * tongues + cx, y * 2.5 - cy, 1.0, 4, seed=seed)
        nz2 = fbm(x * 7 - cy, y * 6 + cx, 1.0, 3, seed=seed + 3)
        bend = (nz - 0.5) * 0.45 * yy
        env = np.clip(1 - np.abs(x + bend) / (w * np.clip(1.15 - yy, 0.02, None) ** 0.8), 0, 1)
        base = np.sqrt(np.clip(yy / 0.18, 0, 1))
        f = env * base * (1.25 - yy) + (nz2 - 0.5) * 0.9 * yy * np.clip(env * 3, 0, 1)
        f = np.where((yy >= 0) & (yy <= 1.1), f, 0.0)
        return {"sd": (0.33 - f) * 0.35, "thick": 0.12, "loop": True}
    return frame


def fire_burst(rng):
    seed = int(rng.integers(1e6))
    n = int(rng.integers(3, 7))
    tongues = [(U(rng, -0.4, 0.4), U(rng, 0.5, 1.3), U(rng, 0.15, 0.3)) for _ in range(n)]
    def frame(t, x, y, m):
        g = grow(t, 0.25)
        sd = np.full(x.shape, 9.0)
        for ox, hh, ww in tongues:
            h = hh * g
            yy = (y + 0.75 - t * 0.4) / max(h, 1e-3)
            prof = np.where(yy < 0.3, np.sqrt(np.clip(1 - ((yy - 0.3) / 0.3) ** 2, 0, 1)), np.clip(1 - (yy - 0.3) / 0.7, 0, 1) ** 1.2)
            s = (np.abs(x - ox * g) / ww - prof) * ww
            sd = smin(sd, np.where((yy >= 0) & (yy <= 1), s, 9.0), 0.08)
        nz = fbm(x * 4 + seed, y * 4 - t * 3, 1.0, 4, seed=seed) - 0.5
        return {"sd": sd + nz * 0.08, "thick": 0.12, "erode_t0": 0.35}
    return frame


def fireball_loop(rng):
    seed = int(rng.integers(1e6))
    R = U(rng, 0.38, 0.55)
    def frame(t, x, y, m):
        r, th = polar(x, y)
        cx, cy = math.cos(TAU * t), math.sin(TAU * t)
        nz = fbm(x * 3 + cx, y * 3 + cy, 1.0, 4, seed=seed) - 0.5
        tail = np.clip(y, 0, 1) * 0.5
        sd = r - (R + tail * (1 + nz * 2)) - nz * 0.18
        return {"sd": sd, "thick": 0.2, "loop": True}
    return frame


# ================================================================ smoke & dust
def smoke_puff_fb(rng):
    seed = int(rng.integers(1e6))
    lumps = [(U(rng, -0.35, 0.35), U(rng, -0.3, 0.3), U(rng, 0.25, 0.42)) for _ in range(int(rng.integers(4, 8)))]
    rise = U(rng, 0.1, 0.45)
    def frame(t, x, y, m):
        g = 0.35 + 0.65 * grow(t, 0.45)
        f = np.zeros(x.shape)
        for cx, cy, rr in lumps:
            f = np.maximum(f, np.clip(1 - np.hypot(x - cx * g, y - cy * g - rise * t) / (rr * g), 0, 1) ** 0.7)
        nz = fbm(x * 2.5 + seed, y * 2.5 - t, 1.0, 4, seed=seed) - 0.5
        f = np.clip(f * (1 - 0.4 * t) + nz * 0.5 * np.clip(f * 4, 0, 1), 0, 1)
        return {"f": f, "erode_t0": 0.35}
    return frame


def dust_ground(rng):
    seed = int(rng.integers(1e6))
    Wm, Hm = U(rng, 0.45, 0.88), U(rng, 0.15, 0.55)
    lean, drift = U(rng, -0.35, 0.35), U(rng, -0.3, 0.3)
    lumps = [(U(rng, -0.7, 0.7), U(rng, 0.0, 0.6), U(rng, 0.12, 0.3)) for _ in range(int(rng.integers(0, 6)))]
    peak = U(rng, 0.2, 0.5)
    def frame(t, x, y, m):
        g = grow(t, peak)
        W = 0.15 + (Wm - 0.15) * g
        H = 0.08 + Hm * g
        xs = x - drift * t - lean * np.clip(y + 0.45, 0, None)
        yy = (y + 0.45) / H
        f = np.clip(1 - (xs / W) ** 2 - (np.clip(yy, 0, None) - 0.4) ** 2 * 0.8, 0, 1) * (yy > -0.2)
        for (lx, ly, lr) in lumps:
            f = np.maximum(f, np.clip(1 - np.hypot(xs - lx * W, y + 0.45 - ly * H * 1.5) / (lr * g + 1e-3), 0, 1) ** 0.7)
        nz = fbm(x * 4 + seed + t * 2, y * 4, 1.0, 4, seed=seed) - 0.5
        return {"f": np.clip(f * 1.4 + nz * 0.7 * np.clip(f * 4, 0, 1), 0, 1), "erode_t0": 0.4}
    return frame


def plume_loop(rng):
    seed = int(rng.integers(1e6))
    def frame(t, x, y, m):
        yy = (y + 0.85) / 1.7
        w = 0.12 + 0.3 * yy
        cx, cy = math.cos(TAU * t) * 1.3, math.sin(TAU * t) * 1.3
        nz = fbm(x * 3 + cx, y * 2 + cy, 1.0, 4, seed=seed) - 0.5
        f = np.clip(1 - np.abs(x + nz * 0.3) / w, 0, 1) * np.clip(1 - yy, 0, 1) ** 0.5 * (yy > 0)
        f = np.clip(f * 1.5 + nz * 0.6 * np.clip(f * 4, 0, 1), 0, 1)
        return {"f": f, "loop": True}
    return frame


# ================================================================ lightning / electric
def lightning_fb(rng):
    seed0 = int(rng.integers(1e6))
    W = U(rng, 0.03, 0.07)
    vertical = rng.random() < 0.6
    def frame(t, x, y, m):
        r2 = np.random.default_rng(seed0 + int(t * 16))
        def jag(p0, p1, depth, disp):
            if depth == 0:
                return [p0, p1]
            mx, my = (p0[0] + p1[0]) / 2, (p0[1] + p1[1]) / 2
            dx, dy = p1[0] - p0[0], p1[1] - p0[1]
            L = math.hypot(dx, dy) + 1e-9
            o = r2.normal(0, disp) * L
            mid = (mx - dy / L * o, my + dx / L * o)
            return jag(p0, mid, depth - 1, disp)[:-1] + jag(mid, p1, depth - 1, disp)
        p0, p1 = ((0, 0.85), (r2.uniform(-0.3, 0.3), -0.85)) if vertical else ((-0.85, 0), (0.85, r2.uniform(-0.3, 0.3)))
        main = jag(p0, p1, 6, 0.22)
        fade = 1 - smooth(0.5, 0.95, t)
        sd = path_sd(x, y, main, W * (0.4 + 0.6 * fade), W * 0.3)
        for _ in range(int(r2.integers(1, 4))):
            q = main[int(r2.integers(2, len(main) - 2))]
            end = (float(np.clip(q[0] + r2.normal(0, 0.4), -0.85, 0.85)), float(np.clip(q[1] + r2.normal(0, 0.4), -0.85, 0.85)))
            sd = np.minimum(sd, path_sd(x, y, jag(q, end, 4, 0.3), W * 0.5, W * 0.1))
        if t > 0.85:
            sd = sd + 1.0
        return {"sd": sd, "thick": 0.03, "no_erode": True}
    return frame


def electric_orb(rng):
    seed0 = int(rng.integers(1e6))
    R = U(rng, 0.25, 0.4)
    def frame(t, x, y, m):
        r2 = np.random.default_rng(seed0 + int(t * 16))
        sd = np.hypot(x, y) - R * (1 + 0.05 * math.sin(t * TAU * 2))
        for _ in range(int(r2.integers(3, 7))):
            a = r2.uniform(0, TAU)
            pts = [(math.cos(a) * R, math.sin(a) * R)]
            L = r2.uniform(0.35, 0.55)
            for i in range(1, 8):
                aa = a + r2.normal(0, 0.25)
                rr = R + L * i / 7
                pts.append((math.cos(aa) * rr, math.sin(aa) * rr))
            sd = np.minimum(sd, path_sd(x, y, pts, 0.035, 0.006))
        return {"sd": sd, "thick": 0.05, "loop": True}
    return frame


# ================================================================ slashes
def slash_sweep(rng):
    R = U(rng, 0.65, 1.1)
    span = min(U(rng, 1.4, 2.6), 1.75 / R)
    a0 = U(rng, 0, TAU)
    mid = a0 + span / 2
    cx, cy = -math.cos(mid) * R * 0.95, -math.sin(mid) * R * 0.95
    W = U(rng, 0.18, 0.42)
    extra = int(rng.choice([0, 1, 2]))
    def frame(t, x, y, m):
        head = ease_out(t / 0.3, 3)
        tail = smooth(0.15, 0.85, t)
        s0, s1 = a0 + span * tail, a0 + span * head
        sp = max(s1 - s0, 1e-3)
        sd = S._crescent_sd(x, y, cx, cy, R, s0, sp, W * (1 - 0.5 * t), 1.0)
        for k in range(extra):
            sd = np.minimum(sd, S._crescent_sd(x, y, cx, cy, R - 0.12 * (k + 1), s0 + sp * 0.1, sp * 0.8, W * 0.4 * (1 - t)))
        return {"sd": sd, "thick": 0.06, "erode_t0": 0.5}
    return frame


def claw_sweep(rng):
    n = int(rng.integers(3, 6))
    a = U(rng, -0.9, 0.9)
    gap = U(rng, 0.14, 0.22)
    def frame(t, x, y, m):
        xr, yr = rot(x, y, -a)
        sd = np.full(x.shape, 9.0)
        head = ease_out(t / 0.25, 3) * 1.7 - 0.85
        tail = smooth(0.15, 0.85, t) * 1.7 - 0.85
        for i in range(n):
            off = (i - (n - 1) / 2) * gap
            ln = max(head - tail, 1e-3)
            u = (xr - tail) / ln
            w = 0.11 * np.clip(np.sin(math.pi * np.clip(u, 0, 1)), 0, 1) ** 1.3
            s = np.abs(yr - off - 0.15 * (1 - xr ** 2)) - w / 2
            sd = np.minimum(sd, np.where((u >= 0) & (u <= 1), s, 9.0))
        return {"sd": sd, "thick": 0.04, "no_erode": True}
    return frame


# ================================================================ water & wind
def water_splash(rng):
    n = int(rng.integers(3, 20))
    drops = [(U(rng, 0.3, 2.7), U(rng, 1.2, 2.8), U(rng, 0.03, 0.1)) for _ in range(n)]
    spikes = U(rng, 6, 24)
    crown_h = U(rng, 0.3, 0.95)
    bw0, bw1 = U(rng, 0.15, 0.4), U(rng, 0.2, 0.5)
    def frame(t, x, y, m):
        sd = np.full(x.shape, 9.0)
        base_w = bw0 + bw1 * grow(t, 0.4)
        crown = np.maximum(np.abs(x) - base_w, -(y + 0.7)) * 1.0
        crown = np.maximum(crown, (y + 0.7) - (0.1 + crown_h * grow(t, 0.3)) * (1 - t) * (0.55 + 0.45 * np.cos(x * spikes)))
        sd = np.minimum(sd, crown)
        for (ang, sp, rr) in drops:
            a = math.pi / 2 + (ang - 1.5) * 0.8
            vx, vy = math.cos(a) * sp, math.sin(a) * sp
            px, py = vx * t, -0.6 + vy * t - 2.0 * t * t
            if abs(px) < 0.86 and -0.86 < py < 0.86:
                sd = np.minimum(sd, path_sd(x, y, [(px - vx * 0.05, py - (vy - 4 * t) * 0.05), (px, py)], rr * 2, rr * 1.4))
        return {"sd": sd, "thick": 0.05, "erode_t0": 0.55}
    return frame


def wind_gust(rng):
    n = int(rng.integers(2, 6))
    lines = [(U(rng, -0.6, 0.6), U(rng, 0.03, 0.15), U(rng, 1, 3), U(rng, 0, TAU)) for _ in range(n)]
    def frame(t, x, y, m):
        sd = np.full(x.shape, 9.0)
        for (cy, amp, fr, ph) in lines:
            head = -0.85 + 1.7 * ease_out(t / 0.6, 2)
            tail = -0.85 + 1.7 * smooth(0.2, 0.95, t)
            pts = []
            for i in range(30):
                u = tail + (head - tail) * i / 29
                pts.append((u, cy + amp * math.sin(u * fr * math.pi + ph)))
            sd = np.minimum(sd, path_sd(x, y, pts, 0.004, 0.05))
        return {"sd": sd, "thick": 0.03, "no_erode": True}
    return frame


def tornado_loop(rng):
    k = int(rng.integers(4, 9))
    def frame(t, x, y, m):
        sd = np.full(x.shape, 9.0)
        for i in range(k):
            yy = -0.8 + 1.6 * i / (k - 1)
            R = 0.12 + 0.6 * (yy + 0.8) / 1.6
            ph = TAU * (t + i * 0.13)
            ex = R * math.cos(ph) * 0.15
            sd = np.minimum(sd, np.abs(np.hypot((x - ex) / R, (y - yy) / 0.08) - 1) * 0.06 - 0.012)
        return {"sd": sd, "thick": 0.02, "loop": True}
    return frame


# ================================================================ shards & sparks
def shatter(rng):
    n = int(rng.integers(6, 14))
    pieces = []
    for _ in range(n):
        a = U(rng, 0, TAU)
        pieces.append((a, U(rng, 0.6, 1.4), U(rng, 0.1, 0.22), U(rng, -8, 8), int(rng.choice([3, 4]))))
    def frame(t, x, y, m):
        sd = np.full(x.shape, 9.0)
        for (a, sp, s, spin, k) in pieces:
            d = sp * ease_out(t, 2) * 0.75
            cx, cy = math.cos(a) * d, math.sin(a) * d - 0.4 * t * t
            ang = spin * t
            pts = [(cx + math.cos(ang + TAU * i / k) * s, cy + math.sin(ang + TAU * i / k) * s * 0.6) for i in range(k)]
            pts = [(float(np.clip(p[0], -0.9, 0.9)), float(np.clip(p[1], -0.9, 0.9))) for p in pts]
            sd = np.minimum(sd, mask_sd(raster(m, lambda dr, P, pts=pts: dr.polygon([P(p) for p in pts], fill=255))))
        return {"sd": sd, "thick": 0.03, "erode_t0": 0.6}
    return frame


def sparks(rng):
    n = int(rng.integers(8, 24))
    parts = [(U(rng, 0, TAU), U(rng, 0.5, 1.4), U(rng, 0.02, 0.045)) for _ in range(n)]
    grav = U(rng, 0, 1.5)
    def frame(t, x, y, m):
        sd = np.full(x.shape, 9.0)
        for (a, sp, w) in parts:
            d = sp * ease_out(t, 2) * 0.8
            px, py = math.cos(a) * d, math.sin(a) * d - grav * t * t * 0.5
            vx, vy = math.cos(a) * sp * (1 - t) ** 2, math.sin(a) * sp * (1 - t) ** 2 - grav * t
            L = 0.04 + 0.15 * math.hypot(vx, vy)
            nrm = math.hypot(vx, vy) + 1e-6
            tail = (px - vx / nrm * L, py - vy / nrm * L)
            if abs(px) < 0.88 and abs(py) < 0.88:
                sd = np.minimum(sd, path_sd(x, y, [tail, (px, py)], 0.002, w * 2 * (1 - 0.7 * t)))
        return {"sd": sd, "thick": 0.02, "no_erode": True}
    return frame


def twinkle(rng):
    n = int(rng.choice([4, 4, 6, 8]))
    inner = U(rng, 0.08, 0.2)
    spin = U(rng, -1.5, 1.5)
    def frame(t, x, y, m):
        r, th = polar(x, y)
        s = math.sin(math.pi * t) ** 0.8
        sec = ((th + spin * t) / TAU * n) % 1
        f = np.abs(sec - 0.5) * 2
        edge = (inner + (0.85 - inner) * (1 - f) ** 2.2) * s
        return {"sd": (r - edge) * 0.6 + (0 if s > 0.02 else 1), "thick": 0.05, "no_erode": True}
    return frame


def embers_rise(rng):
    n = int(rng.integers(5, 14))
    pts = [(U(rng, -0.6, 0.6), U(rng, 0.4, 1.4), U(rng, 0.05, 0.1), U(rng, 0, TAU)) for _ in range(n)]
    def frame(t, x, y, m):
        sd = np.full(x.shape, 9.0)
        for (ox, sp, rr, ph) in pts:
            py = -0.8 + sp * t * 1.2
            px = ox + 0.12 * math.sin(t * 8 + ph)
            fl = 0.6 + 0.4 * math.sin(t * 30 + ph)
            if py < 0.85:
                sd = np.minimum(sd, np.hypot(x - px, y - py) - rr * fl * (1 - 0.6 * t))
        return {"sd": sd, "thick": 0.03, "no_erode": True}
    return frame


# ================================================================ magic
def magic_poof(rng):
    seed = int(rng.integers(1e6))
    n = int(rng.integers(4, 9))
    st = [(U(rng, 0, TAU), U(rng, 0.4, 0.8), U(rng, 0.05, 0.1)) for _ in range(n)]
    def frame(t, x, y, m):
        g = grow(t, 0.3)
        r = np.hypot(x, y)
        nz = fbm(x * 3 + seed, y * 3, 1.0, 4, seed=seed) - 0.5
        f = np.clip(1 - r / (0.15 + 0.45 * g) + nz * 0.8, 0, 1)
        sd_cloud = (0.5 - f) * 0.25
        sd = sd_cloud
        for (a, d, s) in st:
            cx, cy = math.cos(a) * d * g, math.sin(a) * d * g
            rr, th = polar(x - cx, y - cy)
            fs = np.abs(((th / TAU) * 4) % 1 - 0.5) * 2
            sd = np.minimum(sd, (rr - (s * 0.3 + s * (1 - fs) ** 2.5) * (1 - t)) * 0.6)
        return {"sd": sd, "thick": 0.08}
    return frame


def charge_in(rng):
    n = int(rng.integers(10, 26))
    parts = [(U(rng, 0, TAU), U(rng, 0.6, 0.9), U(rng, 0, 0.5)) for _ in range(n)]
    def frame(t, x, y, m):
        sd = np.hypot(x, y) - (0.05 + 0.25 * smooth(0.2, 1.0, t))
        for (a, d0, delay) in parts:
            tt = np.clip((t - delay * 0.6) / 0.5, 0, 1)
            if tt <= 0 or tt >= 1:
                continue
            d = d0 * (1 - tt)
            hx, hy = math.cos(a) * d, math.sin(a) * d
            tx, ty = math.cos(a) * min(d + 0.15, 0.9), math.sin(a) * min(d + 0.15, 0.9)
            sd = np.minimum(sd, path_sd(x, y, [(tx, ty), (hx, hy)], 0.004, 0.03))
        return {"sd": sd, "thick": 0.04, "no_erode": True}
    return frame


def portal_loop(rng):
    arms = int(rng.integers(2, 6))
    tight = U(rng, 2, 6)
    R = U(rng, 0.7, 0.88)
    def frame(t, x, y, m):
        r, th = polar(x, y)
        phase = (th * arms + tight * np.log(r + 0.05) * arms - TAU * t * arms) / TAU
        f = np.abs((phase % 1) - 0.5) * 2
        sd = (f - 0.45) * 0.12 * (r + 0.1)
        sd = np.maximum(sd, r - R)
        sd = np.minimum(sd, np.abs(r - R) - 0.025)
        return {"sd": sd, "thick": 0.03, "loop": True}
    return frame


def sigil_spin(rng):
    base = S.sigil(rng, *_g(512), 512)["sd"]
    spin = rng.choice([-1, 1]) * (TAU / int(rng.choice([4, 6, 8, 12])))
    def frame(t, x, y, m):
        sd = base if base.shape[0] == m else ndimage.zoom(base, m / base.shape[0], order=1)
        sd = ndimage.rotate(sd, math.degrees(spin * t), reshape=False, order=1, mode="nearest")
        return {"sd": sd, "thick": 0.02, "loop": True}
    return frame


def _g(m):
    from texcore import grid
    return grid(m)


def ink_splash(rng):
    seed = int(rng.integers(1e6))
    blobs = [(U(rng, 0, TAU), U(rng, 0.35, 0.8), U(rng, 0.04, 0.1)) for _ in range(int(rng.integers(6, 14)))]
    def frame(t, x, y, m):
        r, th = polar(x, y)
        g = grow(t, 0.2)
        sd = r - (0.4 + 0.12 * ang_noise(th, 9, seed)) * g
        for (a, d, rr) in blobs:
            dd = d * g
            cx, cy = math.cos(a) * dd, math.sin(a) * dd - 0.25 * smooth(0.3, 1, t)
            sd = smin(sd, np.hypot(x - cx, y - cy) - rr * g, 0.06)
        return {"sd": sd, "thick": 0.08, "erode_t0": 0.45}
    return frame


def heal_rise(rng):
    n = int(rng.integers(3, 7))
    pl = [(U(rng, -0.55, 0.55), U(rng, 0.0, 0.4), U(rng, 0.13, 0.24)) for _ in range(n)]
    def frame(t, x, y, m):
        sd = np.full(x.shape, 9.0)
        for (ox, delay, s) in pl:
            tt = np.clip((t - delay) / 0.6, 0, 1)
            if tt <= 0 or tt >= 1:
                continue
            py = -0.6 + 1.3 * tt
            sc = s * math.sin(math.pi * tt)
            xx, yy = np.abs(x - ox), np.abs(y - py)
            plus = np.minimum(np.maximum(xx - sc, yy - sc * 0.33), np.maximum(xx - sc * 0.33, yy - sc))
            sd = np.minimum(sd, plus)
        return {"sd": sd, "thick": 0.03, "no_erode": True}
    return frame


def bubbles_rise(rng):
    n = int(rng.integers(6, 14))
    b = [(U(rng, -0.6, 0.6), U(rng, 0.03, 0.12), U(rng, 0, 1), U(rng, 0, TAU)) for _ in range(n)]
    def frame(t, x, y, m):
        sd = np.full(x.shape, 9.0)
        for (ox, rr, off, ph) in b:
            tt = (t + off) % 1
            py = -0.85 + 1.7 * tt
            px = ox + 0.06 * math.sin(tt * 10 + ph)
            d = np.hypot(x - px, y - py)
            sd = np.minimum(sd, np.abs(d - rr) - rr * 0.15)
        return {"sd": sd, "thick": 0.02, "loop": True}
    return frame


def crack_spread(rng):
    base = S.crack(rng, *_g(512), 512)["sd"]
    def frame(t, x, y, m):
        sd = base if base.shape[0] == m else ndimage.zoom(base, m / base.shape[0], order=1)
        r = np.hypot(x, y)
        reach = 0.05 + 0.9 * ease_out(t / 0.4, 2)
        return {"sd": np.maximum(sd, r - reach), "thick": 0.02, "erode_t0": 0.6}
    return frame


def black_hole(rng):
    arms = int(rng.integers(1, 7))
    tight = U(rng, 1.5, 7) * rng.choice([-1, 1])
    core = U(rng, 0.1, 0.35)
    R = U(rng, 0.55, 0.88)
    width = U(rng, 0.3, 0.7)
    rim = U(rng, 0.0, 0.05)
    def frame(t, x, y, m):
        r, th = polar(x, y)
        phase = (th * arms - tight * np.log(r + 0.05) * arms + TAU * t * arms) / TAU
        f = np.abs((phase % 1) - 0.5) * 2
        sd = (f - width) * 0.1 * (r + 0.1)
        sd = np.maximum(sd, r - R)
        sd = np.maximum(sd, core - r)
        if rim:
            sd = np.minimum(sd, np.abs(r - core - 0.02) - rim)
        return {"sd": sd, "thick": 0.03, "loop": True}
    return frame


FLIPS = {
    # category: [(family, styles, variants per style, grid)]
    "shockwaves": [(shockwave, "cel soft glow ink", 9, 4), (shock_spiked, "cel glow", 8, 4), (ripple_fb, "cel glow", 7, 4)],
    "impacts": [(impact, "cel soft glow ink", 9, 4), (comic_pop, "cel ink", 7, 4), (explosion, "cel soft hot", 9, 4)],
    "fire": [(fire_loop, "cel soft hot", 10, 4), (fire_burst, "cel soft hot ink", 9, 4), (fireball_loop, "cel soft hot", 8, 4)],
    "smoke": [(smoke_puff_fb, "soft cel ink", 11, 4), (dust_ground, "soft cel", 10, 4), (plume_loop, "soft cel", 8, 4)],
    "lightning": [(lightning_fb, "cel glow", 12, 4), (electric_orb, "cel glow", 9, 4)],
    "slashes": [(slash_sweep, "cel soft glow ink", 10, 4), (claw_sweep, "cel glow ink", 8, 4)],
    "water": [(water_splash, "cel soft glow", 9, 4), (bubbles_rise, "cel glow", 8, 4)],
    "wind": [(wind_gust, "cel soft glow", 10, 4), (tornado_loop, "cel glow", 8, 4)],
    "shards": [(shatter, "cel glow ink", 10, 4)],
    "specks": [(sparks, "cel glow", 12, 8), (twinkle, "cel soft glow", 10, 8), (embers_rise, "cel glow", 10, 8)],
    "magic": [(magic_poof, "cel soft glow", 9, 4), (charge_in, "cel glow", 9, 4), (portal_loop, "cel glow ink", 8, 4),
              (sigil_spin, "cel glow", 10, 4), (heal_rise, "cel glow", 8, 4), (black_hole, "cel glow", 8, 4)],
    "ink": [(ink_splash, "cel ink", 10, 4)],
    "cracks": [(crack_spread, "cel glow ink", 8, 4)],
}
