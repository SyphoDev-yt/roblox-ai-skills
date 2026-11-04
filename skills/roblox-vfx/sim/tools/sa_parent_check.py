"""Fail any effect whose SurfaceAppearance is not parented to a MeshPart (Studio refuses to build it:
"SurfaceAppearance can only be parented to MeshParts" - Kurohitsugi v5).

    python sim/tools/sa_parent_check.py [glob]      default: every effect JSON in sim/effects
"""
import glob
import json
import os
import sys

FX = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "effects")


def walk(node, bad, path):
    for c in node.get("children", []) or []:
        if c.get("class") == "SurfaceAppearance" and node.get("class") != "MeshPart":
            bad.append(f"{path}/{node.get('name', '?')} ({node.get('class')})")
        walk(c, bad, f"{path}/{node.get('name', '?')}")


def main():
    pat = sys.argv[1] if len(sys.argv) > 1 else os.path.join(FX, "*.json")
    files, fails = sorted(glob.glob(pat)), 0
    for f in files:
        d = json.load(open(f, encoding="utf-8"))
        if not isinstance(d, dict):
            continue
        bad = []
        for inst in d.get("instances", []):
            if inst.get("class") == "SurfaceAppearance":
                bad.append("(top level)")
            walk(inst, bad, "")
        if bad:
            fails += 1
            print(f"FAIL {os.path.basename(f)}: {len(bad)} -> {', '.join(bad[:6])}{' ...' if len(bad) > 6 else ''}")
    print(f"{len(files)} effects checked, {fails} with a SurfaceAppearance off a MeshPart")
    if not files:
        # a check that finds nothing to check must FAIL, not pass (2026-10-30: an unexpanded "~" in the glob matched
        # no files and this printed a green "0 effects checked")
        print(f"FAIL: no effect files matched {pat}")
        sys.exit(1)
    sys.exit(1 if fails else 0)


if __name__ == "__main__":
    main()
