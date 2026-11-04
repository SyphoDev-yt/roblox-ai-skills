# Category skeletons (condensed from the corpus)

Live numbers: `python scripts/corpus_stats.py --cat <category>` (STATS.md /
STATS.json regenerate from `effects/*.json`). These are the shapes to build
inside. Seconds are GAMEPLAY-scaled (see styles/STYLES.md: cinematic
durations include cutaways; keep the ratios, fit the tier budget).

## slash (melee)
- Corpus: 8; flash in 88 %, 1 frame; 7 layers (6-7); white core 75 %;
  residue:main 0.35 (0.17-0.95). Anime: anticipation:release ~10:1.
- Skeleton (skill tier, ~0.9 s + residue): wind-up 0.12-0.3 s (blade glint,
  dark/quiet beat) -> release 1-2 frames, crescent FULL SIZE on frame 1 ->
  sustain 0.2-0.3 s (rotate on, strokes shrink) -> residue 0.3-0.8 s.
- Layers: dark under-layer + body + bright leading edge (+ glow), 5-12 curved
  stroke beams at different radii, 1-frame contact flare, sparks with gravity,
  ground/residue (wind, cut marks, leaves, smoke).
- Anime specifics: FLAT cel slash masses (not glowing gradients), inverted
  two-tone impact frames between multi-hit beats, holds that LENGTHEN as the
  mass dies (2s -> 3s -> 4s), whitening push-in right before a shatter.
- Realistic: single-frame contact flare, spark fan with gravity (not radial),
  white-hot -> red along spark life, world graded dark/cool.

## beam
- Corpus: 9; flash 100 %, 2 frames; 9 layers; white core 78 %; anticipation
  ~20:1 (cinematic); residue:main 0.6 (0.4-1.0).
- Skeleton (big skill ~3 s): charge 1-1.5 s (lights/plates in sequence,
  then DIM) -> dark beat 2-6 frames -> release flash 2 frames -> beam pops to
  ~35 %, surges to full (two-stage) -> sustain 0.8-1.5 s with 2-frame
  flicker -> impact (cut wide on ultimates) -> residue in a DIFFERENT colour.
- Layers: core cylinder (white) + outer body + rim in a complementary
  accent, helical rings/segments, sparks, ground scorch/trench, screen grade.
- Game variant: telegraph line yellow -> orange -> red (~0.9 s), peak 2
  frames (first with a dark core), decay ~0.5 s.

## impact / punch / ground slam
- Corpus: 6; flash 83 %; 9.5 layers; residue:main 0.35 (gameplay) up to 2.4.
- Skeleton: quiet beat 0.1-0.5 s -> DARK frame -> contact (body appears at
  40-94 % size) -> 2-3 ESCALATING impact frames (big moves) -> shock ring
  born at ~43 % radius, full in 0.2 s Quint Out -> residue (crater, scorch,
  lingering crackle) 1.4-2.4x the hit.
- Cool accent on a warm body; whole-world regrade on big hits.

## explosion
- Corpus: 6; flash 67 %, 4 frames typical; 8 layers; white core 100 %.
- Anime: KonoSuba skeleton (circles -> calm wide -> point/star/ring -> 1 white
  frame -> fireball 0.7R in 0.2 s Quart Out, 1.0R by 0.8 s -> squash to dome
  + shock rings -> held whiteout -> cooling -> mushroom -> embers).
- Realistic: fireball from 20 % (Quad Out 0.53 s), debris swallows it at
  ~0.5 s, dust plume grows ~1.5 s, brown edges, flash as light on the world.
- Stylised/Roblox: puffs pop with an 8-frame white core, cool to orange,
  char to black in ~0.85 s, glowing cracks stay.

## orb_charge
- Corpus: 3. Single point first; ring/portal half size in 0.17 s, full in
  1.3 s (ease out); sparks from the start; sustained orbs loop on 0.5-1 s
  with 2-frame flicker; release via an accelerating (ease-in) whiteout.

## aura_transform / ultimate (domains)
- Corpus: 4 auras + 3 ultimates; flash 75 %; 8 layers; white core only 25 %
  (tinted whiteouts 8/10).
- Skeleton: concealment / dark hold (0.6-2.4 s) -> 1-2 frame flash reveal ->
  colour fills from the ground up (33 -> 100 % in 0.7 s) -> sustain loop
  (2-frame flicker + 0.5-1 s secondary cycle) -> world regrade for the whole
  sustain (darker world, empowered state ~7 s in games).
- Domains: hand sign -> white 8 frames -> ink wipe 0.5 s -> world REPLACED
  (tunnel/void) -> payoff held as stills. Keep white phases ~0.3 s (the
  Roblox copy overstayed at 5.2 s).

## elemental / projectile
- Corpus: 7 + 2. Strikes flash (1-8 frames), sustained charges do not; bolts
  redrawn on 2s-3s, never tweened; colour swaps THROUGH white; world darkens
  around the element; ignition pops to ~22 % of frame in 1 frame then grows
  steadily; opposing elements make a third state; long residue (ice, smoke,
  burning, steam).

## dash_teleport
- Corpus: 1 (Raijin). 1-2 frame white frames with shrinking gaps (0.2 ->
  0.1 s), streaks wrap the target, last white decays through the accent in
  ~0.13 s, character reappears already in the end pose; total ~0.6 s.

## ambient_pickup (utility)
- Corpus: 3. Pop to max in 1 frame, ~20 % by 0.15 s, plateau, gone in
  0.5-1.5 s; stack along coin lines; text/arrows carry meaning; revive/buff
  ramps 0.3 s then sustains with a rune under the feet.
