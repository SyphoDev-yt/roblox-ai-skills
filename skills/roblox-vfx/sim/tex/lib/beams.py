"""Beam / Trail strip families. A strip is W x H (default 1024 x 256): U runs
along the beam (x, wraps when "tile" is True so TextureMode Wrap scrolls
seamlessly), V across it (y). Returns {"sd" | "f"} in strip coordinates
x in [0, 1) (periodic) and y in [-1, 1].
"""
import math

import numpy as np

from texcore import seg_sd, smooth, fbm

TAU = 2 * math.pi


def U(rng, a, b):
    return float(rng.uniform(a, b))


def strip_grid(w, h):
    xs = (np.arange(w) + 0.5) / w
    ys = ((np.arange(h) + 0.5) / h) * 2 - 1
    x, y = np.meshgrid(xs, -ys)
    return x, y


def pfbm(x, y, kx, ky, seed, oct=4):
    """Noise periodic in x (x in [0,1))."""
    return fbm(x * kx, y * ky, 1.0, oct, seed=seed, period=(kx, 0))


def energy(rng, x, y):
    seed = int(rng.integers(1e6))
    k = int(rng.integers(2, 7))
    w = U(rng, 0.35, 0.8)
    nz = pfbm(x, y, k, U(rng, 1.5, 3), seed) - 0.5
    core = np.clip(1 - np.abs(y + nz * U(rng, 0.3, 0.9)) / w, 0, 1)
    streaks = pfbm(x, y, k * 4, 6, seed + 1, 3)
    f = core ** U(rng, 0.6, 1.4) * (0.6 + 0.6 * streaks)
    return {"f": np.clip(f, 0, 1), "tile": True}


def plasma(rng, x, y):
    seed = int(rng.integers(1e6))
    k = int(rng.integers(3, 8))
    a = pfbm(x, y, k, 3, seed)
    b = pfbm(x, y, k * 2, 5, seed + 4)
    band = 1 - np.abs(a - 0.5) * U(rng, 3, 7)
    f = np.clip(band, 0, 1) * (0.5 + 0.5 * b) * smooth(1.0, 0.55, np.abs(y))
    return {"f": np.clip(f * 1.6, 0, 1), "tile": True}


def streak(rng, x, y):
    W = U(rng, 0.15, 0.9)
    head = U(rng, 0.7, 0.98)
    u = x
    prof = np.where(u < head, (u / head) ** U(rng, 0.7, 2.5), np.clip(1 - (u - head) / (1 - head), 0, 1) ** 0.5)
    sd = np.abs(y) - W * prof
    return {"sd": sd * 0.5, "tile": False, "thick": 0.3}


def speed_streaks(rng, x, y):
    seed = int(rng.integers(1e6))
    n = int(rng.integers(5, 16))
    sd = np.full(x.shape, 9.0)
    r2 = np.random.default_rng(seed)
    for _ in range(n):
        cy = r2.uniform(-0.8, 0.8)
        x0 = r2.uniform(0, 1)
        L = r2.uniform(0.15, 0.6)
        w = r2.uniform(0.02, 0.08)
        for shift in (-1, 0, 1):
            xx = (x - x0 - shift) / L
            prof = w * np.clip(np.sin(math.pi * np.clip(xx, 0, 1)), 0, 1) ** 0.6
            s = np.abs(y - cy) - prof
            sd = np.minimum(sd, np.where((xx >= 0) & (xx <= 1), s, 9.0))
    return {"sd": sd * 0.5, "tile": True, "thick": 0.05}


def lightning(rng, x, y):
    seed = int(rng.integers(1e6))
    r2 = np.random.default_rng(seed)
    k = int(rng.integers(12, 40))
    ys = r2.normal(0, U(rng, 0.2, 0.45), k + 1)
    ys[-1] = ys[0]
    ys = np.clip(ys, -0.75, 0.75)
    pts = [(i / k, float(ys[i])) for i in range(k + 1)]
    W = U(rng, 0.05, 0.14)
    sd = np.full(x.shape, 9.0)
    for shift in (-1, 0, 1):
        for i in range(k):
            a = (pts[i][0] + shift, pts[i][1])
            b = (pts[i + 1][0] + shift, pts[i + 1][1])
            sd = np.minimum(sd, _seg_aspect(x, y, a, b) - W / 2)
    if rng.random() < 0.6:
        ys2 = np.clip(r2.normal(0, 0.4, k + 1), -0.8, 0.8)
        ys2[-1] = ys2[0]
        for shift in (-1, 0, 1):
            for i in range(k):
                sd = np.minimum(sd, _seg_aspect(x, y, (i / k + shift, float(ys2[i])), ((i + 1) / k + shift, float(ys2[i + 1]))) - W * 0.3)
    return {"sd": sd * 0.5, "tile": True, "thick": 0.05}


