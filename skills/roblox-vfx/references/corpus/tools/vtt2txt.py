"""Collapse a YouTube auto-caption VTT (rolling duplicates) into timestamped lines.
usage: python vtt2txt.py in.vtt out.txt [--chunk 20]   (one line per ~chunk seconds)
"""
import re, sys
src, out = sys.argv[1], sys.argv[2]
chunk = float(sys.argv[4]) if len(sys.argv) > 4 else 20.0
words, last = [], ""
t = 0.0
for line in open(src, encoding="utf-8"):
    m = re.match(r"(\d+):(\d+):([\d.]+) -->", line)
    if m:
        t = int(m.group(1)) * 3600 + int(m.group(2)) * 60 + float(m.group(3))
        continue
    if "-->" in line or not line.strip() or line.startswith(("WEBVTT", "Kind:", "Language:")):
        continue
    txt = re.sub(r"<[^>]+>", "", line).strip()
    if not txt or txt == last:
        continue
    # rolling captions repeat the previous line as a prefix
    if last and txt.startswith(last):
        txt_new = txt[len(last):].strip()
    else:
        txt_new = txt
    last = txt
    if txt_new:
        words.append((t, txt_new))
lines, cur, cur_t = [], [], None
for t, w in words:
    if cur_t is None:
        cur_t = t
    if t - cur_t > chunk and cur:
        lines.append((cur_t, " ".join(cur)))
        cur, cur_t = [], t
    cur.append(w)
if cur:
    lines.append((cur_t, " ".join(cur)))
with open(out, "w", encoding="utf-8") as fh:
    for t, s in lines:
        fh.write(f"[{int(t//60):02d}:{int(t%60):02d}] {s}\n")
print(len(lines), "lines")
