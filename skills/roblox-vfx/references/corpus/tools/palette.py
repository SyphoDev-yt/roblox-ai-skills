"""Dominant colours (k-means) for named frames -> JSON + swatch PNG.
usage: python palette.py spec.json out.json out.png
spec: [{"name":..., "src":..., "t":sec, "crop":"w:h:x:y" (optional), "k":6}]
"""
import json, sys, subprocess, numpy as np
from PIL import Image, ImageDraw, ImageFont

spec = json.load(open(sys.argv[1]))
res = []
for s in spec:
    vf = (["crop=" + s["crop"]] if s.get("crop") else []) + ["scale=160:-2"]
    out = subprocess.run(["ffmpeg", "-v", "error", "-ss", str(s["t"]), "-i", s["src"], "-frames:v", "1", "-vf", ",".join(vf),
                          "-f", "rawvideo", "-pix_fmt", "rgb24", "-"], capture_output=True).stdout
    px = np.frombuffer(out, np.uint8).reshape(-1, 3).astype(np.float32)
    k = s.get("k", 6)
    rng = np.random.default_rng(0)
    c = px[rng.choice(len(px), k, replace=False)]
    for _ in range(25):
        lab = ((px[:, None, :] - c[None]) ** 2).sum(2).argmin(1)
        c = np.array([px[lab == j].mean(0) if (lab == j).any() else c[j] for j in range(k)])
    share = np.bincount(lab, minlength=k) / len(px)
    order = np.argsort(-share)
    cols = [{"hex": "#%02x%02x%02x" % tuple(int(v) for v in c[j]), "share": round(float(share[j]), 3)} for j in order]
    res.append({"name": s["name"], "src": s["src"], "t": s["t"], "colours": cols})
json.dump(res, open(sys.argv[2], "w"), indent=1)
W, rowh = 900, 34
im = Image.new("RGB", (W, rowh * len(res)), (24, 24, 28))
d = ImageDraw.Draw(im)
try:
    f = ImageFont.truetype("arial.ttf", 12)
except Exception:
    f = ImageFont.load_default()
for i, r in enumerate(res):
    y = i * rowh
    d.text((4, y + 10), r["name"][:34], fill=(230, 230, 230), font=f)
    x = 260
    for c in r["colours"]:
        w = max(8, int(600 * c["share"]))
        d.rectangle([x, y + 2, x + w, y + rowh - 4], fill=c["hex"])
        if w > 50:
            d.text((x + 3, y + 10), c["hex"], fill=(0, 0, 0) if sum(int(c["hex"][j:j + 2], 16) for j in (1, 3, 5)) > 380 else (255, 255, 255), font=f)
        x += w + 2
im.save(sys.argv[3])
for r in res:
    print(r["name"], " ".join(f"{c['hex']}({c['share']})" for c in r["colours"]))
