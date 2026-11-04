"""Surface textures for the prop / debris / creature meshes (make_props.py),
cel-shaded to match the effect style: 2-3 hard value levels, an inked crack or
edge line, never flat colour. Grey unless the material is defined by its
colour (gold, steel edge highlight, leather, fire feathers).

    python make_prop_tex.py
"""
import json

import numpy as np

import vfxtex as vt
from vfxtex import save, smooth

N = 512


def uvgrid(n=N, ss=2):
    m = n * ss
    c = (np.arange(m) + 0.5) / m
    u, v = np.meshgrid(c, c[::-1])
    return u, v


def out(name, rgb, a, meta):
    g, aa = vt.downsample(rgb, a, N)
    save(name, g, aa, meta)


def stone_cel():
    u, v = uvgrid()
    f = vt.fbm(u * 4, v * 4, 1.0, 5, seed=3, period=(4, 4))
    lev = np.where(f < 0.44, 0.42, np.where(f < 0.58, 0.62, 0.8))
    # cracks: thin dark lines along ridges of a second noise
    c = vt.fbm(u * 3, v * 3, 1.0, 4, seed=9, period=(3, 3))
    crack = np.abs(c - 0.5) < 0.012
    pits = vt.fbm(u * 18, v * 18, 1.0, 2, seed=21, period=(18, 18)) > 0.72
    g = np.where(crack, 0.12, np.where(pits, lev - 0.12, lev))
    out("stone_cel", np.clip(g, 0, 1), np.ones_like(g), {"use": "rock / crater / spire / stone fist (box UV), tint brown-grey", "grey": True})


def blade(name, split, body, edge, spine_dark, grip, hamon=True, chips=False):
    """U across (edge 0 -> spine 1), V along (blade tip 0 -> grip top 1)."""
    u, v = uvgrid()
    rgb = np.zeros(u.shape + (3,))
    rgb[:] = body
    # edge highlight band and spine shade
    rgb[u < 0.12] = edge
    rgb[(u > 0.12) & (u < 0.15)] = np.array(edge) * 0.8
    rgb[u > 0.78] = np.array(body) * spine_dark
    if hamon:
        line = 0.3 + 0.05 * np.sin(v * 70) + 0.02 * np.sin(v * 190)
        band = (u > 0.12) & (u < line)
        rgb[band] = np.array(body) * 0.6 + np.array(edge) * 0.4
        rgb[np.abs(u - line) < 0.008] = edge
    if chips:
        n = vt.fbm(v * 30, u * 3, 1.0, 2, seed=5) > 0.62
        rgb[(u < 0.1) & n] = np.array(body) * 0.5
    # a long specular streak down the flat
    rgb[np.abs(u - 0.55) < 0.025] = np.minimum(1, np.array(body) * 1.6 + 0.2)
    # guard and grip
    g0 = split
    rgb[(v > g0) & (v < g0 + 0.02)] = (0.85, 0.68, 0.3)
    gr = v >= g0 + 0.02
    diamond = (np.abs(((u * 4) % 1) - 0.5) + np.abs(((v * 40) % 1) - 0.5)) < 0.35
    rgb[gr] = grip
    rgb[gr & diamond] = np.minimum(1, np.array(grip) * 1.8 + 0.08)
    out(name, np.clip(rgb, 0, 1), np.ones(u.shape), {"use": f"blade ColorMap (U across edge->spine, V tip->grip, grip from v={split})", "grey": False})


def gold_metal():
    u, v = uvgrid()
    f = vt.fbm(u * 3, v * 6, 1.0, 4, seed=13, period=(3, 6))
    lev = np.where(f < 0.45, 0.55, np.where(f < 0.6, 0.78, 1.0))
    band = (np.abs(((v * 8) % 1) - 0.5) < 0.04)
    lev = np.where(band, 0.4, lev)
    rgb = np.stack([lev * 1.0, lev * 0.78, lev * 0.32], -1)
    out("gold_metal", np.clip(rgb, 0, 1), np.ones(u.shape), {"use": "ornate gold (portals, gate weapons, guards)", "grey": False})


def iron_cel():
    u, v = uvgrid()
    f = vt.fbm(u * 5, v * 5, 1.0, 4, seed=17, period=(5, 5))
    lev = np.where(f < 0.5, 0.28, np.where(f < 0.62, 0.45, 0.7))
    out("iron_cel", lev, np.ones(u.shape), {"use": "dark iron (chains), tint", "grey": True})


