# Designing an ORIGINAL effect with no reference

Why this exists (2026-10-26): the KonoSuba-referenced explosion looked good;
the no-reference slash "doesnt look amazing". The reference supplied five
things the slash lacked: a timeline, motion curves, a colour story, a
signature beat, and staging. Without a reference they come from here:
the brief (intent), `references/corpus/` (measured skeletons),
`references/styles/` (look family), `references/BEATS.md` (the memorable
moment). Do every step; skipping the brief is exactly how the slash failed.

## 1. Write the brief (in the builder file's docstring)

```
Name:            <move name>
Fantasy:         <one line: what the player feels>
Tier:            basic | skill | big skill | ultimate   (sets the time budget, STYLES.md)
Style family:    anime_cel | realistic | stylised_game
Category:        beam | slash | impact | explosion | orb_charge | aura_transform | projectile | dash_teleport | elemental | ambient_pickup | ultimate
Shape word:      ONE word (crescent, shatter, bloom, spiral, needle, petal, fracture...)
Dominant hue:    #hex           Accent: #hex (complementary or cool vs warm)   Darks: #hex
Colour arc:      e.g. violet charge -> white flash -> gold body -> ash residue
Signature beat:  1-2 from BEATS.md (+ one twist of our own)
Timeline:        phases with seconds, taken from the category skeleton below, scaled to the tier
Staging:         camera (gameplay / cut / wide), shake, world grade
Residue:         what stays, and for how long (residue:main ratio)
```

Uniqueness comes from the shape word, the palette, and the twist on the
signature beat. Quality comes from the skeleton and the style rules.

## 2. Get the skeleton from the corpus

`python scripts/corpus_stats.py --cat <category>` prints the measured phase
shares, anticipation:release and residue:main ranges, flash frequency and
frames, layer counts and roles. Use the median as the target and stay inside
p25..p75 unless the brief says why not. `references/corpus/CATEGORIES.md`
holds the condensed skeleton per category.

## 3. Assets
Textures from `sim/tex/make_textures.py` (study-measured recipes; add a new
category there, then `texture-study/measure.py` against the references);
meshes from `sim/mesh/make_meshes.py`. Match the STYLE FAMILY: cel textures
for anime_cel, soft/blended for realistic, bright clean sprites for game.

## 4. Build as a parametric builder
`sim/effects/build_<name>.py`, every number from the brief + skeleton,
scaled from one size parameter. Layer roles to cover (corpus median 6-9
layers): flash, core, body, secondary strokes, sparks, ground, residue,
screen, light. Distinct lifetimes per layer.

## 5. Critic loop (do not grade your own work by eye alone)
1. **Numeric gate:** `python scripts/critic_gate.py sim/effects/<file>.json
   [--metrics strip_metrics.json]` checks the definition against the category
   skeleton and the universal rules (flash hard-off, peak in the first quarter
   of the main event, residue ratio in range, layer count, distinct
   lifetimes, accent present, no linear whole-effect fades, strobe < 3 Hz).
   Fix every FAIL.
2. **Blind review:** spawn ONE reviewer agent with: a numbered strip of our
   effect and 2-3 strips of pro corpus effects of the same category (from
   `<your VFX research folder>/corpus/<batch>/sheets`, set in `LOCAL.md`), shuffled and
   unlabelled, plus `references/styles/<family>.md`. Ask: "rank these by
   professional quality; for the weakest, list the 3 concrete defects in
   VFX terms". If ours ranks last, fix the named defects and repeat (max 3
   rounds; then report honestly).
3. Render the MP4 (`app.captureFrame(t, 1920, 1080)` per frame, POST each
   to `/save`, ffmpeg at 60 fps) for the user.

Blind strips: `app.strip(times, {blind: true})` labels frames `#n` only.
Without it the luma readout identified our strips to the reviewer.

## What the first blind reviews taught (2026-10-27, Eclipse Rend + Riptide Lance)

Scores out of 10 against pro strips: Eclipse Rend climbed from "last,
procedural" to 6/10 over four rounds (a pro Roblox slash scored 5, the Twist
VFX slash 7.5); Riptide Lance 4.5. The defects that kept recurring are now
rules:

1. **Geometric regularity is the giveaway.** Exact circles, evenly spaced
   spikes or rings, ruler-straight lines, identical repeated sprites, flat
   slab fills: "a parameter preset, not a drawing". Use the PAINTED tier
   (`sim/tex/vfxpaint.py` brush engine, `sim/tex/make_painted.py`): every
   shape is many tapered, wandering strokes of different weight and value.
2. **Never a full-screen white for a skill.** The flash is local (flare at
   the contact) or thematic (an eclipse DARKENS); full white only for
   ultimates, 1-2 frames.
3. **Dark layers must be translucent and fade at the edges,** or they read
   as an opaque black slab.
4. **A white-hot leading edge along the whole stroke** that cools to the
   hue: a separate rim layer painted from the SAME strokes (qmax filter),
   thin, not a second body.
5. **Erode over 6-8 frames, don't fade;** keep residue ~0.4 s for a skill
   and attach it to the effect.
6. **Additive cores eat the body colour:** keep the core thin and the body
   alpha-blended (LightEmission ~0.35) or the beam reads pure white.
7. **Check every CFrame "by" spec:** [x,y,z,rx,ry,rz], a rotation in the
   translation slots flew rings 120 studs away.
Open: the reviewer still wants the crescent to draw on over 2-3 frames and
sweep (it holds), the beam to lose its uniform cylinder look, and impact
sparks in the beam's palette.
