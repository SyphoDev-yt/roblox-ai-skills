"""Parse ffmpeg signalstats+scene metadata dumps and list luma events.

usage: python events.py frames/<id>.stats.txt [--fps 60] [--csv out.csv]
Prints: frames that are white flashes (YAVG jumps up vs local median),
black/dark impact frames (YAVG drops), hard scene cuts (scene score), and
a per-second luma summary so effects can be located without images.
"""
import re, sys, statistics, argparse

ap = argparse.ArgumentParser()
ap.add_argument("stats")
ap.add_argument("--csv")
ap.add_argument("--jump", type=float, default=25.0)
a = ap.parse_args()

rows = []
cur = None
for line in open(a.stats, encoding="utf-8", errors="ignore"):
    m = re.match(r"frame:(\d+)\s+pts:\S+\s+pts_time:([\d.]+)", line)
    if m:
        cur = {"f": int(m.group(1)), "t": float(m.group(2))}
        rows.append(cur)
        continue
    m = re.match(r"lavfi\.(\S+)=(\S+)", line)
    if m and cur is not None:
        k, v = m.group(1), m.group(2)
        if k in ("signalstats.YAVG", "signalstats.YMIN", "signalstats.YMAX",
                 "signalstats.SATAVG", "scene_score", "signalstats.YLOW", "signalstats.YHIGH"):
            cur[k.split(".")[-1]] = float(v)

if a.csv:
    with open(a.csv, "w") as fh:
        fh.write("f,t,yavg,ylow,yhigh,sat,scene\n")
        for r in rows:
            fh.write(f"{r['f']},{r['t']:.3f},{r.get('YAVG',0):.1f},{r.get('YLOW',0):.0f},{r.get('YHIGH',0):.0f},{r.get('SATAVG',0):.1f},{r.get('scene_score',0):.3f}\n")

y = [r.get("YAVG", 0) for r in rows]
n = len(y)
print(f"frames={n} dur={rows[-1]['t']:.2f}s median_luma={statistics.median(y):.1f}")
events = []
for i in range(n):
    lo, hi = max(0, i - 15), min(n, i + 16)
    win = y[lo:i] + y[i + 1:hi]
    med = statistics.median(win) if win else y[i]
    d = y[i] - med
    if abs(d) >= a.jump:
        events.append((i, d))
# group consecutive
groups = []
for i, d in events:
    if groups and i - groups[-1][-1][0] <= 2 and (d > 0) == (groups[-1][-1][1] > 0):
        groups[-1].append((i, d))
    else:
        groups.append([(i, d)])
print("LUMA EVENTS (start_t, nframes, sign, peak_delta, luma path):")
for g in groups:
    i0, i1 = g[0][0], g[-1][0]
    pk = max(g, key=lambda x: abs(x[1]))[1]
    path = " ".join(f"{y[k]:.0f}" for k in range(max(0, i0 - 2), min(n, i1 + 3)))
    print(f"  t={rows[i0]['t']:7.3f} f={i0:5d} n={i1 - i0 + 1:2d} {'BRIGHT' if pk > 0 else 'DARK  '} d={pk:+6.1f} | {path}")
print("SCENE CUTS (score>0.35):")
cuts = [(r["t"], r.get("scene_score", 0)) for r in rows if r.get("scene_score", 0) > 0.35]
print("  " + " ".join(f"{t:.2f}({s:.2f})" for t, s in cuts))
print("PER-SECOND mean luma / max-min / sat:")
sec = {}
for r in rows:
    sec.setdefault(int(r["t"]), []).append(r)
line = []
for s in sorted(sec):
    ys = [r.get("YAVG", 0) for r in sec[s]]
    ss = [r.get("SATAVG", 0) for r in sec[s]]
    line.append(f"{s}:{statistics.mean(ys):.0f}/{max(ys)-min(ys):.0f}/{statistics.mean(ss):.0f}")
for k in range(0, len(line), 10):
    print("  " + "  ".join(line[k:k + 10]))
