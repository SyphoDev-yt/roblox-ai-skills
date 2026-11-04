"""Re-render a subset of families (limit 1 per style) for a quick visual check.

    python run_subset.py fire_loop explosion ...
Writes them into the library and rebuilds catalog entries for them only.
"""
import json
import sys
from multiprocessing import Pool

import build_library as B
import texcore as C

if __name__ == "__main__":
    fams = set(sys.argv[1:])
    J = [j for j in B.jobs(None, 1) if j[2] in fams]
    with Pool(11) as p:
        R = p.map(B.render, J)
    errs = [r["error"] for r in R if "error" in r]
    for e in errs:
        print("ERROR", e[:400])
    R = [r for r in R if "error" not in r]
    for r in R:
        r["tags"] = []
        r["id"] = "sim:lib/" + r["file"][:-4]
    path = C.LIB / "catalog.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({"textures": R}))
    print(len(R), "rendered")
