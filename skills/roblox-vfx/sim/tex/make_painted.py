"""Painted VFX textures (brush engine, vfxpaint.py): the hand-drawn tier.

    python make_painted.py [slash eclipse smoke ring beam]

Each texture is many tapered, wandering strokes painted back-to-front
(shadow strokes, then mid, then the bright leading strokes), never an exact
geometric shape. Same naming and output folder as make_textures.py, so
measure.py and the sim pick them up.
"""
import math
import sys

import numpy as np
from PIL import Image

import vfxtex as vt
from vfxtex import smooth, save, assemble, add_halo, single
from vfxpaint import Canvas, arc_path, curl_path, grain_field

FR = 256
T16 = [i / 15 for i in range(16)]


def env_slash(s):
    v = (np.clip(s, 1e-4, 1) ** 0.35) * (np.clip(1 - s, 1e-4, 1) ** 1.2) * smooth(0.0, 0.25, s)
    return v / 0.37


def slash_paint(seed=5, name="slash_paint_4x4", qmax=None):
    """qmax: keep only strokes with q <= qmax (the leading-edge rim), drawn from the SAME
    random strokes as the full crescent so the rim layer lines up with it exactly."""
    rng = np.random.default_rng(seed)
    N = 30
    S = []
    for k in range(N):
        q = float(rng.beta(1.2, 2.6))                      # 0 = leading (outer) edge, 1 = inner
        s0 = float(rng.uniform(0.0, 0.14))
        ln = float(rng.uniform(0.35, 1.0)) * (1 - s0)
        wf = float(rng.uniform(0.6, 1.3))
        die = float(rng.uniform(0.45, 0.95))
        grey = 1.0 if q < 0.1 else (float(rng.uniform(0.62, 0.78)) if q < 0.45 else float(rng.uniform(0.3, 0.45)))
        S.append((q, s0, ln, wf, die, grey))
    S.sort(key=lambda z: -z[0])                            # inner/dark first, bright leading strokes last
    wisps = [(float(rng.uniform(0.1, 0.6)), float(rng.uniform(0.6, 1.4)), float(rng.uniform(0.5, 0.95))) for _ in range(5)]
    head = math.radians(-10 + rng.uniform(-5, 5))
    span_pk = math.radians(rng.uniform(205, 225))
    frames = []
    m = FR * 4
    grain = grain_field(m, seed + 1, scale=5, amount=0.22)
    for t in T16:
        c = Canvas(FR)
        R = 0.80 * (1 + 0.12 * t)
        span = span_pk * (0.42 + 0.58 * smooth(0.0, 0.25, t)) * (1 - 0.8 * smooth(0.86, 1.0, t))
        Tk = (0.55 + 0.45 * smooth(0.0, 0.2, t)) * (1 - 0.82 * smooth(0.28, 0.92, t))
        for q, s0, ln, wf, die, grey in S:
            if t > die or (qmax is not None and q > qmax):
                continue
            life = 1 - smooth(die - 0.28, die, t)
            s_end = s0 + ln * (0.35 + 0.65 * life)
            ss = np.linspace(s0, min(1.0, s_end), 40)
            th = head + span * ss
            r = R - q * env_slash(ss) * R * 0.62
            r = r * (1 + 0.012 * np.sin(ss * 17 + q * 9))
            pts = np.stack([np.cos(th) * r, np.sin(th) * r], 1)
            w = 0.17 * (0.45 + 0.55 * (1 - q)) * wf * Tk * float(np.mean(env_slash(ss)) + 0.3)
            if qmax is not None:
                w *= 0.4            # the rim is a thin hot edge, not a second body
            c.stroke(pts, w, taper=(0.25, 1.15), alpha=1.0, grey=grey * (1 - 0.25 * t), grain=grain)
        # wisps tearing off the inner edge
        for s_w, curl, wl in wisps:
            if t < 0.2 or t > 0.8 or qmax is not None:
                continue
            a = head + span * s_w
            r0 = R - env_slash(s_w) * R * 0.45
            p0 = (math.cos(a) * r0, math.sin(a) * r0)
            pts = curl_path(p0, a + math.pi * 0.62, 0.22 * wl * (1 - t * 0.5), curl * 1.2, n=24)
            c.stroke(pts, 0.022 * (1 - t), taper=(0.2, 1.4), alpha=0.85, grey=0.8, grain=grain)
        g, a = c.result()
        frames.append((g, a))
    rgb, al = assemble(frames, 4, FR)
    save(name, rgb, al, {"use": "PAINTED crescent slash, head at right sweeping over the top, OneShot Grid4x4", "flipbook": "Grid4x4", "grey": True})


