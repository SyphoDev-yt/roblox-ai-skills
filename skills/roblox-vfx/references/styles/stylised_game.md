# Style family: stylised_game

Evidence: corpus game entries (League: Lux Final Spark, Malphite Ground Slam,
revive; Genshin: Raiden ultimate, Overloaded reaction) + Roblox simulator
pickups, level-up and cash effects.

## Look
- **Readability over spectacle:** saturated element hue + white core, clean
  shapes, effects sized to gameplay hitboxes.
- **Cool leading edge on a warm body** (Malphite ring), element hue coding
  (electro purple, pyro orange, heal green).
- Text and arrows can carry meaning ("LEVEL UP!", upward chevrons).

## Timing grammar
- **Telegraph before damage:** beam skills draw a warning line along the path
  first (Lux 0.92 s, shifting yellow -> orange -> red); the anime family uses
  a charge instead.
- **Rings are born big and settle fast:** born at ~43 % of final radius, full
  in 0.2 s (Quint Out); the scorch lasts ~2.4x the ring.
- **No screen flash on normal skills;** a 1-frame contact flash only for
  reactions/crits (Genshin Overloaded: flash, ring builds 0.25 s, burst peaks
  +0.33 s, gone +0.65 s, damage number after the burst).
- **Utility pop shape (3/4 measured):** pop to max within 1 frame (< 0.2 s),
  fall to ~20 % within 0.15 s, plateau, gone in 0.5-1.5 s; repeats stack
  along a coin line. Soft exception: revive/buff ramps 0.3 s then sustains.
- **Ultimates:** dim to black, freeze frame, cinematic cut-in, ONE 17 ms
  white frame on the slash line, sigil, burst, then an empowered state with a
  darker world (~7 s).

## Staging
Gameplay camera; ultimates may cut in for < 2 s. Light shake on heavy hits
only. Opposing elements make a third state (water + fire = steam, pyro +
electro = burst): a strong idea for reaction systems.

## Build in Roblox
Bright sprite particles with LightEmission 0.4-0.7 (not 1, keeps colour on
pale maps), flat ground rings (MeshPart or flat particle), BillboardGui text
pops with a TweenService overshoot (Back Out), Highlight pulses on the target,
short PointLight pops. Keep total life under 1.5 s for anything that repeats.
