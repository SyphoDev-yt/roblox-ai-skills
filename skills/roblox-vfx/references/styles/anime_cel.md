# Style family: anime_cel

Evidence: corpus anime entries (Kamehameha, Final Flash, Hollow Purple,
Getsuga, Special Beam Cannon, Serious Punch, Detroit Smash, Howitzer, haki
clash, Rasenshuriken, Spirit Bomb, Super Saiyan, Unlimited Void, Bankai,
Chidori, Kirin, Fire Fist, glacier, water dragon, Flying Raijin, Zoro, Zenitsu,
Black Flash, KonoSuba Explosion) + the pro Roblox anime showcases.

## Look
- **Shapes are hard and flat.** Cel textures: ~1 px alpha edge, 2-3 grey
  levels, darker rim band (`slash_cel_4x4`, `fire_hot_4x4`, `smoke_cel_4x4`,
  `impact_burst_4x4`, `ring_cel_4x4`, sigils). Soft only as a separate halo.
- **Animation holds on 2s/3s.** Shapes re-randomise every 0.083-0.125 s
  instead of tweening smoothly (bolts redrawn on 2s-3s, puffs boil on 2-3s,
  Hollow Purple star pulses every 3 frames). In Roblox: FlipbookBlendFrames
  false, FlipbookFramerate 12-24, or re-emit/re-randomise on a 0.083 s timer.
- **White core, saturated rim, dark accents.** Peak is mostly white with the
  hue at the edges; inked/dark under-layers for contrast.
- **Tinted whiteouts.** 8/10 aura/domain whiteouts are tinted (cyan, violet,
  pink, lemon, warm), not neutral white.

## Timing grammar
- **Dark or quiet beat right before the brightest frame:** 6/10 beams, 6/10
  impacts, 6/10 auras (grey/black frames, lights dimming, the charge
  collapsing, 0.33-2.4 s blackouts on set-pieces).
- **Anticipation >> release:** beams median 26:1 (7-82); auras ~6:1. For
  gameplay: charge 0.4-1.0 s, release 1-3 frames.
- **Flashes:** strikes and teleports get 1-2 frame white (or black-then-white)
  frames; climaxes get held whiteouts 0.35-1.6 s (gameplay) and longer in
  cinematics. Teleports: white frames with SHRINKING gaps (0.2 s then 0.1 s),
  last one fading through the accent colour in ~0.13 s.
- **Impact frames** (inverted / posterised / flat silhouette, black separators,
  stepped on 3s at 60 fps): 5/10 beams, 5/10 impacts, 4/10 auras. Big moves only.
- **Escalation:** two or more impact frames that get bigger (5/10 impacts).
- **Payoff held still** on climaxes (3/10 auras): the frame freezes.
- **Long aftermath:** smoke, ice, burning fleets, embers for seconds.

## Staging
- Cut to a far, wide, calm shot for the payoff (5/10 beams); no camera shake
  in the wide shot, impact frames do that job.
- World regraded per phase (6-7/10): sky darkens before the form changes,
  desaturate during charge, colour swap at release.
- Colour swap THROUGH white at the moment of change (5/13 elemental).
- Speed-line backgrounds during travel (water dragon, Raijin).

## Build in Roblox
Particle cel flipbooks + MeshPart shells with SurfaceAppearance (emissive
mask), curved Beams for strokes, ColorCorrection for flash/whiteout/regrade
(TintColor through the measured hexes), full-screen ScreenGui frames for
inverted impact frames (a ColorCorrection cannot invert), Highlight for
contact flashes, camera cuts with CameraType Scriptable for set-pieces.
Keep flashes under 3 per second (photosensitivity).