def eclipse_paint(seed=7):
    rng = np.random.default_rng(seed)
    c = Canvas(512)
    m = 512 * 4
    # warped dark disc (painted fill, not a circle)
    n = 180
    ang = np.linspace(0, 2 * math.pi, n, endpoint=False)
    rr = 0.40 * (1 + 0.035 * np.sin(3 * ang + 1.1) + 0.02 * np.sin(7 * ang + 0.4) + 0.012 * rng.normal(0, 1, n).cumsum() / 6)
    poly = [((math.cos(a) * r + 1) / 2 * m, (1 - (math.sin(a) * r + 1) / 2) * m) for a, r in zip(ang, rr)]
    from PIL import ImageDraw
    disc = Image.new("L", (m, m), 0)
    ImageDraw.Draw(disc).polygon(poly, fill=242)
    c.a = np.asarray(disc, np.float32) / 255
    c.g = np.full_like(c.a, 0.06)
    # inner faint swirl strokes inside the disc
    for k in range(6):
        a0 = rng.uniform(0, 6.28)
        c.stroke(arc_path(0.28 * rng.uniform(0.6, 1.0), 0.3 * rng.uniform(0.5, 1.0), a0, a0 + rng.uniform(1.0, 2.4), wobble=0.04, rng=rng),
                 0.02, taper=(0.3, 1.2), alpha=0.25, grey=0.35)
    # painted rim: 4 overlapping arcs of uneven weight
    for k in range(4):
        a0 = rng.uniform(0, 6.28)
        c.stroke(arc_path(0.405, 0.41, a0, a0 + rng.uniform(3.5, 6.0), n=90, wobble=0.012, rng=rng), rng.uniform(0.02, 0.045),
                 taper=(0.15, 0.6), alpha=0.95, grey=1.0)
    # corona: flame tongues of uneven length, curling
    K = 46
    starts = np.sort(rng.uniform(0, 2 * math.pi, K))
    for a in starts:
        L = float(np.clip(rng.lognormal(math.log(0.13), 0.55), 0.04, 0.42))
        r0 = 0.40 + rng.uniform(-0.01, 0.02)
        p0 = (math.cos(a) * r0, math.sin(a) * r0)
        pts = curl_path(p0, a + rng.normal(0, 0.18), L, rng.normal(0, 0.7), n=20, rng=rng, jitter=0.03)
        c.stroke(pts, rng.uniform(0.018, 0.05), taper=(0.15, 1.4), alpha=rng.uniform(0.7, 1.0), grey=1.0)
    g, a = c.result()
    a = add_halo(a, 512, ((0.012, 0.3), (0.04, 0.12)))
    single("eclipse_paint", g, a, 512, {"use": "PAINTED eclipse: dark warped disc, uneven rim, curling corona; tint via Color", "grey": True})


def smoke_wisp(seed=11, name="smoke_wisp_4x4"):
    """Ink-wash smoke: curling strokes, not circle clusters."""
    rng = np.random.default_rng(seed)
    K = 34
    W = []
    for k in range(K):
        ang = rng.uniform(0, 2 * math.pi)
        rad = rng.uniform(0, 0.3) ** 0.9
        W.append((math.cos(ang) * rad, math.sin(ang) * rad * 0.8, rng.uniform(0, 2 * math.pi), rng.uniform(-2.2, 2.2),
                  rng.uniform(0.14, 0.32), rng.uniform(0.16, 0.32), rng.uniform(0.45, 0.95), rng.choice([1.0, 0.84, 0.66], p=[0.35, 0.4, 0.25])))
    W.sort(key=lambda z: z[7])
    frames = []
    for t in T16:
        c = Canvas(FR)
        grow = 0.55 + 0.45 * smooth(0.0, 0.3, t)
        rise = 0.22 * t
        for x0, y0, hd, curl, ln, wd, die, grey in W:
            if t > die:
                continue
            fade = 1 - smooth(die - 0.3, die, t)
            p0 = (x0 * grow * 1.6, y0 * grow * 1.6 + rise - 0.1)
            pts = curl_path(p0, hd, ln * grow * (0.6 + 0.4 * fade), curl, n=26)
            c.stroke(pts, wd * grow * (0.4 + 0.6 * fade), taper=(0.45, 0.9), alpha=0.9 * (0.5 + 0.5 * fade), grey=grey * (1 - 0.35 * t))
        frames.append(c.result())
    rgb, al = assemble(frames, 4, FR)
    save(name, rgb, al, {"use": "PAINTED ink-wash smoke wisps, OneShot Grid4x4, tint", "flipbook": "Grid4x4", "grey": True})


