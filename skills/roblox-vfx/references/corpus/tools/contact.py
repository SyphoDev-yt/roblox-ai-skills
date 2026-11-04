"""Timestamped contact sheet: one tile every --every seconds.
usage: python contact.py SRC OUT.png [--every 2] [--start 0] [--end None] [--cols 14] [--w 160]
"""
import argparse, subprocess, tempfile, glob, os
from PIL import Image, ImageDraw, ImageFont

ap = argparse.ArgumentParser()
ap.add_argument("src"); ap.add_argument("out")
ap.add_argument("--every", type=float, default=2.0)
ap.add_argument("--start", type=float, default=0.0)
ap.add_argument("--end", type=float)
ap.add_argument("--cols", type=int, default=14)
ap.add_argument("--w", type=int, default=160)
a = ap.parse_args()
tmp = tempfile.mkdtemp()
cmd = ["ffmpeg", "-v", "error", "-ss", str(a.start), "-i", a.src]
if a.end:
    cmd += ["-t", str(a.end - a.start)]
cmd += ["-vf", f"fps=1/{a.every},scale={a.w}:-2", os.path.join(tmp, "%04d.png")]
subprocess.run(cmd, check=True)
files = sorted(glob.glob(os.path.join(tmp, "*.png")))
ims = [Image.open(f).convert("RGB") for f in files]
tw, th = ims[0].size
lab = 14
rows = (len(ims) + a.cols - 1) // a.cols
sheet = Image.new("RGB", (a.cols * (tw + 2), rows * (th + lab + 2)), (20, 20, 24))
d = ImageDraw.Draw(sheet)
try:
    font = ImageFont.truetype("arial.ttf", 12)
except Exception:
    font = ImageFont.load_default()
for i, im in enumerate(ims):
    x, y = (i % a.cols) * (tw + 2), (i // a.cols) * (th + lab + 2)
    sheet.paste(im, (x, y))
    t = a.start + i * a.every
    d.text((x + 2, y + th), f"{t:.1f}s", fill=(255, 255, 0), font=font)
sheet.save(a.out)
print(a.out, len(ims), sheet.size)