def ice_facet():
    u, v = uvgrid()
    f = vt.fbm(u * 3 + v * 2, v * 3, 1.0, 4, seed=23, period=(3, 3))
    lev = np.where(f < 0.46, 0.55, np.where(f < 0.6, 0.78, 0.95))
    streak = np.abs(((u * 7 + v * 3 + f) % 1) - 0.5) < 0.025
    g = np.where(streak, 1.0, lev)
    a = np.clip(0.72 + 0.28 * (g > 0.9), 0, 1)
    out("ice_facet", g, a, {"use": "ice crystal / ice block skin (translucent, white streaks), tint pale blue", "grey": True})


def book_cover():
    u, v = uvgrid()
    x, y = (u - 0.5) * 2, (v - 0.5) * 2
    f = vt.fbm(u * 6, v * 6, 1.0, 4, seed=29)
    leather = np.where(f < 0.5, 0.36, 0.46)
    rgb = np.stack([leather * 1.0, leather * 0.32, leather * 0.28], -1)
    gold = np.array((0.95, 0.75, 0.3))
    border = (np.abs(x) > 0.82) | (np.abs(y) > 0.86)
    inner = (np.abs(np.abs(x) - 0.74) < 0.02) & (np.abs(y) < 0.8) | (np.abs(np.abs(y) - 0.78) < 0.02) & (np.abs(x) < 0.76)
    r = np.hypot(x, y * 1.4)
    emblem = (np.abs(r - 0.32) < 0.03) | ((r < 0.22) & (np.abs(np.sin(np.arctan2(y, x) * 3)) > 0.6))   # a three-lobed clover-like seal (original)
    for m in (border, inner, emblem):
        rgb[m] = gold
    out("book_cover", np.clip(rgb, 0, 1), np.ones(u.shape), {"use": "grimoire cover (blade UV: u across, v along), leather + gold", "grey": False})


def paper():
    u, v = uvgrid()
    base = 0.92 + 0.05 * (vt.fbm(u * 4, v * 4, 1.0, 3, seed=31) - 0.5)
    lines = (np.abs(((v * 34) % 1) - 0.5) < 0.08) & (u > 0.1) & (u < 0.9) & (vt.fbm(u * 30, v * 34, 1.0, 1, seed=37) > 0.35)
    g = np.where(lines, 0.45, base)
    rgb = np.stack([g, g * 0.96, g * 0.86], -1)
    out("paper", np.clip(rgb, 0, 1), np.ones(u.shape), {"use": "grimoire pages, lines of script", "grey": False})


def feather_fire():
    """U across a feather, V along it (root 0 -> tip 1): white-hot root, yellow,
    orange, red tips, a dark vane line, ragged tip alpha."""
    u, v = uvgrid()
    f = vt.fbm(u * 3, v * 8, 1.0, 4, seed=41)
    t = np.clip(v + (f - 0.5) * 0.25, 0, 1)
    rgb = np.where(t[..., None] < 0.25, np.array((1, 0.97, 0.85)),
                   np.where(t[..., None] < 0.5, np.array((1, 0.85, 0.3)), np.where(t[..., None] < 0.78, np.array((1, 0.5, 0.12)), np.array((0.85, 0.18, 0.08)))))
    vane = np.abs(u - 0.5) < 0.015
    rgb[vane] = rgb[vane] * 0.7
    barbs = np.abs(((u * 2 - v * 10 + f) % 1) - 0.5) < 0.05
    rgb[barbs & ~vane] = np.minimum(1, rgb[barbs & ~vane] * 1.15)
    a = np.where(v > 0.85 + 0.12 * (f - 0.5) * 2, 0.0, 1.0)
    out("feather_fire", np.clip(rgb, 0, 1), a, {"use": "phoenix wings / tail / crest (U across, V root->tip), pre-coloured", "grey": False})


def petal():
    u, v = uvgrid()
    g = 0.65 + 0.35 * smooth(0.0, 0.7, v)
    vein = np.abs(u - 0.5) < 0.012
    g = np.where(vein & (v < 0.8), g * 0.85, g)
    out("petal_skin", g, np.ones(u.shape), {"use": "flower petals (V root->tip), tint per flower", "grey": True})


