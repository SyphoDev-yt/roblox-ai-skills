# VFX style families

Measured from the effect-DNA corpus (`../corpus/`, 50+ effects, 2026-10-27)
and a study of pro VFX textures (rules in `sim/tex/vfxtex.py`). Pick ONE
family per effect (per game, ideally) and follow only that family's rules: a
cel slash next to a realistic fireball reads as two games. Each family has its
own file here; this page is the router.

| Family | File | Use for | One-line signature |
|---|---|---|---|
| `anime_cel` | `anime_cel.md` | battlegrounds, anime fighting, magic RPGs, any "anime" brief | hard cel shapes, holds on 2s, 1-2 frame flashes, dark beat before release, tinted whiteouts, world regrade |
| `realistic` | `realistic.md` | shooters, survival, military, horror, grounded sims | smooth motion, blackbody colour, light on the world instead of a whiteout, debris and dust swallow the fire |
| `stylised_game` | `stylised_game.md` | simulators, tycoons, MOBA-like PvP, cosy games, pickups/UI feedback | readability first, telegraphs, short pops, saturated element hues + white core, no screen flash on normal skills |

Roblox showcases are not a style: they are the evidence of what Roblox can
express and where Roblox artists fall short (see "Roblox lessons" below).

## Scale: cinematic vs gameplay

Anime and film durations are CINEMATIC (cutaways, held shots: beams 14-30 s,
impacts 4-22 s). Never copy the seconds. Copy the RATIOS and SHAPES, then fit
the gameplay budget:

| Tier | Budget | Allowed |
|---|---|---|
| basic attack / pickup | 0.3-0.8 s | no screen effects; residue <= 1 s |
| skill | 0.8-2.0 s | 1-2 frame flash on contact, light shake, short residue |
| big skill | 2-4 s | dark beat, impact frames (1-3), world tint |
| ultimate / set-piece | 4-15 s | camera cuts, held whiteout, full regrade, long residue |

Measured: impact frames and held whiteouts appear on 4/4 ultimates and 0/9
ordinary moves (video teardown); the anime corpus keeps 1-2 frame flashes
for strikes and saves held whiteouts (0.35-1.6 s) for climaxes.

## Rules that held across EVERY family

1. **Peak early, die late.** The brightest moment lands in the first quarter
   of the main event; the residue outlasts it (residue:main medians 0.35-1.4,
   up to 5 on set-pieces).
2. **Hard-off flashes.** Where there is a flash it switches off in 1-2 frames
   (5/10 impacts, 7/10 auras hard-off; the exceptions are deliberate ramps).
3. **Body appears big.** Main shapes appear at 40-94 % of full size, not from
   a point (6/10 impacts; slashes full-size on frame 1). Only realistic
   fireballs grow from ~20 %.
4. **A complementary or cool accent against the dominant hue** (6/10 beams,
   6/10 impacts).
5. **White core** in 78-100 % of beams/explosions/impacts (old DBZ uses cream).
6. **Curve matches intent:** reveals ease OUT (half size in ~0.17 s), build-ups
   to a climax ease IN (accelerating whiteout, shield growth).

## Roblox lessons (from the Roblox showcases in the corpus)

Where Roblox artists fall short of the reference material, measured:
- **They overstay:** a void white phase of 5.2 s against the anime's 0.3 s; a
  frame held saturated yellow for 5 s; 4 s of dead time in a thunder move.
- **No cut, no scale:** gameplay-camera clips with no wide shot are the
  weakest in the beam batch.
- **Pop in steps:** no measured growth curve; elements appear and vanish in
  ~0.3 s steps.
- **Monotone colour:** no cooling arc (a red-only explosion).
What they do well and the corpus confirms: stacked flipbook rings, curved
beam slashes, ColorCorrection flashes, inverted impact frames, crater rock
Parts, glowing ground cracks.