ASPECT = 4.0  # strip is 4x wider than tall: x units are 4x the y units


def _seg_aspect(x, y, a, b):
    return seg_sd(x * ASPECT * 0.5, y, (a[0] * ASPECT * 0.5, a[1]), (b[0] * ASPECT * 0.5, b[1]))


def laser(rng, x, y):
    w = U(rng, 0.05, 0.7)
    rings = int(rng.choice([0, 1, 2, 3, 4, 6, 8, 12]))
    f = np.clip(1 - np.abs(y) / w, 0, 1) ** U(rng, 0.4, 2)
    if rings:
        f = np.maximum(f, np.clip(1 - np.abs(((x * rings) % 1) - 0.5) * 30, 0, 1) * (np.abs(y) < 0.85))
    return {"f": f, "tile": True}


def sine(rng, x, y):
    n = int(rng.integers(1, 4))
    sd = np.full(x.shape, 9.0)
    for i in range(n):
        k = int(rng.integers(1, 6))
        amp = U(rng, 0.2, 0.7)
        ph = TAU * i / n
        cy = amp * np.sin(TAU * k * x + ph)
        sd = np.minimum(sd, np.abs(y - cy) - U(rng, 0.04, 0.15))
    return {"sd": sd * 0.5, "tile": True, "thick": 0.05}


def dashed(rng, x, y):
    n = int(rng.integers(3, 16))
    duty = U(rng, 0.3, 0.7)
    w = U(rng, 0.1, 0.5)
    u = (x * n) % 1
    ends = np.minimum(u, duty - u) * ASPECT * 2 / n
    sd = np.where(u < duty, np.maximum(np.abs(y) - w, -ends), 0.2)
    if rng.random() < 0.5:
        sd = np.maximum(sd, -(np.abs(y) - w * 0.4)) if rng.random() < 0.5 else sd
    return {"sd": sd * 0.5, "tile": True, "thick": 0.05}


def helix(rng, x, y):
    k = int(rng.integers(2, 7))
    w = U(rng, 0.06, 0.16)
    a = 0.7 * np.sin(TAU * k * x)
    b = -a
    sd = np.minimum(np.abs(y - a), np.abs(y - b)) - w
    return {"sd": sd * 0.5, "tile": True, "thick": 0.05}


def rune_band(rng, x, y):
    n = int(rng.integers(6, 18))
    r2 = np.random.default_rng(int(rng.integers(1e6)))
    sd = np.minimum(np.abs(y - 0.85) - 0.03, np.abs(y + 0.85) - 0.03)
    for i in range(n):
        cx = (i + 0.5) / n
        strokes = r2.integers(2, 5)
        for _ in range(strokes):
            p = [(cx + r2.uniform(-0.3, 0.3) / n, r2.uniform(-0.55, 0.55)) for _ in range(2)]
            sd = np.minimum(sd, _seg_aspect(x, y, p[0], p[1]) - 0.035)
    return {"sd": sd * 0.5, "tile": True, "thick": 0.03}


def fire_trail(rng, x, y):
    seed = int(rng.integers(1e6))
    k = int(rng.integers(2, 12))
    nz = pfbm(x, y, k, U(rng, 1.5, 4), seed)
    edge = U(rng, 0.1, 0.35) + U(rng, 0.4, 0.9) * nz
    f = np.clip((edge - np.abs(y)) * 4, 0, 1)
    tongues = pfbm(x, y, k * 3, 4, seed + 2, 3)
    return {"f": np.clip(f * (0.7 + 0.6 * tongues), 0, 1), "tile": True, "hot": True}


def smoke_trail(rng, x, y):
    seed = int(rng.integers(1e6))
    nz = pfbm(x, y, int(rng.integers(2, 6)), 3, seed, 5)
    f = np.clip((0.6 + 0.6 * (nz - 0.5) * 2 - np.abs(y)) * 2, 0, 1)
    return {"f": f, "tile": True}


def water_trail(rng, x, y):
    seed = int(rng.integers(1e6))
    k = int(rng.integers(1, 9))
    nz = pfbm(x, y, k, U(rng, 1, 4), seed)
    lines = np.abs(((y * U(rng, 1.5, 5) + (nz - 0.5) * U(rng, 1, 4)) % 1) - 0.5) < U(rng, 0.04, 0.2)
    body = np.abs(y) < 0.7 + 0.2 * (nz - 0.5)
    f = np.where(body, np.where(lines, 1.0, 0.55), 0.0)
    return {"f": f * smooth(1.0, 0.6, np.abs(y)), "tile": True}


