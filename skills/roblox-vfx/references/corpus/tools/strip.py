"""Numbered frame strip of a short window, optional crop.
usage: python strip.py SRC START END OUT.png [--step 1] [--cols 6] [--w 320] [--crop w:h:x:y]
--step N keeps every Nth native frame. Labels: tile index, native frame offset, ms from START.
"""
import argparse, subprocess, tempfile, glob, os, json
from PIL import Image, ImageDraw, ImageFont

ap = argparse.ArgumentParser()
ap.add_argument("src"); ap.add_argument("start", type=float); ap.add_argument("end", type=float)
ap.add_argument("out")
ap.add_argument("--step", type=int, default=1)
ap.add_argument("--cols", type=int, default=6)
ap.add_argument("--w", type=int, default=320)
ap.add_argument("--crop")
a = ap.parse_args()

fr = subprocess.run(["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries",
                     "stream=r_frame_rate", "-of", "json", a.src], capture_output=True, text=True)
num, den = json.loads(fr.stdout)["streams"][0]["r_frame_rate"].split("/")
fps = float(num) / float(den)
vf = []
if a.crop:
    vf.append("crop=" + a.crop)
vf.append(f"select='not(mod(n\\,{a.step}))'")
vf.append(f"scale={a.w}:-2")
tmp = tempfile.mkdtemp()
subprocess.run(["ffmpeg", "-v", "error", "-ss", str(a.start), "-i", a.src, "-t", str(a.end - a.start),
                "-vf", ",".join(vf), "-vsync", "vfr", os.path.join(tmp, "%04d.png")], check=True)
files = sorted(glob.glob(os.path.join(tmp, "*.png")))
ims = [Image.open(f).convert("RGB") for f in files]
tw, th = ims[0].size
lab = 18
rows = (len(ims) + a.cols - 1) // a.cols
sheet = Image.new("RGB", (a.cols * (tw + 4), rows * (th + lab + 4)), (20, 20, 24))
d = ImageDraw.Draw(sheet)
try:
    font = ImageFont.truetype("arial.ttf", 14)
except Exception:
    font = ImageFont.load_default()
for i, im in enumerate(ims):
    x, y = (i % a.cols) * (tw + 4), (i // a.cols) * (th + lab + 4)
    sheet.paste(im, (x, y))
    nf = i * a.step
    d.text((x + 3, y + th + 2), f"#{i} f+{nf} {nf / fps * 1000:.0f}ms", fill=(230, 230, 230), font=font)
sheet.save(a.out)
print(a.out, len(ims), "tiles", sheet.size, f"fps={fps:.2f}")
