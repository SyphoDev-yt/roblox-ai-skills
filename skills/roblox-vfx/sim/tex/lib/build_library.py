"""Build the VFX texture library: sprites, flipbooks and beam/trail strips,
every one generated (no third-party art), into sim/textures/lib/, with a
searchable catalog.json and per-category contact sheets.

    python build_library.py                 # everything (12 processes)
    python build_library.py --only flips    # sprites | flips | beams
    python build_library.py --limit 2       # 2 variants per family/style (quick look)

In the sim and in recipes a library texture is "sim:lib/<path without .png>",
e.g. "sim:lib/sprites/rings/ring_glow_03". catalog.json lists every file with
kind, category, family, style, grid (flipbooks), tile (beams) and tags; use
find_tex.py to search it.
"""
import argparse
import hashlib
import json
import math
import os
import sys
import time
from multiprocessing import Pool
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

FLIP_SCALE = 1.12

PALETTE_HOT = [(0.0, (0.35, 0.05, 0.02)), (0.35, (0.85, 0.18, 0.05)), (0.6, (1.0, 0.5, 0.1)), (0.82, (1.0, 0.85, 0.35)), (1.0, (1.0, 0.98, 0.85))]


def hot_colour(v):
    v = np.clip(v, 0, 1)
    out = np.zeros(v.shape + (3,))
    for (a, ca), (b, cb) in zip(PALETTE_HOT, PALETTE_HOT[1:]):
        k = np.clip((v - a) / (b - a), 0, 1)[..., None]
        sel = ((v >= a) & (v <= b))[..., None]
        out = np.where(sel, np.array(ca) * (1 - k) + np.array(cb) * k, out)
    return out


def jobs(only=None, limit=None):
    from sprites import SPRITES
    from flips import FLIPS
    from beams import BEAMS
    J = []
    if only in (None, "sprites"):
        for cat, fams in SPRITES.items():
            for fn, styles, n in fams:
                for st in styles.split():
                    for i in range(min(n, limit or n)):
                        J.append(("sprite", cat, fn.__name__, st, i, 0))
    if only in (None, "flips"):
        for cat, fams in FLIPS.items():
            for fn, styles, n, g in fams:
                for st in styles.split():
                    for i in range(min(math.ceil(n * FLIP_SCALE), limit or 999)):
                        J.append(("flip", cat, fn.__name__, st, i, g))
    if only in (None, "beams"):
        for fn, styles, n in BEAMS:
            for st in styles.split():
                for i in range(min(n, limit or n)):
                    J.append(("beam", "beams", fn.__name__, st, i, 0))
    return J


def seed_of(*parts):
    return int(hashlib.md5("/".join(map(str, parts)).encode()).hexdigest()[:8], 16)