def sparkle_trail(rng, x, y):
    r2 = np.random.default_rng(int(rng.integers(1e6)))
    n = int(rng.integers(8, 30))
    sd = np.full(x.shape, 9.0)
    for _ in range(n):
        cx, cy = r2.uniform(0, 1), r2.uniform(-0.6, 0.6)
        s = r2.uniform(0.08, 0.25)
        for shift in (-1, 0, 1):
            dx = (x - cx - shift) * ASPECT * 0.5
            dy = y - cy
            star = np.minimum(np.abs(dx) * 4 + np.abs(dy), np.abs(dx) + np.abs(dy) * 4) / 4 - s * 0.25
            sd = np.minimum(sd, star)
    return {"sd": sd, "tile": True, "thick": 0.03}


def chain_band(rng, x, y):
    n = int(rng.integers(4, 12))
    u = (x * n) % 1
    xx = (u - 0.5) * ASPECT * 2 / n
    sd_o = np.abs(np.hypot(xx / 0.45, y / 0.5) - 1) * 0.3 - 0.04
    alt = (np.floor(x * n) % 2) == 1
    sd_b = np.abs(y) - 0.08
    sd = np.where(alt, np.maximum(sd_b, np.abs(xx) - 0.2), sd_o)
    return {"sd": sd * 0.6, "tile": True, "thick": 0.05}


def ink_stroke(rng, x, y):
    seed = int(rng.integers(1e6))
    nz = pfbm(x, y, int(rng.integers(2, 5)), 2, seed)
    w = 0.4 + 0.45 * (nz - 0.5) * 2
    dry = pfbm(x, y, 3, 30, seed + 1, 3) > U(rng, 0.55, 0.7)
    sd = np.abs(y) - w
    sd = np.where(dry & (np.abs(y) > w * 0.3), np.maximum(sd, 0.02), sd)
    return {"sd": sd * 0.5, "tile": True, "thick": 0.1}


def zigzag(rng, x, y):
    k = int(rng.integers(2, 14))
    amp = U(rng, 0.25, 0.8)
    w = U(rng, 0.05, 0.16)
    tri = (np.abs(((x * k) % 1) - 0.5) * 4 - 1) * amp
    sd = np.abs(y - tri) - w
    if rng.random() < 0.4:
        sd = np.minimum(sd, np.abs(y + tri) - w * 0.6)
    return {"sd": sd * 0.5, "tile": True, "thick": 0.05}


def beads(rng, x, y):
    n = int(rng.integers(3, 14))
    r2 = np.random.default_rng(int(rng.integers(1e6)))
    sizes = r2.uniform(0.25, 0.85, n)
    u = (x * n) % 1
    i = np.floor(x * n).astype(int) % n
    xx = (u - 0.5) * ASPECT * 2 / n
    sd = np.hypot(xx, y) - sizes[i] * min(0.9, ASPECT / n)
    if rng.random() < 0.5:
        sd = np.minimum(sd, np.abs(y) - U(rng, 0.03, 0.1))
    return {"sd": sd * 0.5, "tile": True, "thick": 0.1}


def chevrons(rng, x, y):
    n = int(rng.integers(3, 12))
    w = U(rng, 0.08, 0.2)
    slope = U(rng, 0.15, 0.6)
    u = (x * n) % 1
    v = u - np.abs(y) * slope
    sd = (np.abs(((v + 1) % 1) - 0.5) - w) / n * ASPECT * 0.5
    sd = np.maximum(sd, np.abs(y) - U(rng, 0.5, 0.85))
    return {"sd": sd, "tile": True, "thick": 0.04}


BEAMS = [(energy, "soft glow", 12), (plasma, "soft glow", 8), (streak, "cel soft glow", 6), (speed_streaks, "cel glow", 6),
         (lightning, "cel glow", 10), (laser, "soft glow", 8), (sine, "cel glow", 6), (dashed, "cel glow", 5), (helix, "cel glow", 5),
         (rune_band, "cel glow", 6), (fire_trail, "soft hot", 8), (smoke_trail, "soft cel", 6), (water_trail, "soft cel", 6),
         (sparkle_trail, "cel glow", 6), (chain_band, "cel", 6), (ink_stroke, "cel ink", 6),
         (zigzag, "cel glow", 6), (beads, "cel soft glow", 6), (chevrons, "cel glow", 6)]
