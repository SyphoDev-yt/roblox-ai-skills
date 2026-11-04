"""Per-frame numeric measures over a window (no images to read).
usage: python measure.py SRC START END OUT.csv [--thr 200] [--crop w:h:x:y]
Columns: frame offset, t, diff (mean abs luma diff vs previous frame, 0-255; ~0 => animation hold),
bright_frac (luma>thr), bbox of bright region as fractions of frame (x0,y0,x1,y1, w, h),
bright centroid, mean RGB hex of bright pixels, mean RGB hex of whole frame, white_frac (all ch>235).
"""
import argparse, subprocess, json, numpy as np, csv

ap = argparse.ArgumentParser()
ap.add_argument("src"); ap.add_argument("start", type=float); ap.add_argument("end", type=float); ap.add_argument("out")
ap.add_argument("--thr", type=int, default=200)
ap.add_argument("--crop")
ap.add_argument("--w", type=int, default=480)
a = ap.parse_args()
fr = subprocess.run(["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries", "stream=r_frame_rate",
                     "-of", "json", a.src], capture_output=True, text=True)
n, d = json.loads(fr.stdout)["streams"][0]["r_frame_rate"].split("/"); fps = float(n) / float(d)
vf = (["crop=" + a.crop] if a.crop else []) + [f"scale={a.w}:-2"]
probe = subprocess.run(["ffmpeg", "-v", "error", "-ss", str(a.start), "-i", a.src, "-frames:v", "1", "-vf", ",".join(vf),
                        "-f", "image2pipe", "-vcodec", "png", "-"], capture_output=True)
from PIL import Image
import io
W, H = Image.open(io.BytesIO(probe.stdout)).size
p = subprocess.Popen(["ffmpeg", "-v", "error", "-ss", str(a.start), "-i", a.src, "-t", str(a.end - a.start), "-vf", ",".join(vf),
                      "-f", "rawvideo", "-pix_fmt", "rgb24", "-"], stdout=subprocess.PIPE)
hexs = lambda c: "#%02x%02x%02x" % tuple(int(x) for x in c)
prev = None; i = 0; rows = []
while True:
    buf = p.stdout.read(W * H * 3)
    if len(buf) < W * H * 3:
        break
    im = np.frombuffer(buf, np.uint8).reshape(H, W, 3).astype(np.float32)
    y = 0.299 * im[..., 0] + 0.587 * im[..., 1] + 0.114 * im[..., 2]
    diff = float(np.abs(y - prev).mean()) if prev is not None else 0.0
    prev = y
    m = y > a.thr
    bf = float(m.mean())
    if m.any():
        ys, xs = np.nonzero(m)
        x0, x1 = np.percentile(xs, 2) / W, np.percentile(xs, 98) / W
        y0, y1 = np.percentile(ys, 2) / H, np.percentile(ys, 98) / H
        cx, cy = xs.mean() / W, ys.mean() / H
        bc = hexs(im[m].mean(0))
    else:
        x0 = x1 = y0 = y1 = cx = cy = 0; bc = ""
    wf = float((im.min(2) > 235).mean())
    rows.append([i, round(a.start + i / fps, 3), round(diff, 2), round(bf, 4), round(x0, 3), round(y0, 3), round(x1, 3), round(y1, 3),
                 round(x1 - x0, 3), round(y1 - y0, 3), round(cx, 3), round(cy, 3), bc, hexs(im.reshape(-1, 3).mean(0)), round(wf, 4)])
    i += 1
with open(a.out, "w", newline="") as fh:
    w = csv.writer(fh)
    w.writerow(["f", "t", "diff", "bright_frac", "x0", "y0", "x1", "y1", "bw", "bh", "cx", "cy", "bright_rgb", "mean_rgb", "white_frac"])
    w.writerows(rows)
print(a.out, len(rows), "frames", f"fps={fps:.3f}")