def render(job):
    import texcore as C
    import sprites as S
    import flips as F
    import beams as B
    kind, cat, fam, st, i, g = job
    # the shape depends on family + index only, so cel/soft/glow/ink of the same
    # index are the SAME shape in four looks (pick a shape, then a look)
    rng = np.random.default_rng(seed_of(kind, cat, fam, i))
    try:
        if kind == "sprite":
            n, m = 512, 1024
            x, y = C.grid(m)
            S.INDEX = i
            d = getattr(S, fam)(rng, x, y, m)
            if "f" in d:
                gr, a = C.density_style(d["f"], n, st, i)
            else:
                gr, a = C.style(d["sd"], n, "cel" if st == "hot" else st, i, thick=d.get("thick", 0.08), shade=d.get("shade"), levels=d.get("levels"))
            if st == "hot":
                gr = hot_colour(np.clip(gr * 1.05, 0, 1))
            a = C.fade_border(a)
            from vfxtex import downsample
            gg, aa = downsample(gr, a, n)
            rel = f"sprites/{cat}/{fam}_{st}_{i:02d}.png"
            C.save_png(C.LIB / rel, gg, aa)
            cov = float((aa > 0.5).mean())
            thumb = (aa[::32, ::32] > 0.3)
            return {"file": rel, "kind": kind, "category": cat, "family": fam, "style": st, "size": [n, n], "coverage": round(cov, 4),
                    "thumb": "".join("1" if v else "0" for v in thumb.ravel())}
        if kind == "flip":
            n = 256 if g == 4 else 128
            m = n * 2
            x, y = C.grid(m)
            frame = getattr(F, fam)(rng)
            N = g * g
            frames, covs = [], []
            loop = False
            for k in range(N):
                t = k / N
                d = frame(t, x, y, m)
                loop = loop or d.get("loop", False)
                if "f" in d:
                    gr, a = C.density_style(d["f"], n, "soft" if st == "hot" else st, i)
                else:
                    gr, a = C.style(d["sd"], n, "cel" if st == "hot" else st, i, thick=d.get("thick", 0.08))
                if not (d.get("loop") or d.get("no_erode")):
                    a = C.erode(a, t, i * 31 + k * 0, x, y, t0=d.get("erode_t0", 0.42))
                a = C.fade_border(a)
                if st == "hot":
                    heat = np.clip((gr if np.ndim(gr) == 2 else np.full(a.shape, gr)) * (1.1 if d.get("loop") else 1.15 - 0.6 * t), 0, 1)
                    gr = hot_colour(heat)
                frames.append((gr, a))
            from vfxtex import assemble
            rgb, A = assemble(frames, g, n)
            rel = f"flipbooks/{cat}/{fam}_{st}_{i:02d}_{g}x{g}.png"
            C.save_png(C.LIB / rel, rgb, A)
            per = [float((A[(k // g) * n:(k // g + 1) * n, (k % g) * n:(k % g + 1) * n] > 0.5).mean()) for k in range(N)]
            moving = float(np.std(per)) > 1e-4 or loop
            return {"file": rel, "kind": kind, "category": cat, "family": fam, "style": st, "grid": g, "frames": N, "loop": loop,
                    "size": [n * g, n * g], "coverage": round(max(per), 4), "last": round(per[-1], 4), "moving": moving,
                    "thumb": "".join("1" if v else "0" for v in (A[::64, ::64] > 0.3).ravel())}
        if kind == "beam":
            W, H = 1024, 256
            x, y = B.strip_grid(W * 2, H * 2)
            d = getattr(B, fam)(rng, x, y)
            from scipy import ndimage
            pw = 2.0 / H
            if "f" in d:
                f = d["f"]
                if st == "cel":
                    gr = np.where(f > 0.7, 1.0, np.where(f > 0.45, 0.8, 0.6))
                    a = np.clip((f - 0.3) / 0.03, 0, 1)
                elif st == "glow":
                    a = np.clip(f, 0, 1) ** 0.8
                    gr = 0.9 + 0.1 * a
                else:
                    a = np.clip(f, 0, 1) ** 1.1
                    gr = 0.8 + 0.2 * a
            else:
                sd = d["sd"]
                core = np.clip(0.5 - sd / pw, 0, 1)
                if st == "cel":
                    a = core
                    depth = np.clip(-sd / d.get("thick", 0.05), 0, 1)
                    gr = np.where(depth > 0.6, 1.0, np.where(depth > 0.25, 0.82, 0.62))
                elif st == "glow":
                    halo = ndimage.gaussian_filter(core, (H * 0.04, H * 0.04), mode=("nearest", "wrap"))
                    a = np.clip(np.maximum(core, halo * 1.4), 0, 1)
                    gr = 0.88 + 0.12 * core
                elif st == "ink":
                    nz = B.pfbm(x, y, 8, 6, i + 3) - 0.5
                    a = np.clip(0.5 - (sd + nz * pw * 8) / pw, 0, 1)
                    gr = np.where(B.pfbm(x, y, 4, 3, i + 5) > 0.55, 0.78, 0.95)
                else:
                    a = np.maximum(core, np.exp(-np.maximum(sd, 0) / 0.08) * 0.8 * (sd > 0))
                    gr = 0.85 + 0.15 * core
            if st == "hot" or d.get("hot"):
                gr = hot_colour(np.clip(a * 1.05, 0, 1))
            if not d.get("tile", True):
                a = a * np.clip(np.minimum(x, 1 - x) * 40, 0, 1)
            a = a * np.clip((1 - np.abs(y)) * 25, 0, 1)
            # 2x supersample down
            a2 = a.reshape(H, 2, W, 2).mean(axis=(1, 3))
            if np.ndim(gr) == 2:
                g2 = (gr * a).reshape(H, 2, W, 2).mean(axis=(1, 3)) / np.maximum(a2, 1e-5)
                g2 = np.where(a2 < 1e-3, 1.0, g2)
            else:
                g2 = (gr * a[..., None]).reshape(H, 2, W, 2, 3).mean(axis=(1, 3)) / np.maximum(a2[..., None], 1e-5)
                g2 = np.where(a2[..., None] < 1e-3, 1.0, g2)
            rel = f"beams/{fam}_{st}_{i:02d}.png"
            C.save_png(C.LIB / rel, g2, a2)
            return {"file": rel, "kind": kind, "category": "beams", "family": fam, "style": st, "size": [W, H], "tile": bool(d.get("tile", True)),
                    "coverage": round(float((a2 > 0.5).mean()), 4), "thumb": "".join("1" if v else "0" for v in (a2[::32, ::64] > 0.3).ravel())}
    except Exception as e:
        import traceback
        return {"error": f"{job}: {e}\n{traceback.format_exc()[-600:]}"}


TAGS = {
    "rings": "ring shockwave circle wave pulse", "slashes": "slash sword crescent cut arc claw", "sigils": "magic circle rune sigil arcane glyph hex",
    "elements": "element fire water leaf ice lightning wind poison dark holy earth rock", "impacts": "impact hit burst explosion pop star comic",
    "specks": "speck dot spark particle wisp ember streak", "shards": "shard crystal glass ice fragment debris", "flares": "flare lens glint star bokeh light",
    "swirls": "swirl spiral vortex portal wind", "stars": "star sparkle twinkle", "cracks": "crack ground fissure break", "smoke": "smoke cloud puff dust",
    "shapes": "orb heart petal feather chevron arrow", "masks": "mask noise gradient", "shockwaves": "shockwave ring wave", "fire": "fire flame burn",
    "lightning": "lightning electric thunder spark bolt", "water": "water splash bubble", "wind": "wind gust tornado air", "magic": "magic portal sigil heal charge poof",
    "ink": "ink paint splat", "beams": "beam trail ribbon strip"}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--only")
    ap.add_argument("--limit", type=int)
    ap.add_argument("--families", help="comma list: re-render only these families (merged into the catalog)")
    ap.add_argument("--procs", type=int, default=max(1, (os.cpu_count() or 4) - 1))
    args = ap.parse_args()
    J = jobs(args.only, args.limit)
    if args.families:
        fs = set(args.families.split(","))
        J = [j for j in J if j[2] in fs]
    print(f"{len(J)} textures, {args.procs} processes", flush=True)
    t0 = time.time()
    out, errs = [], []
    with Pool(args.procs) as pool:
        for k, r in enumerate(pool.imap_unordered(render, J, chunksize=2)):
            (errs if "error" in r else out).append(r)
            if (k + 1) % 100 == 0:
                print(f"  {k + 1}/{len(J)}  {time.time() - t0:.0f}s  errors {len(errs)}", flush=True)
    for e in errs[:10]:
        print("ERROR", e)
    import texcore as C
    cat_path = C.LIB / "catalog.json"
    old = json.loads(cat_path.read_text()) if cat_path.exists() else {"textures": []}
    keep = {e["file"]: e for e in old["textures"]}
    for r in out:
        r["tags"] = (TAGS.get(r["category"], "") + " " + r["family"].replace("_", " ") + " " + r["style"]).split()
        r["id"] = "sim:lib/" + r["file"][:-4]
        keep[r["file"]] = r
    cat = {"note": "Generated VFX texture library. id = the Texture value to use in the sim (Studio: upload the png).",
           "textures": sorted(keep.values(), key=lambda e: e["file"])}
    cat_path.write_text(json.dumps(cat, indent=0))
    print(f"done {len(out)} ok, {len(errs)} errors, {time.time() - t0:.0f}s; catalog {len(cat['textures'])}")


if __name__ == "__main__":
    main()