def wave_layers():
    """Thick wave mesh (U along the arc, V across: outer edge 1): an ink body
    with ragged alpha and a separate rim-only layer."""
    u, v = uvgrid()
    f = vt.fbm(u * 6, v * 2, 1.0, 4, seed=47, period=(6, 0))
    body_a = np.clip((0.9 - np.abs(v - 0.45) * 1.6 + (f - 0.5) * 0.4) * 4, 0, 1)
    g = np.where(f < 0.5, 0.06, 0.16)
    out("wave_body", g, body_a, {"use": "wave_blade dark body (alpha ragged), tint", "grey": True})
    rim = np.clip(1 - np.abs(v - 0.88 - (f - 0.5) * 0.08) / 0.05, 0, 1)
    rim = np.maximum(rim, np.clip(1 - np.abs(v - 0.12) / 0.03, 0, 1) * (f > 0.55))
    out("wave_rim", np.ones(u.shape), np.clip(rim * 1.6, 0, 1), {"use": "wave_blade rim-only layer (bright), tint", "grey": True})


def afterimage():
    u, v = uvgrid()
    streak = vt.fbm(u * 12, v * 1.2, 1.0, 3, seed=53)
    a = np.clip(0.55 + (streak - 0.5) * 1.2, 0.15, 0.9)
    out("afterimage", np.ones(u.shape), a, {"use": "translucent motion-smeared afterimage skin (fists, arms)", "grey": True})


def leaf():
    u, v = uvgrid()
    f = vt.fbm(u * 4, v * 4, 1.0, 3, seed=59)
    g = np.where(f < 0.5, 0.55, 0.75)
    g = np.where(np.abs(u - 0.5) < 0.01, 0.4, g)
    out("leaf", g, np.ones(u.shape), {"use": "flower stem + leaves, tint green", "grey": True})


def feather_blade():
    """A single flame feather for the card-built wings and tail (U across the card,
    V root 0 -> tip 1): the ALPHA is the feather silhouette (a tapered blade with a
    quill, notched barbs on the trailing edge, a pointed tip), so each card draws a
    separate feather instead of the cards merging into one flat shape (Studio
    round 4). Colour: white-hot root, yellow, orange, red tip."""
    u, v = uvgrid()
    x = (u - 0.5) * 2
    f = vt.fbm(u * 3, v * 8, 1.0, 4, seed=61)
    half = 0.86 * np.clip(np.sin(np.pi * np.clip(v * 1.02, 0, 1)) ** 0.55, 0, 1) * (1 - 0.35 * v)
    barbs = 0.12 * np.abs(np.sin(v * 38 + (x > 0) * 1.3)) * (v > 0.12)
    edge = half - np.where(x > 0, barbs, barbs * 0.4) + (f - 0.5) * 0.08
    a = np.clip((edge - np.abs(x)) * 60, 0, 1)
    a = np.where(v > 0.985, 0, a)
    t = np.clip(v + (f - 0.5) * 0.18, 0, 1)
    rgb = np.where(t[..., None] < 0.22, np.array((1, 0.97, 0.82)),
                   np.where(t[..., None] < 0.48, np.array((1, 0.82, 0.28)), np.where(t[..., None] < 0.78, np.array((1, 0.48, 0.12)), np.array((0.82, 0.16, 0.07)))))
    quill = np.abs(x) < 0.035 + 0.02 * (1 - v)
    rgb[quill] = np.minimum(1, rgb[quill] * 1.15 + 0.08)
    rim = (edge - np.abs(x)) < 0.05
    rgb[rim & ~quill] = rgb[rim & ~quill] * 0.78
    out("feather_blade", np.clip(rgb, 0, 1), a, {"use": "one flame feather per card (U across, V root->tip), alpha = feather silhouette", "grey": False})


if __name__ == "__main__":
    stone_cel()
    blade("blade_katana", 0.755, (0.72, 0.75, 0.8), (0.98, 0.99, 1.0), 0.65, (0.12, 0.1, 0.12))
    blade("blade_asta", 0.781, (0.13, 0.13, 0.15), (0.6, 0.6, 0.64), 0.7, (0.25, 0.12, 0.08), hamon=False, chips=True)
    blade("blade_light", 0.782, (1.0, 0.86, 0.45), (1.0, 1.0, 0.92), 0.85, (0.85, 0.65, 0.25), hamon=False)
    gold_metal()
    iron_cel()
    ice_facet()
    book_cover()
    paper()
    feather_fire()
    feather_blade()
    petal()
    wave_layers()
    afterimage()
    leaf()
    man = vt.OUT / "manifest.json"
    old = json.loads(man.read_text()) if man.exists() else {}
    old.update(vt.MANIFEST)
    man.write_text(json.dumps(old, indent=1))
    print("made", list(vt.MANIFEST))