def ring_paint(seed=13, name="ring_paint_4x4"):
    rng = np.random.default_rng(seed)
    A = [(rng.uniform(0, 6.28), rng.uniform(1.0, 3.6), rng.uniform(-0.05, 0.04), rng.uniform(0.6, 1.3), rng.uniform(0.4, 0.85), rng.choice([1.0, 0.8])) for _ in range(9)]
    frames = []
    for t in T16:
        c = Canvas(FR)
        thick = 0.13 * max(0.0, 1 - t / 0.75) ** 1.2
        for a0, span, dr, wf, die, grey in A:
            if t > die:
                continue
            f = 1 - smooth(die - 0.25, die, t)
            pts = arc_path(0.84 + dr, 0.84 + dr * 0.5, a0, a0 + span * (0.5 + 0.5 * f), n=60, wobble=0.015, rng=np.random.default_rng(int(a0 * 1000)))
            c.stroke(pts, thick * wf * f + 0.004, taper=(0.3, 0.9), alpha=1.0, grey=grey)
        frames.append(c.result())
    rgb, al = assemble(frames, 4, FR)
    save(name, rgb, al, {"use": "PAINTED shock ring: uneven arc strokes, outer radius fixed, Size expands; OneShot Grid4x4", "flipbook": "Grid4x4", "grey": True})


def beam_paint(seed=17):
    """Painted energy strip, tiles along U: horizontal tapered streaks."""
    rng = np.random.default_rng(seed)
    c = Canvas(512)
    for k in range(34):
        y = float(np.clip(rng.normal(0, 0.32), -0.8, 0.8))
        x0 = rng.uniform(-1, 1)
        ln = rng.uniform(0.3, 1.1)
        w = 0.12 * (1 - abs(y) * 0.8) * rng.uniform(0.5, 1.2)
        grey = 1.0 if abs(y) < 0.25 else 0.75
        for off in (-2, 0, 2):          # wrap so U tiles
            xs = np.linspace(x0 + off, x0 + off + ln, 30)
            ys = y + 0.04 * np.sin(xs * 3 + k)
            c.stroke(np.stack([xs, ys], 1), w, taper=(0.4, 1.0), alpha=0.95, grey=grey)
    g, a = c.result()
    g2 = np.asarray(Image.fromarray((g * 255).astype(np.uint8)).resize((512, 128), Image.LANCZOS), np.float32) / 255
    a2 = np.asarray(Image.fromarray((np.clip(a, 0, 1) * 255).astype(np.uint8)).resize((512, 128), Image.LANCZOS), np.float32) / 255
    save("beam_paint", np.repeat(g2[..., None], 3, 2), a2, {"use": "PAINTED energy beam strip, Wrap along U", "grey": True})


ALL = {"slash": lambda: (slash_paint(5, "slash_paint_4x4"), slash_paint(9, "slash_paint_b_4x4"), slash_paint(5, "slash_paint_rim_4x4", qmax=0.16)), "eclipse": eclipse_paint,
       "smoke": smoke_wisp, "ring": ring_paint, "beam": beam_paint}

if __name__ == "__main__":
    import json
    want = sys.argv[1:]
    for k, fn in ALL.items():
        if not want or k in want:
            fn()
            print("made", k)
    man = vt.OUT / "manifest.json"
    old = json.loads(man.read_text()) if man.exists() else {}
    old.update(vt.MANIFEST)
    man.write_text(json.dumps(old, indent=1))
