"""The 24 letters of the Elder Futhark (historic runic alphabet, public domain)
as stroke polylines on a stave box: x in [-0.5, 0.5], y in [-1, 1] (the
stave runs the full height). Used by the rune sprites and the magic-circle
rune bands so runes read as REAL runes, not random lattice scribbles.
"""
import math

FUTHARK = {
    "fehu": [[(0, -1), (0, 1)], [(0, 0.15), (0.45, 0.6)], [(0, 0.55), (0.45, 1.0)]],
    "uruz": [[(-0.38, -1), (-0.38, 1), (0.38, 0.35), (0.38, -1)]],
    "thurisaz": [[(-0.1, -1), (-0.1, 1)], [(-0.1, 0.5), (0.4, 0.0), (-0.1, -0.5)]],
    "ansuz": [[(0, -1), (0, 1)], [(0, 1), (0.45, 0.55)], [(0, 0.5), (0.45, 0.05)]],
    "raidho": [[(-0.15, -1), (-0.15, 1)], [(-0.15, 1), (0.35, 0.55), (-0.15, 0.1), (0.4, -1)]],
    "kaunan": [[(0.3, 0.65), (-0.25, 0.0), (0.3, -0.65)]],
    "gebo": [[(-0.45, -1), (0.45, 1)], [(-0.45, 1), (0.45, -1)]],
    "wunjo": [[(-0.15, -1), (-0.15, 1)], [(-0.15, 1), (0.35, 0.55), (-0.15, 0.1)]],
    "hagalaz": [[(-0.38, -1), (-0.38, 1)], [(0.38, -1), (0.38, 1)], [(-0.38, 0.35), (0.38, -0.15)]],
    "naudiz": [[(0, -1), (0, 1)], [(-0.35, 0.35), (0.35, -0.2)]],
    "isa": [[(0, -1), (0, 1)]],
    "jera": [[(-0.08, 0.85), (-0.45, 0.4), (-0.08, -0.05)], [(0.08, 0.05), (0.45, -0.4), (0.08, -0.85)]],
    "eihwaz": [[(0, -1), (0, 1)], [(0, 1), (0.38, 0.65)], [(0, -1), (-0.38, -0.65)]],
    "perthro": [[(-0.2, -1), (-0.2, 1)], [(-0.2, 1), (0.3, 0.55), (0.3, 0.25)], [(-0.2, -1), (0.3, -0.55), (0.3, -0.25)]],
    "algiz": [[(0, -1), (0, 1)], [(0, 0.3), (-0.45, 0.95)], [(0, 0.3), (0.45, 0.95)]],
    "sowilo": [[(0.32, 1), (-0.32, 0.35), (0.32, -0.35), (-0.32, -1)]],
    "tiwaz": [[(0, -1), (0, 1)], [(0, 1), (-0.45, 0.5)], [(0, 1), (0.45, 0.5)]],
    "berkanan": [[(-0.2, -1), (-0.2, 1)], [(-0.2, 1), (0.35, 0.5), (-0.2, 0.0), (0.35, -0.5), (-0.2, -1)]],
    "ehwaz": [[(-0.4, -1), (-0.4, 1)], [(0.4, -1), (0.4, 1)], [(-0.4, 1), (0, 0.5), (0.4, 1)]],
    "mannaz": [[(-0.4, -1), (-0.4, 1)], [(0.4, -1), (0.4, 1)], [(-0.4, 1), (0.4, 0.2)], [(0.4, 1), (-0.4, 0.2)]],
    "laguz": [[(-0.15, -1), (-0.15, 1)], [(-0.15, 1), (0.4, 0.5)]],
    "ingwaz": [[(0, 0.6), (0.4, 0.0), (0, -0.6), (-0.4, 0.0), (0, 0.6)]],
    "othala": [[(0, 1), (0.4, 0.45), (-0.38, -1)], [(0, 1), (-0.4, 0.45), (0.38, -1)]],
    "dagaz": [[(-0.42, 1), (-0.42, -1), (0.42, 1), (0.42, -1), (-0.42, 1)]],
}
NAMES = list(FUTHARK)


def place(strokes, cx, cy, h, ang=0.0, w_scale=1.0):
    """Stave-box strokes -> frame coordinates: height h (full stave), centred
    on (cx, cy), rotated by ang (radians, 0 = upright)."""
    c, s = math.cos(ang), math.sin(ang)
    out = []
    for poly in strokes:
        pts = []
        for px, py in poly:
            qx, qy = px * h * 0.5 * w_scale, py * h * 0.5
            pts.append((cx + qx * c - qy * s, cy + qx * s + qy * c))
        out.append(pts)
    return out


def bind(names):
    """A bind-rune: several runes sharing one central stave."""
    out = [[(0, -1), (0, 1)]]
    for k, nm in enumerate(names):
        for poly in FUTHARK[nm]:
            if len(poly) == 2 and poly[0][0] == poly[1][0] and abs(poly[0][1] - poly[1][1]) > 1.8:
                continue  # its own stave: replaced by the shared one
            sx = -1 if k % 2 else 1
            out.append([(px * sx, py) for px, py in poly])
    return out
