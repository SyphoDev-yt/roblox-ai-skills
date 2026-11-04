#!/usr/bin/env python3
"""Fetch HIGH-RES copies of chosen library textures, so a sprite sheet can be judged.

    python fetch_tex_hires.py --lib "<lib>" Stem#1 Stem#2 ...      # by layer ref
    python fetch_tex_hires.py --lib "<lib>" --ids <asset id> ...    # by asset id
    python fetch_tex_hires.py --lib "<lib>" Stem#1 --size 420x420 --frames out.png

DEFECT THIS EXISTS FOR (2026-10-08, a flipbook upgrade). classify_lib.py
caches every texture at 150x150 (<lib>/.cache/tex). That is fine for tagging, and
useless for judging a SPRITE SHEET: a Grid4x4 frame is 37 px and a Grid8x8 frame is
18 px, so "is this a leaf or a speck?" cannot be answered from the cache - LeafSpec4x4
read as scattered grey dots at 150 px. This pulls the Roblox asset thumbnail at a
larger size into <lib>/.cache/tex_hi/<id>.png (never overwriting the 150 px cache,
which classify_lib and assemble_kit.black_backed() read), and with --frames writes a
contact sheet of every frame of each sheet, on mid grey, labelled, so one image shows
the whole animation.

Read-only GETs against thumbnails.roblox.com (no auth, same endpoint classify_lib
uses). A thumbnail that is not "Completed" is reported, never silently skipped.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
import time
import urllib.request
from pathlib import Path

UA = {"User-Agent": "roblox-vfx/fetch_tex_hires"}
GRID = {"Grid2x2": 2, "Grid4x4": 4, "Grid8x8": 8}


def http(u, raw=False, tries=3):
    for i in range(tries):
        try:
            r = urllib.request.urlopen(urllib.request.Request(u, headers=UA), timeout=45)
            return r.read() if raw else json.load(r)
        except Exception:
            if i == tries - 1:
                return None
            time.sleep(1.5 * (i + 1))


def layer_of(rdir: Path, ref: str):
    stem, _, i = ref.partition("#")
    rec = json.loads((rdir / f"{stem}.json").read_text(encoding="utf-8"))
    return rec["layers"][int(i or 1) - 1]


def enum_tail(v):
    v = v.get("Enum") if isinstance(v, dict) else v
    return str(v or "").split(".")[-1]


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--lib", required=True)
    ap.add_argument("refs", nargs="*", help="layer refs Stem#i")
    ap.add_argument("--ids", nargs="*", default=[], help="raw texture asset ids")
    ap.add_argument("--size", default="420x420", help="thumbnail size (420x420 is always offered)")
    ap.add_argument("--frames", help="write a frame contact sheet PNG here")
    ap.add_argument("--cell", type=int, default=110, help="frame cell px on the sheet")
    a = ap.parse_args()
    lib = Path(a.lib)
    rdir = lib / "recipes"
    hi = lib / ".cache" / "tex_hi"
    hi.mkdir(parents=True, exist_ok=True)
    want = []  # (label, id, grid)
    for ref in a.refs:
        p = layer_of(rdir, ref)["props"]
        m = re.search(r"(\d{5,})", str(p.get("Texture") or ""))
        if not m:
            print(f"NO TEXTURE ID  {ref}: {p.get('Texture')!r}")
            continue
        want.append((ref, m.group(1), GRID.get(enum_tail(p.get("FlipbookLayout")), 1)))
    want += [(i, i, 1) for i in a.ids]
    todo = sorted({i for _, i, _ in want if not (hi / f"{i}.png").is_file()})
    for k in range(0, len(todo), 100):
        d = http("https://thumbnails.roblox.com/v1/assets?assetIds=" + ",".join(todo[k:k + 100])
                 + f"&size={a.size}&format=Png")
        got = {str(x["targetId"]): x for x in (d or {}).get("data", [])}
        for i in todo[k:k + 100]:
            x = got.get(i)
            if not x or x.get("state") != "Completed" or not x.get("imageUrl"):
                print(f"NOT FETCHED  {i}: {x.get('state') if x else 'no reply'}")
                continue
            b = http(x["imageUrl"], raw=True)
            if b:
                (hi / f"{i}.png").write_bytes(b)
    ok = [(lab, i, g) for lab, i, g in want if (hi / f"{i}.png").is_file()]
    print(f"{len(ok)}/{len(want)} high-res textures in {hi}")
    if a.frames and ok:
        from PIL import Image, ImageDraw
        c = a.cell
        rows = []
        for lab, i, g in ok:
            im = Image.open(hi / f"{i}.png").convert("RGBA")
            fw = im.size[0] // g
            frames = [im.crop(((n % g) * fw, (n // g) * fw, (n % g + 1) * fw, (n // g + 1) * fw)) for n in range(g * g)]
            rows.append((lab, frames))
        per = 16
        h = sum(((len(f) + per - 1) // per) * c + 14 for _, f in rows)
        S = Image.new("RGB", (per * c, h), (90, 90, 90))
        d = ImageDraw.Draw(S)
        y = 0
        for lab, frames in rows:
            d.text((2, y), lab, fill=(255, 255, 0))
            y += 14
            for n, fr in enumerate(frames):
                t = fr.resize((c - 2, c - 2))
                bg = Image.new("RGBA", t.size, (90, 90, 90, 255))
                bg.alpha_composite(t)
                S.paste(bg.convert("RGB"), ((n % per) * c + 1, y + (n // per) * c + 1))
            y += ((len(frames) + per - 1) // per) * c
        S.save(a.frames)
        print("frames ->", a.frames, S.size)
    return 0 if len(ok) == len(want) else 1


if __name__ == "__main__":
    sys.exit(main())
