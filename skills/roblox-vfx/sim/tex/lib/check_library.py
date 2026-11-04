"""Numeric QA over the whole library (no images spent):
  - empty / near-empty textures (coverage < 0.3 %)
  - shapes touching the frame edge (sprites, flipbook frames)
  - flipbooks whose frames do not change, one-shots still visible on the last frame
  - near-duplicates within a family+style (thumbnail Hamming distance)
Prints a report and writes qa.json next to catalog.json.

    python check_library.py
"""
import json
from collections import defaultdict
from pathlib import Path

import numpy as np
from PIL import Image

ENDS_LIT = {"charge_in"}  # these one-shots end on a lit core by design (the release happens on the next layer)
LIB = Path(__file__).resolve().parent.parent.parent / "textures" / "lib"


def edge_alpha(a, frac=0.025):
    b = max(1, int(a.shape[0] * frac))
    return float(np.concatenate([a[:b].ravel(), a[-b:].ravel(), a[:, :b].ravel(), a[:, -b:].ravel()]).mean())


def main():
    cat = json.loads((LIB / "catalog.json").read_text())["textures"]
    issues = defaultdict(list)
    groups = defaultdict(list)
    for e in cat:
        if e["coverage"] < 0.003:
            issues["empty"].append(e["file"])
        a = np.asarray(Image.open(LIB / e["file"]))[..., 3] / 255.0
        if e["kind"] == "sprite" and edge_alpha(a) > 0.02:
            issues["touches_edge"].append(e["file"])
        if e["kind"] == "flip":
            g = e["grid"]
            n = a.shape[0] // g
            fr = [a[(k // g) * n:(k // g + 1) * n, (k % g) * n:(k % g + 1) * n] for k in range(g * g)]
            if max(edge_alpha(f) for f in fr) > 0.03:
                issues["touches_edge"].append(e["file"])
            diffs = [float(np.abs(fr[k + 1] - fr[k]).mean()) for k in range(len(fr) - 1)]
            if max(diffs) < 0.002:
                issues["static_flipbook"].append(e["file"])
            if not e.get("loop") and e["family"] not in ENDS_LIT and e.get("last", 0) > 0.02:
                issues["oneshot_not_gone"].append(e["file"])
        groups[(e["family"], e["style"])].append(e)
    # duplicates: run dedupe.py (relative alpha difference); a coarse thumbnail test here flagged distinct shapes
    counts = defaultdict(int)
    for e in cat:
        counts[e["kind"]] += 1
    print("counts", dict(counts), "total", len(cat))
    for k, v in issues.items():
        print(f"{k}: {len(v)}")
        for f in v[:8]:
            print("   ", f)
    (LIB / "qa.json").write_text(json.dumps({k: v for k, v in issues.items()}, indent=1))


if __name__ == "__main__":
    main()
