# Signature beats

A signature beat is the one moment a player remembers. Every effect picks
ONE or TWO (more and nothing stands out). Counts are from the corpus batches
(of ~10 per batch); "family" says where it belongs. Each has a Roblox build.

| Beat | Seen | Family | Build in Roblox |
|---|---|---|---|
| **Dark beat before release** (black/grey frames, lights dim, charge collapses) | 6/10 beams, 6/10 impacts, 6/10 auras | all (anime strongest) | ColorCorrection Brightness -0.4..-0.8 for 2-20 frames, or dim the charge emitters to 0 just before the flash |
| **Suck-in / contraction** before a burst | 4/14 moves, cone contracts 4 frames | anime, game | tween the charge mesh/ring Size down 15-30 % in 0.06-0.1 s (Quart In), then release |
| **1-2 frame white flash, hard off** | most strikes, teleports, reactions | anime, game (contact only) | ColorCorrection Brightness 1 for 1 frame or a white ScreenGui Frame |
| **Held, tinted whiteout** then a cooling arc | climaxes (8/10 auras tinted) | anime set-pieces | ColorCorrection Brightness 0.9 + TintColor, hold 0.3-1.6 s, then tween TintColor through cream/yellow/orange (or the theme's arc) |
| **Inverted / B&W impact frames**, black separators, stepped on 3s | 5/10 beams, 5/10 impacts, 4/4 ultimates | anime big moves only | full-screen ScreenGui images or Saturation -1 + Contrast frames; 8-17 frames total |
| **Escalating impact frames** (each bigger) | 5/10 impacts | anime | 2-3 impact frame groups, each with a larger burst sprite |
| **Colour swap at release / through white** | 5/13 elemental, KonoSuba, Super Saiyan | anime, game reactions | charge in hue A; flash; everything after in hue B (complementary) |
| **Cut to a far wide shot** for the payoff | 5/10 beams, set-pieces | anime, realistic | CameraType Scriptable, cut (no tween) to a wide locked-off CFrame; restore after |
| **World regrade per phase** (desaturate on charge, sky darkens first) | 7/10 auras, 6/10 impacts | anime, realistic | ColorCorrection Saturation -0.6 + TintColor, Lighting/Atmosphere tweens |
| **Shape born at full size** (no grow-in) | slashes, 6/10 impacts | all | emit the crescent/burst at final Size on frame 1, animate rotation/fade not scale |
| **Squash to a dome + horizontal shock ring** | explosions | anime | sphere shells tween to 1.2:0.62:1.2 while a flat ring mesh races to 5R |
| **Strobe / flicker in sustain** (1-2 frames per state) | 6/10 beams | anime beams | toggle core Transparency or swap texture every 2 frames; keep < 3 Hz for full-screen strobes |
| **Helical rings / segments** on a beam | SBC, Godzilla vs Kong | anime, realistic | spiral mesh or Beam pairs with CurveSize, rings spawned along the path |
| **Stacked staggered circles** | KonoSuba, Roblox showcases | anime | plane meshes with SurfaceAppearance sigils, scale in 0.4 s Quart Out, 0.1-0.25 s apart |
| **Telegraph line** before damage | game beams (2/2) | stylised_game | thin Beam along the path, colour yellow -> orange -> red over ~0.9 s |
| **Residue that outlasts the hit** (scorch, ice, smoke, embers, hanging glyph) | 6-7 per batch | all | decal/plane mesh, slow-fading particles, physics rock Parts |
| **Opposing elements make a third state** | 3/13 | game, anime | two coloured charges meet; the burst uses a THIRD hue (steam, purple, shower) |
| **Payoff held still** (freeze frame) | 3/10 auras | anime | TimeScale 0 on emitters + pause tweens for 0.2-0.5 s, then resume |
| **Streaks wrap the target, reappear in end pose** | Raijin | anime dash | Trails/Beams spiral round the target for 0.2 s, character teleported between white frames |
| **Two-stage onset** (pop to ~35 %, hold, surge) | Godzilla Minus One | realistic, anime | width tween to 0.35 (Quart Out 0.05 s), hold 0.4 s, then surge to 1.0 (Quad In) |
