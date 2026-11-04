# Style family: realistic

Evidence: corpus film/CG entries (Trinity test from Oppenheimer, Houdini
ground burst breakdown, Godzilla Minus One / vs Kong atomic breath,
Mandalorian darksaber sparks, Doctor Strange portal + shield, Harry Potter
fire blast + spell duel).

## Look
- **Smooth motion, no holds.** FlipbookBlendFrames ON, more frames, soft
  edges (`smoke_soft_4x4`, a smooth-ramp volume flipbook from
  `sim/blender/volume_flipbook.py` with a non-CONSTANT ramp).
- **Blackbody colour:** white -> yellow -> orange -> red -> BROWN -> grey.
  Fireball edges go brown, never black (Trinity).
- **Fire is short; debris and dust take over.** Houdini burst: fireball grows
  from 20 % of its final width (Quad Out, 0.53 s), spiky dirt debris swallows
  it at ~0.5 s, dust plume keeps growing ~1.5 s.
- **Sparks are physical:** gravity, drag, bounce; sparks fall from the first
  frame of a portal.

## Timing grammar
- **The flash is light ON THE WORLD, not a whiteout:** Trinity shows the flash
  as cyan light on faces; a linear ~0.4 s decay. In Roblox: PointLight /
  SpotLight pulse + ColorCorrection Brightness ramp, not a white frame.
- **Ease out for reveals** (portal: half size in 0.17 s, full in 1.3 s);
  **ease in for build-ups** (shield accelerates and hard-stops).
- **Two-stage onsets:** a beam pops to ~35 %, holds, then surges to full
  (+0.43 s); plates or lights come on in sequence before firing; lights DIM
  right before release.
- **Sound carries the hit** (Trinity: -26 dB to below -55 dB at ignition):
  pair with roblox-sfx, silence before the boom.

## Staging
Real camera shake (decaying, 0.3-0.8 s), no impact frames, no stepped
animation. Scale via haze/fog and distance. Colour grade stays natural;
at most a warm/cool shift and exposure bloom.

## Build in Roblox
Soft particle smoke and dust with high counts and drag, debris Parts or
tumbling rock flipbooks, PointLights for the flash on the world, Bloom spike,
Atmosphere/fog for scale, physical sparks (VelocityParallel, Acceleration
down, Drag). Avoid cel textures entirely.
