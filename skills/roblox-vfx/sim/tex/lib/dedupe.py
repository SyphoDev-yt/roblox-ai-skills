"""Precise duplicate check: alpha downsampled to 64 px (flipbooks: the frame at
peak coverage), compared within family+style by RELATIVE difference: sum|a-b| / sum(max(a,b)) (an absolute mean calls
any two sparse textures, sparks or thin lines, identical because both are
mostly empty).
Two textures closer than THRESH are duplicates; prints groups and, with
--report, the families that produce them (their parameter ranges are too
narrow and need widening).

    python dedupe.py [--thresh 0.025]
"""
import argparse
import json
from collections import defaultdict
from pathlib import Path

import numpy as np
from PIL import Image

LIB = Path(__file__).resolve().parent.parent.parent / "textures" / "lib"


def sig(e):
    im = Image.open(LIB / e["file"])
    a = np.asarray(im)[..., 3]
    if e["kind"] == "flip":
        g = e["grid"]
        n = a.shape[0] // g
        frames = [a[(k // g) * n:(k // g + 1) * n, (k % g) * n:(k % g + 1) * n] for k in range(g * g)]
        # 4 frames spread over the life: compare the motion, not just one pose
        pick = [frames[i] for i in (1, len(frames) // 4, len(frames) // 2, 3 * len(frames) // 4)]
        return np.concatenate([np.asarray(Image.fromarray(f).resize((48, 48), Image.BILINEAR), float).ravel() / 255 for f in pick])
    size = (128, 32) if e["kind"] == "beam" else (64, 64)
    al = np.asarray(Image.fromarray(a).resize(size, Image.BILINEAR), float) / 255
    # edges weighted in, so an interior mark (a rune cut into a tablet) counts
    # as much as the silhouette instead of vanishing under the solid area
    gy, gx = np.gradient(al)
    edge = np.clip(np.hypot(gx, gy) * 4, 0, 1)
    return np.concatenate([al.ravel(), edge.ravel() * 2])


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--thresh", type=float, default=0.3)
    a = ap.parse_args()
    cat = json.loads((LIB / "catalog.json").read_text())["textures"]
    groups = defaultdict(list)
    for e in cat:
        groups[(e["family"], e["style"])].append(e)
    dups = []
    per_family = defaultdict(int)
    for (fam, st), es in groups.items():
        S = [sig(e) for e in es]
        for i in range(len(es)):
            for j in range(i + 1, len(es)):
                d = float(np.abs(S[i] - S[j]).sum() / max(np.maximum(S[i], S[j]).sum(), 1e-6))
                if d < a.thresh:
                    dups.append((es[i]["file"], es[j]["file"], round(d, 4)))
                    per_family[fam] += 1
    print(f"{len(dups)} duplicate pairs")
    for fam, n in sorted(per_family.items(), key=lambda kv: -kv[1]):
        print(f"  {fam}: {n}")
    (LIB / "dupes.json").write_text(json.dumps(dups, indent=0))


if __name__ == "__main__":
    main()
