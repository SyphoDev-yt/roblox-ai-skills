"""Search the generated texture library.

    python find_tex.py slash glow             # every word must match (tags, family, style, category, kind)
    python find_tex.py fire --kind flip       # sprite | flip | beam
    python find_tex.py ring --style cel -n 5
    python find_tex.py --stats                # counts by kind / category / style

Prints the sim id (use as Texture = "sim:lib/...") plus grid/tile notes.
"""
import argparse
import collections
import json
from pathlib import Path

LIB = Path(__file__).resolve().parent.parent.parent / "textures" / "lib"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("words", nargs="*")
    ap.add_argument("--kind")
    ap.add_argument("--style")
    ap.add_argument("-n", type=int, default=40)
    ap.add_argument("--stats", action="store_true")
    a = ap.parse_args()
    cat = json.loads((LIB / "catalog.json").read_text())["textures"]
    if a.stats:
        for key in ("kind", "category", "style"):
            c = collections.Counter(e[key] for e in cat)
            print(key, dict(sorted(c.items())))
        print("total", len(cat))
        return
    hits = []
    for e in cat:
        hay = " ".join([e["kind"], e["category"], e["family"], e["style"]] + e.get("tags", [])).lower()
        if a.kind and e["kind"] != a.kind:
            continue
        if a.style and e["style"] != a.style:
            continue
        if all(w.lower() in hay for w in a.words):
            hits.append(e)
    for e in hits[: a.n]:
        extra = f"  flipbook {e['grid']}x{e['grid']}{' loop' if e.get('loop') else ''}" if e["kind"] == "flip" else ("  tiles" if e.get("tile") else "") if e["kind"] == "beam" else ""
        print(f"{e['id']}{extra}")
    print(f"{len(hits)} match{'es' if len(hits) != 1 else ''}")


if __name__ == "__main__":
    main()
