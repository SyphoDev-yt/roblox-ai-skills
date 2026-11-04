"""Contact sheets of the texture library, one per kind+category, composited on
a dark slate so white/grey textures read. Flipbooks show 6 frames across.

    python contact_sheets.py [--out DIR] [--cell 128] [--filter text]
"""
import argparse
import json
from pathlib import Path

from PIL import Image, ImageDraw

LIB = Path(__file__).resolve().parent.parent.parent / "textures" / "lib"


def tile(path, entry, cell):
    im = Image.open(LIB / path).convert("RGBA")
    bg = Image.new("RGBA", im.size, (30, 36, 52, 255))
    bg.alpha_composite(im)
    if entry["kind"] == "flip":
        g = entry["grid"]
        n = im.size[0] // g
        N = g * g
        picks = [0, N * 2 // 16, N * 4 // 16, N * 7 // 16, N * 10 // 16, N * 13 // 16]
        strip = Image.new("RGB", (cell * 6, cell))
        for j, k in enumerate(picks):
            fr = bg.crop(((k % g) * n, (k // g) * n, (k % g + 1) * n, (k // g + 1) * n)).resize((cell, cell))
            strip.paste(fr.convert("RGB"), (j * cell, 0))
        return strip
    if entry["kind"] == "beam":
        return bg.convert("RGB").resize((cell * 2, cell // 2))
    return bg.convert("RGB").resize((cell, cell))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=str(LIB / "_sheets"))
    ap.add_argument("--cell", type=int, default=128)
    ap.add_argument("--filter", default="")
    args = ap.parse_args()
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    cat = json.loads((LIB / "catalog.json").read_text())["textures"]
    groups = {}
    for e in cat:
        if args.filter and args.filter not in e["file"]:
            continue
        groups.setdefault((e["kind"], e["category"]), []).append(e)
    for (kind, c), es in sorted(groups.items()):
        tiles = [(e, tile(e["file"], e, args.cell)) for e in es]
        w = tiles[0][1].size[0]
        h = tiles[0][1].size[1] + 14
        cols = max(1, 1600 // w)
        rows = (len(tiles) + cols - 1) // cols
        sheet = Image.new("RGB", (cols * w, rows * h), (12, 14, 20))
        d = ImageDraw.Draw(sheet)
        for i, (e, t) in enumerate(tiles):
            x0, y0 = (i % cols) * w, (i // cols) * h
            sheet.paste(t, (x0, y0))
            d.text((x0 + 2, y0 + h - 13), Path(e["file"]).stem[:28], fill=(170, 180, 200))
        sheet.save(out / f"{kind}_{c}.jpg", quality=82)
        print(out / f"{kind}_{c}.jpg", len(es))


if __name__ == "__main__":
    main()
