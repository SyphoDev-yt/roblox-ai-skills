# Effect DNA corpus: schema

One JSON file per analysed effect in `effects/<id>.json`. It stores the
ABSTRACT STRUCTURE of a pro effect (timing, curves, layer roles, colour arc,
signature beats, staging), never its artwork. Private study: designs are not
copied, only measured. `scripts/corpus_stats.py` aggregates the files into
per-category, per-style distributions that a new, original effect is built
inside.

Heavy working files (downloads, frames, strips) live OUTSIDE the skill in
`<your VFX research folder>/corpus/<batch>/` (the path is in `LOCAL.md`).

## Fields

```jsonc
{
  "id": "beam_kamehameha_dbz",            // <category>_<short>_<source>, snake_case, unique
  "name": "Kamehameha (DBZ)",             // human name of the move/effect
  "category": "beam",                     // beam | slash | impact | explosion | orb_charge | aura_transform
                                          // | projectile | dash_teleport | elemental | ambient_pickup | ultimate | other
  "subtype": "channelled energy beam",    // free text, one line
  "style": "anime_cel",                   // anime_cel | realistic | stylised_game | roblox
  "source": {"title": "...", "url": "https://youtu.be/...", "t_start": 12.3, "t_end": 19.8, "fps": 23.976,
             "kind": "anime | film | game | roblox_showcase", "notes": "on 2s; compilation edit"},
  "importance": 9,                        // 1-10 gameplay/story weight (Riot scale)
  "duration_s": 7.5,                      // first visible frame of the effect to last residue frame
  "phases": [                             // in order; times in seconds from effect start
    {"name": "anticipation", "t0": 0.0, "t1": 3.1, "what": "hands cup, blue orb grows, light gathers"},
    {"name": "release", "t0": 3.1, "t1": 3.2, "what": "..."},
    {"name": "sustain", "t0": 3.2, "t1": 6.0, "what": "..."},
    {"name": "impact", "t0": 6.0, "t1": 6.4, "what": "..."},
    {"name": "residue", "t0": 6.4, "t1": 7.5, "what": "..."}
  ],
  // canonical phase names: anticipation, quiet_beat, release, impact, sustain, peak, dissipation, residue
  "ratios": {"anticipation_to_release": 31.0, "residue_to_main": 0.6},  // measured, null if n/a
  "flash": {"frames": 2, "fps": 24, "peak_luma": 236, "kind": "white | inverted | tinted | none", "hard_off": true},
  "curves": [                             // normalised growth/motion of the main elements
    {"element": "beam width", "points": [[0, 0.1], [0.05, 0.8], [0.2, 1.0]], "x": "s from release", "y": "fraction of max",
     "easing": "Quart Out"}
  ],
  "colour_arc": [                         // what the frame/effect colour does over time
    {"t": 0.0, "hex": ["#2b6cff", "#bfe6ff"], "note": "blue charge"},
    {"t": 3.1, "hex": ["#ffffff"], "note": "white core at release"}
  ],
  "palette": {"dominant": "#3d8bff", "accent": "#ffffff", "darks": "#0b1a3a", "core_white": true,
              "accent_relation": "analogous | complementary | mono | triadic"},
  "layers": [                             // one per visual element, with its Roblox technique
    {"role": "core", "shape": "cylinder", "t0": 3.1, "t1": 6.0, "technique": "MeshPart cylinder + SurfaceAppearance emissive",
     "notes": "white, constant width with 2-frame jitter", "confidence": "high"}
  ],
  // roles: flash, core, body, secondary_strokes, sparks, smoke, ground, debris, residue, screen, camera, light, distortion
  "signature_beats": ["suck-in before release", "colour swap at release"],
  "staging": {"camera": "low angle close-up then wide", "shake": "on release, 0.3 s", "cuts": 3,
              "scale": "beam 0.3 screen wide", "world_grade": "desaturated during charge"},
  "pro_details": ["dark under-layer", "beam edge jitter on 2s"],  // what an amateur would miss
  "roblox_feasibility": "high | medium | low",                    // can Roblox express it, and how hard
  "measured": {"luma_csv": "corpus/<batch>/data/<id>.csv"},        // path under the research folder
  "confidence": "high | medium | low",
  "notes": "free text"
}
```

## Rules for analysts

- Time from FRAMES (per-frame luma / saturation via `tools/events.py`,
  `tools/measure.py`), not from watching. Note the source fps and whether the
  animation is on 2s/3s (`measure.py` diff ~0 = a hold).
- Strips at native fps for the release/impact windows (`tools/strip.py`);
  1-per-second sampling cannot see a 2-frame flash.
- Colours as hex sampled from frames (`tools/palette.py`).
- Every layer gets a Roblox technique (ParticleEmitter sprite/flipbook,
  MeshPart + SurfaceAppearance, Beam, Trail, PointLight, Highlight,
  ColorCorrection/Bloom, camera, ground decal) and a confidence.
- Mark what was measured vs inferred in `notes`.
