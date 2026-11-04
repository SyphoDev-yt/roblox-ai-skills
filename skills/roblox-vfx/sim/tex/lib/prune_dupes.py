"""Delete the near-duplicates found by dedupe.py (keeps the first of each
close pair) and drop them from catalog.json.

    python dedupe.py --thresh 0.2 && python prune_dupes.py
"""
import json
from pathlib import Path

LIB = Path(__file__).resolve().parent.parent.parent / "textures" / "lib"

pairs = json.loads((LIB / "dupes.json").read_text())
drop = set()
for a, b, _ in pairs:
    if a not in drop and b not in drop:
        drop.add(b)
for f in drop:
    (LIB / f).unlink(missing_ok=True)
cat = json.loads((LIB / "catalog.json").read_text())
cat["textures"] = [e for e in cat["textures"] if e["file"] not in drop]
(LIB / "catalog.json").write_text(json.dumps(cat, indent=0))
print(f"removed {len(drop)}; catalog now {len(cat['textures'])}")
