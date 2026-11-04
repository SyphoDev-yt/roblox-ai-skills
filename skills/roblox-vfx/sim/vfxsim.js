/* vfxsim.js - a browser simulator of Roblox's VFX instances.
 *
 * Same classes, same property names, same value types as Roblox Studio:
 * ParticleEmitter, Beam, Trail, Attachment, Part, MeshPart, PointLight,
 * SpotLight, Highlight, ColorCorrectionEffect, BloomEffect. An effect is a
 * JSON tree of those instances plus a timeline (emit / set / tween / enable /
 * shake), using the roblox-vfx recipe codec for typed values:
 *   {"NumberSequence":[[t,v,env],...]}  {"ColorSequence":[[t,[r,g,b]],...]}
 *   {"NumberRange":[a,b]}  {"Vector3":[x,y,z]}  {"Vector2":[x,y]}
 *   {"Enum":"ParticleOrientation.VelocityPerpendicular"}  {"Color3":[r,g,b]}
 *   CFrame: [x,y,z, rxDeg,ryDeg,rzDeg]  (Roblox CFrame.Angles order)
 * Colours are 0..1 floats like Color3.new.
 *
 * The simulation core (SIM.World) has no DOM or WebGL dependency, so it also
 * runs under node for numeric checks. SIM.Renderer draws a World with
 * three.js r128. Everything is deterministic: seek(t) replays from 0 at a
 * fixed 1/60 s step with a seeded RNG, so frame N always looks the same.
 *
 * Behaviour marked CALIBRATE is inferred from the docs and must be checked
 * against Studio (see calibrate/ in the skill). Everything else follows the
 * create.roblox.com API reference.
 */
(function (root) {
  "use strict";
  const SIM = {};
  const DT = 1 / 60;
  SIM.DT = DT;

  // ------------------------------------------------------------ RNG
  function rng(seed) {
    let a = seed >>> 0;
    return function () {
      a = (a + 0x6d2b79f5) >>> 0;
      let t = a;
      t = Math.imul(t ^ (t >>> 15), t | 1);
      t ^= t + Math.imul(t ^ (t >>> 7), t | 61);
      return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
    };
  }
  function hashStr(s) {
    let h = 2166136261;
    for (let i = 0; i < s.length; i++) h = Math.imul(h ^ s.charCodeAt(i), 16777619);
    return h >>> 0;
  }

  // ------------------------------------------------------------ vectors
  const V = {
    add: (a, b) => [a[0] + b[0], a[1] + b[1], a[2] + b[2]],
    sub: (a, b) => [a[0] - b[0], a[1] - b[1], a[2] - b[2]],
    mul: (a, s) => [a[0] * s, a[1] * s, a[2] * s],
    dot: (a, b) => a[0] * b[0] + a[1] * b[1] + a[2] * b[2],
    cross: (a, b) => [a[1] * b[2] - a[2] * b[1], a[2] * b[0] - a[0] * b[2], a[0] * b[1] - a[1] * b[0]],
    len: (a) => Math.hypot(a[0], a[1], a[2]),
    norm: (a) => { const l = Math.hypot(a[0], a[1], a[2]) || 1; return [a[0] / l, a[1] / l, a[2] / l]; },
    lerp: (a, b, t) => [a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t, a[2] + (b[2] - a[2]) * t],
  };
  SIM.V = V;

  // ------------------------------------------------------------ CFrame
  // R is row-major 3x3; its COLUMNS are RightVector, UpVector, -LookVector
  // (Roblox: LookVector = -Z). CFrame.Angles(x,y,z) = Rx * Ry * Rz.
  function matMul(A, B) {
    const C = new Array(9);
    for (let i = 0; i < 3; i++) for (let j = 0; j < 3; j++)
      C[i * 3 + j] = A[i * 3] * B[j] + A[i * 3 + 1] * B[3 + j] + A[i * 3 + 2] * B[6 + j];
    return C;
  }
  function rotX(a) { const c = Math.cos(a), s = Math.sin(a); return [1, 0, 0, 0, c, -s, 0, s, c]; }
  function rotY(a) { const c = Math.cos(a), s = Math.sin(a); return [c, 0, s, 0, 1, 0, -s, 0, c]; }
  function rotZ(a) { const c = Math.cos(a), s = Math.sin(a); return [c, -s, 0, s, c, 0, 0, 0, 1]; }
  const D2R = Math.PI / 180;
  const CF = {
    identity: () => ({ p: [0, 0, 0], R: [1, 0, 0, 0, 1, 0, 0, 0, 1] }),
    fromSpec(s) {
      if (!s) return CF.identity();
      if (s.p && s.R) return { p: s.p.slice(), R: s.R.slice() };
      if (s.CFrame) s = s.CFrame;
      if (s.lookAt) return CF.lookAt(s.pos, s.lookAt);
      const p = [s[0] || 0, s[1] || 0, s[2] || 0];
      const R = matMul(matMul(rotX((s[3] || 0) * D2R), rotY((s[4] || 0) * D2R)), rotZ((s[5] || 0) * D2R));
      return { p, R };
    },
    lookAt(pos, at) {
      const f = V.norm(V.sub(at, pos));
      let up = [0, 1, 0];
      if (Math.abs(V.dot(f, up)) > 0.999) up = [0, 0, 1];
      const r = V.norm(V.cross(f, up));
      const u = V.cross(r, f);
      const b = V.mul(f, -1);
      return { p: pos.slice(), R: [r[0], u[0], b[0], r[1], u[1], b[1], r[2], u[2], b[2]] };
    },
    mul(a, b) {
      const R = matMul(a.R, b.R);
      const p = V.add(a.p, CF.vec(a, b.p));
      return { p, R };
    },
    vec: (c, v) => [c.R[0] * v[0] + c.R[1] * v[1] + c.R[2] * v[2], c.R[3] * v[0] + c.R[4] * v[1] + c.R[5] * v[2], c.R[6] * v[0] + c.R[7] * v[1] + c.R[8] * v[2]],
    point: (c, v) => V.add(c.p, CF.vec(c, v)),
    right: (c) => [c.R[0], c.R[3], c.R[6]],
    up: (c) => [c.R[1], c.R[4], c.R[7]],
    back: (c) => [c.R[2], c.R[5], c.R[8]],
    toQuat(c) {
      const m = c.R; const tr = m[0] + m[4] + m[8];
      let w, x, y, z;
      if (tr > 0) { const s = Math.sqrt(tr + 1) * 2; w = s / 4; x = (m[7] - m[5]) / s; y = (m[2] - m[6]) / s; z = (m[3] - m[1]) / s; }
      else if (m[0] > m[4] && m[0] > m[8]) { const s = Math.sqrt(1 + m[0] - m[4] - m[8]) * 2; w = (m[7] - m[5]) / s; x = s / 4; y = (m[1] + m[3]) / s; z = (m[2] + m[6]) / s; }
      else if (m[4] > m[8]) { const s = Math.sqrt(1 + m[4] - m[0] - m[8]) * 2; w = (m[2] - m[6]) / s; x = (m[1] + m[3]) / s; y = s / 4; z = (m[5] + m[7]) / s; }
      else { const s = Math.sqrt(1 + m[8] - m[0] - m[4]) * 2; w = (m[3] - m[1]) / s; x = (m[2] + m[6]) / s; y = (m[5] + m[7]) / s; z = s / 4; }
      return [x, y, z, w];
    },
    fromQuat(q, p) {
      const [x, y, z, w] = q;
      return { p: p.slice(), R: [1 - 2 * (y * y + z * z), 2 * (x * y - z * w), 2 * (x * z + y * w),
        2 * (x * y + z * w), 1 - 2 * (x * x + z * z), 2 * (y * z - x * w),
        2 * (x * z - y * w), 2 * (y * z + x * w), 1 - 2 * (x * x + y * y)] };
    },
    lerp(a, b, t) {
      let qa = CF.toQuat(a), qb = CF.toQuat(b);
      let d = qa[0] * qb[0] + qa[1] * qb[1] + qa[2] * qb[2] + qa[3] * qb[3];
      if (d < 0) { qb = qb.map((v) => -v); d = -d; }
      let q;
      if (d > 0.9995) q = qa.map((v, i) => v + (qb[i] - v) * t);
      else {
        const th = Math.acos(d), s = Math.sin(th);
        const wa = Math.sin((1 - t) * th) / s, wb = Math.sin(t * th) / s;
        q = qa.map((v, i) => v * wa + qb[i] * wb);
      }
      const l = Math.hypot(...q); q = q.map((v) => v / l);
      return CF.fromQuat(q, V.lerp(a.p, b.p, t));
    },
  };
  SIM.CF = CF;

  // ------------------------------------------------------------ value codec
  function decode(v) {
    if (v === null || typeof v !== "object" || Array.isArray(v)) return v;
    if ("NumberSequence" in v) {
      const k = v.NumberSequence;
      return { ns: typeof k === "number" ? [[0, k, 0], [1, k, 0]] : k.map((p) => [p[0], p[1], p[2] || 0]) };
    }
    if ("ColorSequence" in v) {
      const k = v.ColorSequence;
      return { cs: Array.isArray(k[0]) && Array.isArray(k[0][1]) ? k : [[0, k], [1, k]] };
    }
    if ("NumberRange" in v) { const r = v.NumberRange; return typeof r === "number" ? [r, r] : [r[0], r.length > 1 ? r[1] : r[0]]; }
    if ("Vector3" in v) return v.Vector3.slice();
    if ("Vector2" in v) return v.Vector2.slice();
    if ("Color3" in v) return v.Color3.slice();
    if ("Enum" in v) { const s = String(v.Enum); return s.slice(s.lastIndexOf(".") + 1); }
    if ("Ref" in v) return { ref: v.Ref };
    if ("CFrame" in v) return CF.fromSpec(v.CFrame);
    return v;
  }
  SIM.decode = decode;

  function nsAt(ns, t, envs) {
    const k = ns.ns || ns;
    if (typeof k === "number") return k;
    if (t <= k[0][0]) return k[0][1] + (envs ? envs[0] * k[0][2] : 0);
    for (let i = 1; i < k.length; i++) {
      if (t <= k[i][0]) {
        const a = k[i - 1], b = k[i];
        const f = (t - a[0]) / ((b[0] - a[0]) || 1);
        const va = a[1] + (envs ? envs[i - 1] * a[2] : 0);
        const vb = b[1] + (envs ? envs[i] * b[2] : 0);
        return va + (vb - va) * f;
      }
    }
    const L = k[k.length - 1];
    return L[1] + (envs ? envs[k.length - 1] * L[2] : 0);
  }
  function csAt(cs, t) {
    const k = cs.cs || cs;
    if (!Array.isArray(k[0])) return k;
    if (t <= k[0][0]) return k[0][1];
    for (let i = 1; i < k.length; i++) {
      if (t <= k[i][0]) {
        const a = k[i - 1], b = k[i];
        const f = (t - a[0]) / ((b[0] - a[0]) || 1);
        return V.lerp(a[1], b[1], f);
      }
    }
    return k[k.length - 1][1];
  }
  SIM.nsAt = nsAt;
  SIM.csAt = csAt;

  // ------------------------------------------------------------ easing
  // Roblox EasingStyle / EasingDirection, as TweenService defines them.
  const EASE_IN = {
    Linear: (t) => t,
    Sine: (t) => 1 - Math.cos((t * Math.PI) / 2),
    Quad: (t) => t * t,
    Cubic: (t) => t * t * t,
    Quart: (t) => t ** 4,
    Quint: (t) => t ** 5,
    Exponential: (t) => (t === 0 ? 0 : 2 ** (10 * t - 10)),
    Circular: (t) => 1 - Math.sqrt(1 - t * t),
    Back: (t) => 2.70158 * t * t * t - 1.70158 * t * t,
    Elastic: (t) => (t === 0 || t === 1 ? t : -(2 ** (10 * t - 10)) * Math.sin((t * 10 - 10.75) * ((2 * Math.PI) / 3))),
    Bounce: (t) => 1 - bounceOut(1 - t),
  };
  function bounceOut(t) {
    const n = 7.5625, d = 2.75;
    if (t < 1 / d) return n * t * t;
    if (t < 2 / d) return n * (t -= 1.5 / d) * t + 0.75;
    if (t < 2.5 / d) return n * (t -= 2.25 / d) * t + 0.9375;
    return n * (t -= 2.625 / d) * t + 0.984375;
  }
  function ease(style, dir, t) {
    const f = EASE_IN[style || "Quad"] || EASE_IN.Quad;
    t = Math.min(1, Math.max(0, t));
    dir = dir || "Out";
    if (dir === "In") return f(t);
    if (dir === "Out") return 1 - f(1 - t);
    return t < 0.5 ? f(t * 2) / 2 : 1 - f((1 - t) * 2) / 2;
  }
  SIM.ease = ease;

  // ------------------------------------------------------------ defaults
  // Values a script-made Instance.new() gets (LightInfluence is 0 from a
  // script, 1 when inserted through Studio's UI - the docs call this out).
  const DEFAULTS = {
    Part: { CFrame: CF.identity(), Size: [4, 1, 2], Color: [0.64, 0.635, 0.647], Material: "Plastic", Transparency: 0, Shape: "Block", Anchored: true, CastShadow: true },
    MeshPart: { CFrame: CF.identity(), Size: [1, 1, 1], Color: [0.64, 0.635, 0.647], Material: "Plastic", Transparency: 0, MeshId: "", TextureID: "", DoubleSided: false, CastShadow: true },
    Attachment: { CFrame: CF.identity() },
    ParticleEmitter: {
      Acceleration: [0, 0, 0], Brightness: 1, Color: { cs: [[0, [1, 1, 1]], [1, [1, 1, 1]]] }, Drag: 0,
      EmissionDirection: "Top", Enabled: true, FlipbookFramerate: [1, 1], FlipbookLayout: "None", FlipbookMode: "Loop",
      FlipbookStartRandom: false, FlipbookBlendFrames: true, FlipbookSizeX: 1, FlipbookSizeY: 1,
      Lifetime: [5, 10], LightEmission: 0, LightInfluence: 0, LockedToPart: false, Orientation: "FacingCamera",
      Rate: 20, RotSpeed: [0, 0], Rotation: [0, 0], Shape: "Box", ShapeInOut: "Outward", ShapePartial: 1, ShapeStyle: "Volume",
      Size: { ns: [[0, 1, 0], [1, 1, 0]] }, Speed: [5, 5], SpreadAngle: [0, 0], Squash: { ns: [[0, 0, 0], [1, 0, 0]] },
      Texture: "rbxasset://textures/particles/sparkles_main.dds", TimeScale: 1, Transparency: { ns: [[0, 0, 0], [1, 0, 0]] },
      VelocityInheritance: 0, ZOffset: 0, WindAffectsDrag: false,
    },
    Beam: {
      Attachment0: null, Attachment1: null, Brightness: 1, Color: { cs: [[0, [1, 1, 1]], [1, [1, 1, 1]]] }, CurveSize0: 0, CurveSize1: 0,
      Enabled: true, FaceCamera: false, LightEmission: 0, LightInfluence: 0, Segments: 10, Texture: "", TextureLength: 1,
      TextureMode: "Stretch", TextureSpeed: 1, Transparency: { ns: [[0, 0.5, 0], [1, 0.5, 0]] }, Width0: 1, Width1: 1, ZOffset: 0,
    },
    Trail: {
      Attachment0: null, Attachment1: null, Brightness: 1, Color: { cs: [[0, [1, 1, 1]], [1, [1, 1, 1]]] }, Enabled: true, FaceCamera: false,
      Lifetime: 2, LightEmission: 0, LightInfluence: 0, MaxLength: 0, MinLength: 0.1, Texture: "", TextureLength: 1, TextureMode: "Stretch",
      Transparency: { ns: [[0, 0.5, 0], [1, 0.5, 0]] }, WidthScale: { ns: [[0, 1, 0], [1, 1, 0]] },
    },
    PointLight: { Brightness: 1, Color: [1, 1, 1], Enabled: true, Range: 8, Shadows: false },
    SpotLight: { Brightness: 1, Color: [1, 1, 1], Enabled: true, Range: 16, Angle: 90, Face: "Front", Shadows: false },
    Highlight: { Adornee: null, DepthMode: "AlwaysOnTop", Enabled: true, FillColor: [1, 0, 0], FillTransparency: 0.5, OutlineColor: [1, 1, 1], OutlineTransparency: 0 },
    // The mesh-VFX route: a MeshPart with a SurfaceAppearance whose ColorMap
    // carries alpha (AlphaMode Transparency) and an EmissiveMask for glow.
    // Only Color, AlphaMode, EmissiveStrength and EmissiveTint can change at
    // runtime in Roblox, and the Content properties need plugin capability,
    // so these are authored in Studio edit mode and cloned in game.
    SurfaceAppearance: { AlphaMode: "Overlay", Color: [1, 1, 1], ColorMap: "", EmissiveMask: "", EmissiveStrength: 1, EmissiveTint: [1, 1, 1] },
    ColorCorrectionEffect: { Brightness: 0, Contrast: 0, Enabled: true, Saturation: 0, TintColor: [1, 1, 1] },
    BloomEffect: { Enabled: true, Intensity: 1, Size: 24, Threshold: 2 },
    Folder: {}, Model: {},
  };
  SIM.DEFAULTS = DEFAULTS;
  const BASEPART = { Part: 1, MeshPart: 1 };

  const FACE = { Top: [0, 1, 0], Bottom: [0, -1, 0], Right: [1, 0, 0], Left: [-1, 0, 0], Front: [0, 0, -1], Back: [0, 0, 1] };

  // ------------------------------------------------------------ instances
  class Inst {
    constructor(spec, parent) {
      this.ClassName = spec.class || spec.ClassName || "Folder";
      this.Name = spec.name || spec.Name || this.ClassName;
      this.parent = parent;
      this.children = [];
      const d = DEFAULTS[this.ClassName] || {};
      this.p = {};
      for (const k in d) this.p[k] = clone(d[k]);
      const props = spec.props || {};
      for (const k in props) this.p[k] = decode(props[k]);
      for (const k of ["CFrame", "Size", "Color", "Transparency", "Material", "MeshId", "TextureID", "Shape"]) if (k in spec) this.p[k] = decode(spec[k]);
      if (this.p.CFrame && !this.p.CFrame.R) this.p.CFrame = CF.fromSpec(this.p.CFrame);
      this.spec = spec;
    }
    path() { return this.parent && this.parent.parent ? this.parent.path() + "." + this.Name : this.Name; }
    isA(c) { return this.ClassName === c || (c === "BasePart" && BASEPART[this.ClassName]); }
  }
  function clone(v) { return v === null || typeof v !== "object" ? v : JSON.parse(JSON.stringify(v)); }

  // ------------------------------------------------------------ world
  class World {
    constructor(def, opts) {
      this.def = def;
      this.opts = opts || {};
      this.reset();
    }
    reset() {
      const def = this.def;
      this.time = 0;
      this.seed = def.seed || 1;
      this.root = new Inst({ class: "Model", name: "Workspace" }, null);
      this.byPath = {};
      this.all = [];
      const build = (spec, parent) => {
        const it = new Inst(spec, parent);
        parent.children.push(it);
        this.all.push(it);
        this.byPath[it.path()] = it;
        for (const c of spec.children || []) build(c, it);
        return it;
      };
      for (const s of def.instances || []) build(s, this.root);
      for (const it of this.all) {
        for (const k of ["Attachment0", "Attachment1", "Adornee"]) {
          const v = it.p[k];
          if (v && v.ref) it.p[k] = this.find(v.ref);
          else if (typeof v === "string") it.p[k] = this.find(v);
        }
        if (it.ClassName === "ParticleEmitter") {
          it.parts = [];
          it.acc = 0;
          it.rng = rng(hashStr(it.path()) ^ this.seed);
          it.lastPos = null;
        }
        if (it.ClassName === "Trail") { it.pts = []; it.odo = 0; it.lastMid = null; }
        it.hidden = false;
      }
      this.events = (def.timeline || []).map((e, i) => Object.assign({ _i: i }, e)).sort((a, b) => (a.t || 0) - (b.t || 0) || a._i - b._i);
      this.nextEvent = 0;
      this.tweens = [];
      this.timers = [];
      this.shakes = [];
      this.fovs = [];
      this.overlays = [];
      this.bloomOff = [];
      this.paths = [];
      this.spins = [];
      this.tossed = [];
      this.swings = [];
      this.warnings = [];
      this.cam = def.camera && def.camera.pos ? { pos: def.camera.pos.slice(), at: def.camera.at.slice(), fov: def.camera.fov || 70 } : null;
      this.camTween = null;
      this.rig = def.rig ? prepRig(def.rig) : null;
      // extra rigs: copies of the caster (Naruto's clones) with their own keys, visible in show=[t0, t1]
      this.actors = (def.actors || []).map((a) => Object.assign(prepRig(a), { name: a.name, show: a.show || [0, 1e9] }));
      this.actorCF = {};
      this.foe = {};
      this.ghosts = [];
      this.followers = this.all.filter((it) => it.spec.Follow);
      this.updateRig(0);
      this.fireDue();
    }
    // ---------------------------------------------------- animated R6 rig
    // def.rig = {at:[x,y,z], facing:deg, keys:[{t, root:[x,y,z,yawDeg,pitchDeg],
    //   pose:{Torso,Head,RightArm,LeftArm,RightLeg,LeftLeg: [rxDeg,ryDeg,rzDeg]},
    //   style, dir}]}. Joints pivot where Roblox's R6 Motor6Ds do (shoulders
    // at (+-1, 0.5, 0) on the torso, hips at (+-1, -1, 0), neck at (0, 1, 0)).
    // rx +90 on an arm raises it forward (-Z, the rig's LookVector).
    // Parts with "Follow": "RightHand" (+ "FollowOffset") ride the rig.
    updateRig(t) {
      this.rigCF = this.rig ? rigCFs(this.rig, poseAt(this.rig, t)) : null;
      this.actorCF = {};
      for (const a of this.actors) if (t >= a.show[0] && t < a.show[1]) this.actorCF[a.name] = rigCFs(a, poseAt(a, t));
      for (const it of this.followers) {
        const fw = it.spec.Follow;
        const dot = fw.indexOf(".");
        const set = dot < 0 ? this.rigCF : this.actorCF[fw.slice(0, dot)];
        const base = set && set[dot < 0 ? fw : fw.slice(dot + 1)];
        if (base) it.p.CFrame = CF.mul(base, CF.fromSpec(it.spec.FollowOffset || [0, 0, 0, 0, 0, 0]));
      }
    }
    find(path) {
      if (!path) return null;
      if (this.byPath[path]) return this.byPath[path];
      const tail = path.split(".").slice(-2).join(".");
      for (const k in this.byPath) if (k.endsWith(tail)) return this.byPath[k];
      return null;
    }
    // World CFrame of an instance: BasePart CFrames are world-space, an
    // Attachment's CFrame is relative to its parent part. An Attachment under
    // a Model/Folder has NO world position (skill trap 3): it sits at origin.
    worldCF(it) {
      if (!it) return CF.identity();
      if (it.isA("BasePart")) return it.p.CFrame;
      if (it.ClassName === "Attachment") {
        const par = it.parent;
        if (par && par.isA("BasePart")) return CF.mul(par.p.CFrame, it.p.CFrame);
        return it.p.CFrame;
      }
      return CF.identity();
    }
    seek(t) {
      if (t < this.time - 1e-9) this.reset();
      while (this.time + DT / 2 < t) this.step();
    }
    // One 1/60 s frame: advance the simulation, then fire the timeline events
    // due on this frame. An event at time te lands on frame round(te*60), and
    // a particle emitted there is drawn that frame at age 0, as an Emit()
    // call inside a Roblox frame is.
    step() {
      const t1 = this.time + DT;
      for (const tm of this.timers) if (!tm.done && tm.at <= t1 + DT / 2) { tm.done = true; tm.fn(); }
      for (const tw of this.tweens) this.applyTween(tw, t1);
      this.tweens = this.tweens.filter((tw) => !tw.done);
      for (const pf of this.paths) this.applyPath(pf, t1);
      for (const tz of this.tossed) this.applyToss(tz, DT);
      for (const sw of this.swings) this.applySwing(sw, t1);
      for (const sp of this.spins) this.applySpin(sp, t1);
      this.spins = this.spins.filter((sp) => !sp.done);
      if (this.camTween) {
        const c = this.camTween, k = ease(c.style, c.dir, (t1 - c.t0) / c.time);
        this.cam = { pos: V.lerp(c.from.pos, c.to.pos, k), at: V.lerp(c.from.at, c.to.at, k), fov: c.from.fov + (c.to.fov - c.from.fov) * k, roll: (c.from.roll || 0) + ((c.to.roll || 0) - (c.from.roll || 0)) * k };
        if (k >= 1) this.camTween = null;
      }
      this.updateRig(t1);
      this.stepFoe(t1, DT);
      this.ghosts = this.ghosts.filter((g) => t1 - g.t0 < g.life);
      for (const it of this.all) {
        if (it.ClassName === "ParticleEmitter") this.updateEmitter(it, DT);
        else if (it.ClassName === "Trail") this.updateTrail(it, DT);
      }
      this.time = t1;
      this.fireDue();
    }
    fireDue() {
      const now = this.time;
      while (this.nextEvent < this.events.length && (this.events[this.nextEvent].t || 0) <= now + DT / 2) {
        const e = this.events[this.nextEvent++];
        this.fire(e, now);
        const tw = this.tweens[this.tweens.length - 1];
        if (tw && tw.t0 === (e.t || 0) && (e.do || e.action) === "tween") { tw.t0 = now; this.applyTween(tw, now); }
      }
    }
    target(e) {
      const it = this.find(e.target);
      if (!it) this.warnings.push(`timeline: no instance "${e.target}"`);
      return it;
    }
    fire(e, now) {
      const act = e.do || e.action;
      if (act === "hit") { this.hits = this.hits || []; this.hits.push(Object.assign({ at: now }, e)); this.hitFoe(e, now); return; }
      if (act === "face") { this.faces = this.faces || []; this.faces.push({ at: now, face: e.face, actor: e.actor || null }); return; }   // Studio: h.setFace swaps the head decal
      if (act === "shake") { this.shakes.push({ t0: e.t || 0, amp: e.amp || 0.5, freq: e.freq || 30, time: e.time || 0.3 }); return; }
      if (act === "fov") {
        // FOV punch, layered on whatever fov the camera has (the Luau camera driver re-bases each frame, so a camera fov tween is fine)
        this.fovs.push({ t0: e.t || 0, by: e.by || -8, i: e.i || 0.05, o: e.o || 0.35 }); return;
      }
      if (act === "bloom") { this.bloomOff.push({ t0: e.t || 0, time: e.time || 0.1 }); return; }   // Studio: the place's own BloomEffects off for a moment
      if (act === "overlay") { this.overlays.push(Object.assign({ t0: e.t || 0, kind: e.kind || "lines", time: e.time || 1, color: e.color || [1, 1, 1], transparency: e.transparency == null ? 0.2 : e.transparency, fin: e.fin == null ? 0.08 : e.fin, fout: e.fout == null ? 0.2 : e.fout, size: e.size || 0.11 }, e.kind === "lines" ? { image: e.image || "sim:focus_lines", spin: e.spin !== false, rot: e.rot || 0, scale: e.scale || 1.08, seed: e.seed || 1 } : {})); return; }
      if (act === "ghost") {
        // an afterimage of the rig's current pose that fades out (dash/teleport)
        const src = e.actor ? this.actorCF[e.actor] : this.rigCF;
        if (src) this.ghosts.push({ parts: e.parts || null, keep: !!e.keep, cfs: JSON.parse(JSON.stringify(src)), t0: now, life: e.time || 0.3, color: e.color || [0.8, 0.9, 1], tr0: e.transparency == null ? 0.35 : e.transparency });
        return;
      }
      if (act === "camera") {
        // cinematic camera: cut (time 0) or tween to {pos, at, fov}
        const to = { pos: e.pos, at: e.at, fov: e.fov || (this.cam && this.cam.fov) || 70, roll: e.roll || 0 };   // roll: degrees about the view axis (a tilting horizon)
        const from = this.cam ? JSON.parse(JSON.stringify(this.cam)) : to;
        if (!e.time) { this.cam = to; this.camTween = null; }
        else this.camTween = { from, to, t0: now, time: e.time, style: e.style || "Quad", dir: e.dir || "Out" };
        return;
      }
      if (act === "timescale") {
        // time stop: every ParticleEmitter in the effect (or under e.target) eases its TimeScale to e.value;
        // live particles hang where they are, new ones are born frozen (Roblox ParticleEmitter.TimeScale)
        const root = e.target ? this.target(e) : null;
        const ems = (root ? [root, ...descendants(root)] : this.all).filter((d) => d.ClassName === "ParticleEmitter");
        for (const d of ems) this.tweens.push({ it: d, prop: "TimeScale", from: d.p.TimeScale, to: e.value == null ? 0 : e.value, t0: now, time: Math.max(1e-6, e.time || 1e-6), style: e.style || "Quad", dir: e.dir || "Out" });
        return;
      }
      if (act === "target") {
        // the real target character hidden/shown (a copy of it acts as an actor "@target" meanwhile)
        const pre = e.foe || "Foe";
        for (const d of this.all) if (d.spec && d.spec.simOnly && d.Name.startsWith(pre)) d.hidden = !!e.hide;
        return;
      }
      const it = this.target(e);
      if (!it) return;
      if (act === "emit") {
        if (it.ClassName === "ParticleEmitter") this.emit(it, e.count != null ? e.count : 1);
        else for (const d of descendants(it)) if (d.ClassName === "ParticleEmitter") this.emit(d, e.count != null ? e.count : (d.spec.EmitCount || 1));
      } else if (act === "set") {
        it.p[e.prop] = decodeProp(it, e.prop, e.value);
      } else if (act === "enable") {
        it.p.Enabled = true;
        if (e.duration) this.timers.push({ at: (e.t || 0) + e.duration, fn: () => { it.p.Enabled = false; } });
      } else if (act === "disable") {
        it.p.Enabled = false;
      } else if (act === "tween") {
        const from = e.from !== undefined ? decodeProp(it, e.prop, e.from) : clone(it.p[e.prop]);
        let to = decodeProp(it, e.prop, e.to);
        if (e.by !== undefined && e.prop === "CFrame") to = CF.mul(from, CF.fromSpec(e.by));
        this.tweens.push({ it, prop: e.prop, from, to, t0: e.t || 0, time: Math.max(1e-6, e.time || 0.25), style: e.style, dir: e.dir, reverses: !!e.reverses });
      } else if (act === "spin") {
        this.spins.push({ it, axis: e.axis || "Y", rate: e.rate == null ? 360 : e.rate, t0: now, time: Math.max(1e-6, e.time || 1), angle: 0, last: null });
      } else if (act === "path") {
        this.startPath(it, e, now);
      } else if (act === "toss") {
        // unanchor and throw: Roblox gravity, bounce on the ground plane, settle
        this.tossed = this.tossed.filter((q) => q.it !== it);
        this.tossed.push({ it, v: (e.vel || [0, 30, 0]).slice(), w: (e.spin || [0, 0, 0]).map((d) => d * Math.PI / 180), g: e.grav == null ? 196.2 : e.grav,
          bounce: e.bounce == null ? 0.3 : e.bounce, floor: e.floor == null ? 0 : e.floor, live: true });
      } else if (act === "swing") {
        // rotate about a local pivot from the CFrame the part had when it first swung (a book cover, a door, a wing)
        let sw = this.swings.find((q) => q.it === it);
        if (!sw) { sw = { it, base: clone(it.p.CFrame), angle: 0 }; this.swings.push(sw); }
        sw.pivot = e.pivot || [0, 0, 0]; sw.axis = e.axis || "X";
        sw.tw = { from: e.from != null ? e.from : sw.angle, to: e.to || 0, t0: now, time: Math.max(1e-6, e.time || 0.3), style: e.style, dir: e.dir };
      } else if (act === "hinge") {
        const pf = this.paths.find((q) => q.it === it);
        if (pf) { pf.hingeAxis = e.axis || pf.hingeAxis || "X"; pf.hingeTw = { from: pf.hinge, to: e.to || 0, t0: now, time: Math.max(1e-6, e.time || 0.2), style: e.style, dir: e.dir }; }
      } else if (act === "clear") {
        if (it.parts) it.parts.length = 0;
        if (it.pts) it.pts.length = 0;
      } else if (act === "destroy" || act === "hide") {
        for (const d of [it, ...descendants(it)]) { d.hidden = true; if (d.parts) d.parts.length = 0; if ("Enabled" in d.p) d.p.Enabled = false; }
      } else if (act === "show") {
        for (const d of [it, ...descendants(it)]) d.hidden = false;
      } else {
        this.warnings.push(`timeline: unknown action "${act}"`);
      }
    }
    // ---------------------------------------------------- the target's body (v5: real physics)
    // The SAME model as Studio's HitSystem.luau (keep FOE_PHYS in step with it). v5 fix: the target kept
    // getting pushed, then standing upright in the air. Now a hit either staggers a STANDING target (a small
    // knock, anchored slide) or throws it as a rigid body: v0 = knock / T + (0, G T / 2, 0), so it is exactly at
    // start + knock after T (effects authored there still meet it), then it keeps flying under gravity G
    // (2/3 of Roblox's, a weighty anime hang), tumbles (it falls AWAY from the hit), bounces, slides to a stop
    // on its back, and gets up after its stun; reaction "ragdoll" stays down. A hit on an airborne or downed
    // body re-throws it from where it really is (a juggle); a tiny hit nudges it and keeps it aloft a little.
    foeBody(prefix) {
      prefix = prefix || "Foe";
      if (this.foe[prefix]) return this.foe[prefix];
      const parts = this.all.filter((it) => it.spec && it.spec.simOnly && it.Name.startsWith(prefix) && it.isA("BasePart"));
      const torso = parts.find((it) => it.Name === prefix + "Torso");
      if (!torso) return null;
      const c0 = torso.p.CFrame;
      const inv = { p: [0, 0, 0], R: [c0.R[0], c0.R[3], c0.R[6], c0.R[1], c0.R[4], c0.R[7], c0.R[2], c0.R[5], c0.R[8]] };
      const local = (cf) => ({ p: CF.vec(inv, V.sub(cf.p, c0.p)), R: matMul(inv.R, cf.R) });
      const b = { prefix, parts: parts.map((it) => ({ it, loc: local(it.p.CFrame), half: it.p.Size.map((v) => v / 2) })), pos: c0.p.slice(), R: c0.R.slice(),
        upR: c0.R.slice(), vel: [0, 0, 0], w: [0, 0, 0], mode: "stand", slide: null, stayDown: false, ready: 0 };
      this.foe[prefix] = b;
      return b;
    }
    hitFoe(e, now) {
      const b = this.foeBody(e.target);
      if (!b) return;
      const P = FOE_PHYS;
      const d = (e.knock || [0, 0, 0]).slice();
      const T = Math.max(0.02, Math.min(2, e.time == null ? 0.22 : e.time));
      const reaction = e.reaction || "flinch";
      const mag = V.len(d);
      const stun = e.stun == null ? ({ flinch: 0.3, knockback: 0.5, launch: 0.8, ragdoll: 1.5 })[reaction] || 0.4 : e.stun;
      b.ready = Math.max(b.ready, now + T + stun);
      if (reaction === "ragdoll") b.stayDown = true;
      if (reaction === "warp") {                                            // Shambles: simply THERE, standing
        b.pos = V.add(b.mode === "stand" ? b.pos : [b.pos[0], 3, b.pos[2]], d); b.R = b.upR.slice(); b.vel = [0, 0, 0]; b.w = [0, 0, 0];
        b.mode = "stand"; b.slide = null; return;
      }
      if (b.mode === "stand" && (reaction === "flinch" || (reaction === "knockback" && mag <= P.SMALL)) && mag <= P.SMALL) {
        // never down through the floor (HitSystem v5 take: Bajrang Gun's presses buried the target)
        const dd = [d[0], Math.max(d[1], Math.min(0, 3 - b.pos[1])), d[2]];
        b.slide = { from: b.pos.slice(), d: dd, t0: now, T };          // a stagger on its feet
        return;
      }
      const airborne = b.mode !== "stand";
      let v;
      if (airborne && mag <= P.NUDGE) v = V.add(V.add(b.vel, V.mul(d, 0.6 / T)), [0, P.NUDGE_UP, 0]);
      else {
        const Tt = reaction === "knockback" ? Math.max(T, P.SHOVE_T) : T;
        v = V.add(V.mul(d, 1 / Tt), [0, 0.5 * P.G * Tt, 0]);
      }
      const flat = [v[0], 0, v[2]];
      const fl = V.len(flat);
      const dir = fl > 1e-3 ? V.mul(flat, 1 / fl) : [0, 0, -1];
      const axis = V.cross([0, 1, 0], dir);                                  // the top goes WITH the hit: it falls away
      const spin = Math.max(P.SPIN_MIN, Math.min(P.SPIN_MAX, V.len(v) * P.SPIN_K)) * (reaction === "ragdoll" ? 1.3 : 1);
      b.w = airborne && mag <= P.NUDGE ? V.add(b.w, V.mul(axis, 1.5)) : V.mul(axis, spin);
      b.vel = v;
      b.slide = null;
      b.mode = "air";
    }
    stepFoe(now, dt) {
      const P = FOE_PHYS;
      for (const k in this.foe) {
        const b = this.foe[k];
        if (b.mode === "stand") {
          if (b.slide) {
            const a = Math.min(1, (now - b.slide.t0) / b.slide.T), q = 1 - (1 - a) * (1 - a);
            b.pos = V.add(b.slide.from, V.mul(b.slide.d, q));
            if (a >= 1) b.slide = null;
          }
        } else if (b.mode === "air") {
          b.vel[1] -= P.G * dt;
          b.pos = V.add(b.pos, V.mul(b.vel, dt));
          const wl = V.len(b.w);
          if (wl > 1e-6) b.R = matMul(axisAngle(V.mul(b.w, 1 / wl), wl * dt), b.R);
          const low = this.foeLowest(b);
          if (low < 0) {
            b.pos[1] -= low;
            if (b.vel[1] < -P.BOUNCE_V) { b.vel = [b.vel[0] * 0.7, -b.vel[1] * P.BOUNCE, b.vel[2] * 0.7]; b.w = V.mul(b.w, 0.5); }
            else { b.vel[1] = 0; b.mode = "slide"; b.lie = lyingR(b.R, b.vel); }
          }
        } else if (b.mode === "slide") {
          const sp = Math.hypot(b.vel[0], b.vel[2]), dec = P.FRICTION * dt;
          if (sp <= dec) { b.vel = [0, 0, 0]; b.mode = "down"; }
          else { b.vel = [b.vel[0] * (sp - dec) / sp, 0, b.vel[2] * (sp - dec) / sp]; b.pos = V.add(b.pos, V.mul(b.vel, dt)); }
          b.R = CF.lerp({ p: [0, 0, 0], R: b.R }, { p: [0, 0, 0], R: b.lie }, Math.min(1, dt * 12)).R;
          b.pos[1] += (P.LIE_Y - b.pos[1]) * Math.min(1, dt * 12);
        } else if (b.mode === "down") {
          b.R = CF.lerp({ p: [0, 0, 0], R: b.R }, { p: [0, 0, 0], R: b.lie }, Math.min(1, dt * 12)).R;
          b.pos[1] += (P.LIE_Y - b.pos[1]) * Math.min(1, dt * 12);
          if (!b.stayDown && now >= b.ready) { b.mode = "getup"; b.up = getUpPlan(b, now); }
        } else if (b.mode === "getup") {
          // v5 probe: lerping the root CFrame swung the legs ~0.9 studs through the floor. The body now TIPS UP
          // OVER ITS FEET (a tilt in the vertical plane, so nothing dips under the floor), then turns to its facing.
          const a = Math.min(1, (now - b.up.t0) / P.GETUP), q = 1 - (1 - a) * (1 - a), u = b.up;
          b.R = matMul(axisAngle([0, 1, 0], u.yaw * q), matMul(axisAngle(u.axis, u.ang * q), u.R0));
          const up = [b.R[1], b.R[4], b.R[7]];
          // the root sits so the straight body's LOWEST CORNER is on the floor every frame (HitSystem v5g clearance())
          b.pos = [u.base[0] + up[0] * 3, getUpClearance(b, b.R), u.base[2] + up[2] * 3];
          if (a >= 1) b.mode = "stand";
        }
        const body = { p: b.pos, R: b.R };
        for (const pt of b.parts) pt.it.p.CFrame = CF.mul(body, pt.loc);
      }
    }
    foeLowest(b) {
      let low = Infinity;
      const body = { p: b.pos, R: b.R };
      for (const pt of b.parts) {
        const c = CF.mul(body, pt.loc);
        for (const sx of [-1, 1]) for (const sy of [-1, 1]) for (const sz of [-1, 1]) low = Math.min(low, CF.point(c, [sx * pt.half[0], sy * pt.half[1], sz * pt.half[2]])[1]);
      }
      return low;
    }
    // ---------------------------------------------------- path following
    // {"do":"path", points:[[x,y,z],...], time, style, dir, lag, roll, offset, pivot}
    // A Catmull-Rom curve through the points; the part rides it by arc length,
    // `lag` studs behind the leader, facing along the tangent (LookVector).
    // Many parts on one curve with growing lag = a serpent body. "hinge"
    // tweens a rotation about local X at `offset` (a jaw), then `pivot`.
    startPath(it, e, now) {
      const P = e.points, pts = [];
      for (let i = 0; i < P.length - 1; i++) {
        const p0 = P[Math.max(i - 1, 0)], p1 = P[i], p2 = P[i + 1], p3 = P[Math.min(i + 2, P.length - 1)];
        for (let s = 0; s < 16; s++) {
          const u = s / 16, u2 = u * u, u3 = u2 * u;
          pts.push([0, 1, 2].map((k) => 0.5 * (2 * p1[k] + (-p0[k] + p2[k]) * u + (2 * p0[k] - 5 * p1[k] + 4 * p2[k] - p3[k]) * u2 + (-p0[k] + 3 * p1[k] - 3 * p2[k] + p3[k]) * u3)));
        }
      }
      pts.push(P[P.length - 1].slice());
      const cum = [0];
      for (let i = 1; i < pts.length; i++) cum.push(cum[i - 1] + V.len(V.sub(pts[i], pts[i - 1])));
      const old = this.paths.find((q) => q.it === it);
      this.paths = this.paths.filter((q) => q.it !== it);
      this.paths.push({ it, pts, cum, total: cum[cum.length - 1], t0: now, time: Math.max(1e-6, e.time || 1), style: e.style || "Linear", dir: e.dir || "InOut",
        lag: e.lag || 0, roll: e.roll || 0, spin: e.spin || 0, off: CF.fromSpec(e.offset || [0, 0, 0, 0, 0, 0]), pivot: CF.fromSpec(e.pivot || [0, 0, 0, 0, 0, 0]), hinge: old ? old.hinge : 0, hingeAxis: e.hingeAxis || (old && old.hingeAxis) || "X", hingeTw: null });
    }
    pathAt(pf, d) {
      d = Math.max(0, Math.min(pf.total, d));
      const c = pf.cum, n = c.length;
      let lo = 1, hi = n - 1;
      while (lo < hi) { const m = (lo + hi) >> 1; if (c[m] < d) lo = m + 1; else hi = m; }
      const f = (d - c[lo - 1]) / Math.max(c[lo] - c[lo - 1], 1e-6);
      return V.lerp(pf.pts[lo - 1], pf.pts[lo], f);
    }
    applyPath(pf, now) {
      const a = Math.max(0, Math.min(1, (now - pf.t0) / pf.time));
      const d = ease(pf.style, pf.dir, a) * pf.total - pf.lag;
      const p = this.pathAt(pf, d);
      let q = V.sub(this.pathAt(pf, d + 0.5), this.pathAt(pf, d - 0.5));
      if (V.len(q) < 1e-5) q = pf.lastQ || [0, 0, -1];
      pf.lastQ = q;
      if (pf.hingeTw) {
        const h = pf.hingeTw, k = ease(h.style, h.dir, Math.min(1, (now - h.t0) / h.time));
        pf.hinge = h.from + (h.to - h.from) * k;
        if (k >= 1) pf.hingeTw = null;
      }
      let cf = CF.mul(CF.lookAt(p, V.add(p, q)), CF.fromSpec([0, 0, 0, 0, 0, pf.roll + pf.spin * (now - pf.t0)]));
      const hx = pf.hingeAxis || "X";
      const hr = hx === "X" ? [pf.hinge, 0, 0] : hx === "Y" ? [0, pf.hinge, 0] : [0, 0, pf.hinge];
      cf = CF.mul(CF.mul(CF.mul(cf, pf.off), CF.fromSpec([0, 0, 0, ...hr])), pf.pivot);
      pf.it.p.CFrame = cf;
    }
    applyToss(tz, dt) {
      if (!tz.live) return;
      const cf = tz.it.p.CFrame;
      tz.v[1] -= tz.g * dt;
      let p = V.add(cf.p, V.mul(tz.v, dt));
      const half = Math.min(...tz.it.p.Size) * 0.5;
      let R = cf.R;
      const wl = V.len(tz.w);
      if (wl > 1e-6) {
        const k = V.mul(tz.w, 1 / wl), a = wl * dt, c = Math.cos(a), s = Math.sin(a), t = 1 - c;
        const Rw = [t * k[0] * k[0] + c, t * k[0] * k[1] - s * k[2], t * k[0] * k[2] + s * k[1],
                    t * k[0] * k[1] + s * k[2], t * k[1] * k[1] + c, t * k[1] * k[2] - s * k[0],
                    t * k[0] * k[2] - s * k[1], t * k[1] * k[2] + s * k[0], t * k[2] * k[2] + c];
        R = matMul(Rw, R);
      }
      if (p[1] < tz.floor + half) {
        p[1] = tz.floor + half;
        tz.v = [tz.v[0] * 0.55, -tz.v[1] * tz.bounce, tz.v[2] * 0.55];
        tz.w = V.mul(tz.w, 0.5);
        if (Math.abs(tz.v[1]) < 4 && V.len(tz.v) < 5) tz.live = false;
      }
      tz.it.p.CFrame = { p, R };
    }
    applySwing(sw, now) {
      if (sw.tw) {
        const h = sw.tw, k = ease(h.style, h.dir, Math.min(1, (now - h.t0) / h.time));
        sw.angle = h.from + (h.to - h.from) * k;
        if (k >= 1) sw.tw = null;
      }
      const r = sw.axis === "X" ? [sw.angle, 0, 0] : sw.axis === "Y" ? [0, sw.angle, 0] : [0, 0, sw.angle];
      const pv = sw.pivot;
      sw.it.p.CFrame = CF.mul(CF.mul(CF.mul(sw.base, CF.fromSpec(pv)), CF.fromSpec([0, 0, 0, ...r])), CF.fromSpec([-pv[0], -pv[1], -pv[2]]));
    }
    applySpin(sp, now) {
      const a = Math.max(0, Math.min(now, sp.t0 + sp.time) - sp.t0);
      const ang = sp.rate * a;
      const rot = (d) => CF.fromSpec([0, 0, 0, sp.axis === "X" ? d : 0, sp.axis === "Y" ? d : 0, sp.axis === "Z" ? d : 0]);
      const cur = sp.it.p.CFrame;
      const base = sp.last && cur === sp.last ? CF.mul(cur, rot(-sp.angle)) : cur;
      const out = CF.mul(base, rot(ang));
      sp.it.p.CFrame = out;
      sp.last = out;
      sp.angle = ang;
      if (now >= sp.t0 + sp.time) sp.done = true;
    }
    applyTween(tw, now) {
      let a = (now - tw.t0) / tw.time;
      if (tw.reverses) { if (a >= 2) { a = 2; tw.done = true; } a = a <= 1 ? a : 2 - a; }
      else if (a >= 1) { a = 1; tw.done = true; }
      const k = ease(tw.style, tw.dir, Math.max(0, a));
      const f = tw.from, t = tw.to;
      let v;
      if (tw.prop === "CFrame") v = CF.lerp(f, t, k);
      else if (typeof f === "number") v = f + (t - f) * k;
      else if (Array.isArray(f)) v = f.map((x, i) => x + (t[i] - x) * k);
      else v = k >= 1 ? t : f;
      tw.it.p[tw.prop] = v;
    }
    // ---------------------------------------------------- particles
    emitterFrame(em) {
      const par = em.parent;
      const cf = this.worldCF(par);
      const size = par && par.isA("BasePart") ? par.p.Size : null;
      return { cf, size };
    }
    emit(em, n) {
      if (em.hidden) return;
      n = Math.min(Math.floor(n), 4096);
      const life = em.p.Lifetime;
      if (Math.max(life[0], life[1]) <= 0) return;
      const fr = this.emitterFrame(em);
      for (let i = 0; i < n; i++) this.spawn(em, fr);
    }
    spawn(em, fr) {
      const p = em.p, R = em.rng;
      const r = (a, b) => a + (b - a) * R();
      const face = FACE[p.EmissionDirection] || FACE.Top;
      let local = [0, 0, 0];
      let dir = face.slice();
      const shape = p.Shape;
      const size = fr.size; // null under an Attachment: spawn at its position (docs)
      if (shape === "Box") {
        if (size) {
          if (p.ShapeStyle === "Surface") {
            local = [r(-0.5, 0.5) * size[0], r(-0.5, 0.5) * size[1], r(-0.5, 0.5) * size[2]];
            const ax = Math.floor(R() * 3); local[ax] = (R() < 0.5 ? -0.5 : 0.5) * size[ax];
          } else local = [r(-0.5, 0.5) * size[0], r(-0.5, 0.5) * size[1], r(-0.5, 0.5) * size[2]];
        }
      } else if (shape === "Sphere") {
        // ShapePartial: 1 full sphere, 0.5 hemisphere toward EmissionDirection
        let d;
        for (let k = 0; k < 20; k++) {
          d = V.norm([r(-1, 1), r(-1, 1), r(-1, 1)]);
          if ((V.dot(d, face) + 1) / 2 >= 1 - p.ShapePartial) break;
        }
        const rad = size ? Math.min(size[0], size[1], size[2]) / 2 : 0;
        const rr = p.ShapeStyle === "Surface" ? rad : rad * Math.cbrt(R());
        local = V.mul(d, rr);
        dir = d;
      } else if (shape === "Cylinder" || shape === "Disc") {
        // axis = EmissionDirection; Disc ShapePartial = inner radius proportion,
        // Cylinder ShapePartial = top radius proportion (CALIBRATE geometry)
        const ax = face;
        const t1 = Math.abs(ax[1]) > 0.9 ? [1, 0, 0] : [0, 1, 0];
        const u = V.norm(V.cross(ax, t1)), w = V.cross(ax, u);
        const a = R() * Math.PI * 2;
        const radial = V.add(V.mul(u, Math.cos(a)), V.mul(w, Math.sin(a)));
        const ext = size ? Math.min(size[0], size[2]) / 2 : 0;
        if (shape === "Disc") {
          // inner radius taken as (1 - ShapePartial) so the default 1 is a
          // full disc. The docs only say "inner radius proportion". CALIBRATE.
          const inner = 1 - Math.max(0, Math.min(1, p.ShapePartial));
          const fr01 = p.ShapeStyle === "Surface" ? 1 : Math.sqrt(r(inner * inner, 1));
          local = V.mul(radial, ext * fr01);
          dir = face.slice();
        } else {
          const h = size ? size[1] : 0;
          const y = r(-0.5, 0.5);
          const radAt = ext * (1 + (p.ShapePartial - 1) * (y + 0.5));
          local = V.add(V.mul(ax, y * h), V.mul(radial, p.ShapeStyle === "Surface" ? radAt : radAt * Math.sqrt(R())));
          dir = radial;
        }
      }
      if (p.ShapeInOut === "Inward") dir = V.mul(dir, -1);
      else if (p.ShapeInOut === "InAndOut" && R() < 0.5) dir = V.mul(dir, -1);
      // SpreadAngle: random tilt about the two axes perpendicular to the
      // emission direction (X spread about one, Y about the other).
      const sx = p.SpreadAngle[0] * D2R, sy = p.SpreadAngle[1] * D2R;
      if (sx || sy) {
        const ref = Math.abs(dir[1]) > 0.9 ? [1, 0, 0] : [0, 1, 0];
        const a1 = V.norm(V.cross(dir, ref)), a2 = V.cross(a1, dir);
        dir = rotAxis(dir, a1, r(-sx, sx));
        dir = rotAxis(dir, a2, r(-sy, sy));
      }
      const wdir = V.norm(CF.vec(fr.cf, dir));
      const wpos = CF.point(fr.cf, local);
      const speed = r(p.Speed[0], p.Speed[1]);
      let vel = V.mul(wdir, speed);
      if (p.VelocityInheritance && em.parentVel) vel = V.add(vel, V.mul(em.parentVel, p.VelocityInheritance));
      const nsLen = (s) => (s && s.ns ? s.ns.length : 2);
      const envR = (n) => Array.from({ length: n }, () => r(-1, 1));
      const nFrames = flipFrames(p);
      const fps = r(p.FlipbookFramerate[0], p.FlipbookFramerate[1]);
      const part = {
        age: 0, life: r(p.Lifetime[0], p.Lifetime[1]),
        pos: wpos, vel, dir: wdir, speed0: speed,
        rot: r(p.Rotation[0], p.Rotation[1]), rotSpeed: r(p.RotSpeed[0], p.RotSpeed[1]),
        envS: envR(nsLen(p.Size)), envT: envR(nsLen(p.Transparency)),
        frame0: p.FlipbookStartRandom ? Math.floor(R() * nFrames) : 0, fps: Math.min(30, Math.max(0, fps)),
        seed: Math.floor(R() * 1e9),
      };
      if (p.LockedToPart) { part.lpos = invPoint(fr.cf, wpos); part.lvel = invVec(fr.cf, vel); }
      em.parts.push(part);
    }
    updateEmitter(em, dt) {
      const p = em.p;
      const fr = this.emitterFrame(em);
      const pos = fr.cf.p;
      em.parentVel = em.lastPos ? V.mul(V.sub(pos, em.lastPos), 1 / dt) : [0, 0, 0];
      em.lastPos = pos.slice();
      const ts = Math.max(0, Math.min(1, p.TimeScale));
      const sdt = dt * ts;
      // continuous emission (Rate capped at 400/s as on desktop)
      if (p.Enabled && !em.hidden && p.Rate > 0 && Math.max(p.Lifetime[0], p.Lifetime[1]) > 0) {
        em.acc += Math.min(p.Rate, 400) * sdt;
        while (em.acc >= 1) { em.acc -= 1; this.spawn(em, fr); }
      }
      if (sdt <= 0) return;
      // Drag: "the rate in seconds at which particles lose half their speed
      // via exponential decay". Implemented as halvings per second, which is
      // what the docs' own explosion tutorial needs (Drag 10, life 0.2-0.6)
      // to visibly slow. CALIBRATE.
      const dragK = p.Drag ? Math.pow(0.5, p.Drag * sdt) : 1;
      const acc = p.Acceleration;
      const alive = [];
      for (const q of em.parts) {
        q.age += sdt;
        if (q.age >= q.life) continue;
        q.rot += q.rotSpeed * sdt;
        if (p.LockedToPart && q.lpos) {
          q.lvel = V.mul(V.add(q.lvel, V.mul(invVec(fr.cf, acc), sdt)), dragK);
          q.lpos = V.add(q.lpos, V.mul(q.lvel, sdt));
          q.pos = CF.point(fr.cf, q.lpos);
          q.vel = CF.vec(fr.cf, q.lvel);
        } else {
          q.vel = V.mul(V.add(q.vel, V.mul(acc, sdt)), dragK);
          q.pos = V.add(q.pos, V.mul(q.vel, sdt));
        }
        alive.push(q);
      }
      em.parts = alive;
    }
    // ---------------------------------------------------- trails
    updateTrail(tr, dt) {
      const p = tr.p;
      for (const q of tr.pts) q.age += dt;
      tr.pts = tr.pts.filter((q) => q.age < p.Lifetime);
      if (!p.Enabled || tr.hidden || !p.Attachment0 || !p.Attachment1) return;
      const a = this.worldCF(p.Attachment0).p, b = this.worldCF(p.Attachment1).p;
      const mid = V.lerp(a, b, 0.5);
      if (tr.lastMid) tr.odo += V.len(V.sub(mid, tr.lastMid));
      tr.lastMid = mid;
      const last = tr.pts[tr.pts.length - 1];
      if (!last || V.len(V.sub(mid, last.mid)) >= p.MinLength) tr.pts.push({ a, b, mid, age: 0, odo: tr.odo });
      tr.head = { a, b, mid, age: 0, odo: tr.odo };
      if (p.MaxLength > 0) {
        let L = 0;
        for (let i = tr.pts.length - 1; i > 0; i--) {
          L += V.len(V.sub(tr.pts[i].mid, tr.pts[i - 1].mid));
          if (L > p.MaxLength) { tr.pts.splice(0, i); break; }
        }
      }
    }
    // ---------------------------------------------------- queries for renderers
    shakeOffset() {
      let o = [0, 0, 0];
      for (const s of this.shakes) {
        const a = (this.time - s.t0) / s.time;
        if (a < 0 || a > 1) continue;
        const k = s.amp * (1 - a) * (1 - a);
        const ph = this.time * s.freq;
        o = V.add(o, [Math.sin(ph * 6.1) * k, Math.sin(ph * 7.3 + 1) * k, Math.sin(ph * 5.7 + 2) * k * 0.5]);
      }
      return o;
    }
    fovOffset() {
      let d = 0;
      const qo = (a) => 1 - (1 - a) * (1 - a), qio = (a) => (a < 0.5 ? 2 * a * a : 1 - Math.pow(-2 * a + 2, 2) / 2);
      for (const f of this.fovs) {
        const a = this.time - f.t0;
        if (a < 0 || a > f.i + f.o) continue;
        d += a < f.i ? f.by * qo(a / f.i) : f.by * (1 - qio((a - f.i) / f.o));
      }
      return d;
    }
    bloomSuppressed() { return this.bloomOff.some((b) => this.time >= b.t0 && this.time < b.t0 + b.time); }
    activeOverlays() {
      const out = [];
      for (const o of this.overlays) {
        const a = this.time - o.t0;
        if (a < 0 || a > o.time) continue;
        const fade = Math.max(0, Math.min(1, a / Math.max(o.fin, 1e-3), (o.time - a) / Math.max(o.fout, 1e-3)));
        out.push(Object.assign({ age: a, fade, frame: Math.floor(a * 30) }, o));
      }
      return out;
    }
    particleCount() { let n = 0; for (const it of this.all) if (it.parts) n += it.parts.length; return n; }
  }
  SIM.World = World;
  // the target's physics constants: Studio's HitSystem.luau carries the same numbers
  const FOE_PHYS = { G: 130, SMALL: 2.5, NUDGE: 1.0, NUDGE_UP: 4, SHOVE_T: 0.3, SPIN_K: 0.22, SPIN_MIN: 3, SPIN_MAX: 12,
    BOUNCE: 0.3, BOUNCE_V: 12, FRICTION: 45, LIE_Y: 0.5, GETUP: 0.5 };
  SIM.FOE_PHYS = FOE_PHYS;
  function axisAngle(k, a) {
    const c = Math.cos(a), s = Math.sin(a), t = 1 - c;
    return [t * k[0] * k[0] + c, t * k[0] * k[1] - s * k[2], t * k[0] * k[2] + s * k[1],
            t * k[0] * k[1] + s * k[2], t * k[1] * k[1] + c, t * k[1] * k[2] - s * k[0],
            t * k[0] * k[2] - s * k[1], t * k[1] * k[2] + s * k[0], t * k[2] * k[2] + c];
  }
  // how far below the root the straight body's lowest corner sits for rotation R, from the target's own parts
  // (HitSystem.luau clearance() reads the rig's joints the same way)
  function getUpClearance(b, R) {
    let low = Infinity;
    for (const pt of b.parts) {
      const c = CF.mul({ p: [0, 0, 0], R }, pt.loc), h = pt.half;
      low = Math.min(low, c.p[1] - (Math.abs(c.R[3]) * h[0] + Math.abs(c.R[4]) * h[1] + Math.abs(c.R[5]) * h[2]));
    }
    return -low;
  }
  // the get-up plan (HitSystem.luau getUp does the same): feet on the floor 3 studs down the body, a tilt that takes
  // the body's up to world up about a horizontal axis, then a yaw back to the standing facing
  function getUpPlan(b, now) {
    const R0 = b.R.slice(), u0 = [R0[1], R0[4], R0[7]];
    let axis = V.cross(u0, [0, 1, 0]);
    axis = V.len(axis) < 1e-3 ? [1, 0, 0] : V.norm(axis);
    const ang = Math.acos(Math.max(-1, Math.min(1, u0[1])));
    const base = V.sub(b.pos, V.mul(u0, 3));
    const R1 = matMul(axisAngle(axis, ang), R0);
    const l1 = [-R1[2], 0, -R1[8]], l2 = [-b.upR[2], 0, -b.upR[8]];
    const yaw = Math.atan2(l1[2] * l2[0] - l1[0] * l2[2], l1[0] * l2[0] + l1[2] * l2[2]);
    return { R0, axis, ang, base, yaw, t0: now };
  }
  // lying on its back (or front) along the slide: the torso's up axis horizontal, its back facing the floor
  function lyingR(R, vel) {
    let up = [R[1], 0, R[7]];
    if (V.len(up) < 0.2) up = [vel[0], 0, vel[2]];
    if (V.len(up) < 1e-3) up = [0, 0, -1];
    up = V.norm(up);
    const back = [0, R[5] >= 0 ? 1 : -1, 0];
    const right = V.cross(up, back);
    return [right[0], up[0], back[0], right[1], up[1], back[1], right[2], up[2], back[2]];
  }
  SIM._DEFAULTS = DEFAULTS;

  // ------------------------------------------------------------ R6 rig math
  const JOINTS = ["Torso", "Head", "RightArm", "LeftArm", "RightLeg", "LeftLeg"];
  function prepRig(r) {
    const keys = (r.keys || [{ t: 0 }]).slice().sort((a, b) => a.t - b.t);
    // scale: the model's own body scale (a giant rig such as Adult Gon is ~2); keys may add a "scale"
    // multiplier (Studio: Model:ScaleTo), a "fade" (0 shown .. 1 gone) and per-joint "move" offsets
    // ([dx, dy, dz] studs in the torso frame: limbs come apart, e.g. Law's Amputate on a target copy)
    return { at: r.at || [0, 0, 0], facing: r.facing || 0, keys, lag: r.lag || null, scale: r.scale || 1, model: r.model || null, col: r.col || null };
  }
  function poseAt(rig, t) {
    const pose = poseAtRaw(rig, t);
    // overlapping action: a lagged joint plays its own keys late
    for (const j in rig.lag || {}) if (pose[j]) pose[j] = poseAtRaw(rig, Math.max(0, t - rig.lag[j]))[j];
    return pose;
  }
  function poseAtRaw(rig, t) {
    const K = rig.keys;
    let i = 0;
    while (i < K.length - 1 && K[i + 1].t <= t) i++;
    const a = K[i], b = K[Math.min(K.length - 1, i + 1)];
    const f = b === a || b.t <= a.t ? 0 : ease(b.style || "Quad", b.dir || "InOut", (t - a.t) / (b.t - a.t));
    const lerp3 = (p, q) => [0, 1, 2].map((k) => (p[k] || 0) + ((q[k] || 0) - (p[k] || 0)) * f);
    const pose = {};
    for (const j of JOINTS) pose[j] = lerp3((a.pose || {})[j] || [0, 0, 0], (b.pose || {})[j] || [0, 0, 0]);
    const ra = a.root || [0, 0, 0, 0, 0], rb = b.root || [0, 0, 0, 0, 0];
    pose.root = [0, 1, 2, 3, 4].map((k) => (ra[k] || 0) + ((rb[k] || 0) - (ra[k] || 0)) * f);
    // limb stretch (rubber limbs): k x the limb's length, joint end fixed; default 1
    // a stretch value is k (length) or [k, w] (length, thickness: Gear 5's giant arm)
    pose.stretch = {};
    const sv = (s, j) => { const v = (s || {})[j]; return Array.isArray(v) ? [v[0] || 1, v[1] || 1] : [v || 1, 1]; };
    for (const j of JOINTS) { const p = sv(a.stretch, j), q = sv(b.stretch, j); pose.stretch[j] = [p[0] + (q[0] - p[0]) * f, p[1] + (q[1] - p[1]) * f]; }
    // rubber reach: [distance the real arm slides out, tube width]
    pose.reach = {};
    const rv = (s, j) => { const v = (s || {})[j]; return Array.isArray(v) ? [v[0] || 0, v[1] || 0.6] : [v || 0, 0.6]; };
    for (const j of ["RightArm", "LeftArm"]) { const p = rv(a.reach, j), q = rv(b.reach, j); pose.reach[j] = [p[0] + (q[0] - p[0]) * f, p[1] + (q[1] - p[1]) * f]; }
    pose.move = {};
    for (const j of JOINTS) { const p = (a.move || {})[j] || [0, 0, 0], q = (b.move || {})[j] || [0, 0, 0]; if (p.some((v) => v) || q.some((v) => v)) pose.move[j] = lerp3(p, q); }
    const num = (k, d) => { const p = a[k] == null ? d : a[k], q = b[k] == null ? d : b[k]; return p + (q - p) * f; };
    pose.scale = num("scale", 1);
    pose.fade = num("fade", 0);
    return pose;
  }
  function rigCFs(rig, pose) {
    const S = (rig.scale || 1) * (pose.scale == null ? 1 : pose.scale);
    const C0 = (s) => CF.fromSpec(s);
    const C = (s) => CF.fromSpec([s[0] * S, s[1] * S, s[2] * S, s[3] || 0, s[4] || 0, s[5] || 0]);   // rig-local offsets scale with the body
    const R = (e) => CF.fromSpec([0, 0, 0, e[0], e[1], e[2]]);
    const base = C0([rig.at[0], rig.at[1], rig.at[2], 0, rig.facing, 0]);
    const r = pose.root;
    const torso = CF.mul(CF.mul(base, C0([r[0], 3 * S + r[1], r[2], r[4], r[3], 0])), R(pose.Torso));
    const mv = pose.move || {};
    const chain = (pivot, rot, off, j) => { const m = (j && mv[j]) || [0, 0, 0]; return CF.mul(CF.mul(CF.mul(CF.mul(torso, C0([m[0], m[1], m[2], 0, 0, 0])), C(pivot)), R(rot)), C(off)); };
    const k = pose.stretch || {};
    const sk = (j) => (Array.isArray(k[j]) ? k[j][0] : k[j] || 1);
    const sw = (j) => (Array.isArray(k[j]) ? k[j][1] : 1);
    const rch = pose.reach || {};
    const rd = (j) => (rch[j] ? rch[j][0] : 0);
    const out = {
      Torso: torso,
      Head: chain([0, 1, 0, 0, 0, 0], pose.Head, [0, 0.5, 0, 0, 0, 0], "Head"), // real R6 Neck: head centre 1.5 above the torso
      RightArm: chain([1, 0.5, 0, 0, 0, 0], pose.RightArm, [0.5 * sw("RightArm"), 0.5 - sk("RightArm") - rd("RightArm"), 0, 0, 0, 0], "RightArm"),
      LeftArm: chain([-1, 0.5, 0, 0, 0, 0], pose.LeftArm, [-0.5 * sw("LeftArm"), 0.5 - sk("LeftArm") - rd("LeftArm"), 0, 0, 0, 0], "LeftArm"),
      RightLeg: chain([1, -1, 0, 0, 0, 0], pose.RightLeg, [-0.5 * sw("RightLeg"), -sk("RightLeg"), 0, 0, 0, 0], "RightLeg"),
      LeftLeg: chain([-1, -1, 0, 0, 0, 0], pose.LeftLeg, [0.5 * sw("LeftLeg"), -sk("LeftLeg"), 0, 0, 0, 0], "LeftLeg"),
    };
    out._scale = S;
    out._fade = pose.fade || 0;
    out.RightHand = CF.mul(out.RightArm, C([0, -sk("RightArm") - 0.15, 0, 0, 0, 0]));
    out.LeftHand = CF.mul(out.LeftArm, C([0, -sk("LeftArm") - 0.15, 0, 0, 0, 0]));
    out.RightFoot = CF.mul(out.RightLeg, C([0, -sk("RightLeg") + 0.2, -0.2, 0, 0, 0]));
    out.LeftFoot = CF.mul(out.LeftLeg, C([0, -sk("LeftLeg") + 0.2, -0.2, 0, 0, 0]));
    // the rubber tube: from inside the shoulder (y 0.35) to 0.15 inside the slid-out arm's top
    out._tube = {};
    for (const [j, sx, nm] of [["RightArm", 1, "RightTube"], ["LeftArm", -1, "LeftTube"]]) {
      const d = rd(j);
      if (d > 0.35) {
        const y0 = 0.35, y1 = 0.5 - d - 0.15;   // y1: 0.15 inside the slid-out arm's top
        out[nm] = chain([sx, 0.5, 0, 0, 0, 0], pose[j], [sx * 0.5 * sw(j), (y0 + y1) / 2, 0, 0, 0, 0], j);
        out._tube[nm] = [rch[j][1] * S, (y0 - y1) * S, rch[j][1] * S];
      }
    }
    out._stretch = {};
    for (const j of ["RightArm", "LeftArm", "RightLeg", "LeftLeg"]) out._stretch[j] = [sk(j), sw(j)];
    out.Chest = CF.mul(torso, C([0, 0.2, -0.7, 0, 0, 0]));
    out.Root = CF.mul(base, C0([r[0], r[1], r[2], 0, r[3], 0]));
    return out;
  }
  SIM.poseAt = poseAt;
  SIM.rigCFs = rigCFs;

  function descendants(it) { const out = []; const walk = (x) => { for (const c of x.children) { out.push(c); walk(c); } }; walk(it); return out; }
  function rotAxis(v, k, a) {
    const c = Math.cos(a), s = Math.sin(a);
    return V.add(V.add(V.mul(v, c), V.mul(V.cross(k, v), s)), V.mul(k, V.dot(k, v) * (1 - c)));
  }
  function invVec(cf, v) { const R = cf.R; return [R[0] * v[0] + R[3] * v[1] + R[6] * v[2], R[1] * v[0] + R[4] * v[1] + R[7] * v[2], R[2] * v[0] + R[5] * v[1] + R[8] * v[2]]; }
  function invPoint(cf, v) { return invVec(cf, V.sub(v, cf.p)); }
  function decodeProp(it, prop, v) {
    if (prop === "CFrame") return CF.fromSpec(v);
    return decode(v);
  }
  function flipFrames(p) {
    switch (p.FlipbookLayout) {
      case "Grid2x2": return 4;
      case "Grid4x4": return 16;
      case "Grid8x8": return 64;
      case "Custom": return Math.max(1, (p.FlipbookSizeX | 0) * (p.FlipbookSizeY | 0));
      default: return 1;
    }
  }
  function flipGrid(p) {
    switch (p.FlipbookLayout) {
      case "Grid2x2": return [2, 2];
      case "Grid4x4": return [4, 4];
      case "Grid8x8": return [8, 8];
      case "Custom": return [Math.max(1, p.FlipbookSizeX | 0), Math.max(1, p.FlipbookSizeY | 0)];
      default: return [1, 1];
    }
  }
  // Frame index (float, for crossfade) of a particle. Frame order is assumed
  // left-to-right, top-to-bottom (CALIBRATE with a numbered sheet).
  function flipFrame(p, q) {
    const n = flipFrames(p);
    if (n <= 1) return [0, 0, 0];
    const blend = p.FlipbookBlendFrames !== false;
    let f;
    const mode = p.FlipbookMode;
    if (mode === "OneShot") f = Math.min(n - 1, (q.age / q.life) * n);
    else if (mode === "PingPong") { const c = q.frame0 + q.age * q.fps; const per = 2 * (n - 1) || 1; const m = c % per; f = m <= n - 1 ? m : per - m; }
    else if (mode === "Random") {
      const step = Math.floor(q.age * (q.fps || 1));
      const h = (s) => { let x = Math.imul(q.seed ^ (s * 2654435761), 1597334677) >>> 0; return x % n; };
      const fa = h(step), fb = h(step + 1);
      const fr = q.age * (q.fps || 1) - step;
      return [fa, fb, blend ? fr : 0];
    } else f = (q.frame0 + q.age * q.fps) % n;
    if (q.fps === 0 && mode !== "OneShot") f = q.frame0;
    const a = Math.floor(f);
    const b = mode === "OneShot" ? Math.min(n - 1, a + 1) : (a + 1) % n;
    return [a, b, blend ? f - a : 0];
  }
  SIM.flipFrame = flipFrame;
  SIM.flipGrid = flipGrid;
  SIM.flipFrames = flipFrames;
  SIM.descendants = descendants;

  // ------------------------------------------------------------ Luau export
  // Builds the same instance tree in Roblox and plays the same timeline.
  function luauVal(prop, v, cls, texMap) {
    const num = (x) => (Math.round(x * 10000) / 10000).toString();
    if (v === null || v === undefined) return null;
    if (prop === "CFrame") {
      const c = v.R ? v : CF.fromSpec(v);
      return `CFrame.new(${c.p.map(num).join(", ")}, ${c.R.map(num).join(", ")})`;
    }
    if (typeof v === "boolean") return v ? "true" : "false";
    if (typeof v === "number") return num(v);
    if (typeof v === "string") {
      const ENUMS = {
        EmissionDirection: "NormalId", FlipbookLayout: "ParticleFlipbookLayout", FlipbookMode: "ParticleFlipbookMode",
        Orientation: "ParticleOrientation", Shape: cls === "Part" ? "PartType" : "ParticleEmitterShape", ShapeInOut: "ParticleEmitterShapeInOut",
        ShapeStyle: "ParticleEmitterShapeStyle", TextureMode: "TextureMode", Material: "Material", DepthMode: "HighlightDepthMode", Face: "NormalId",
        AlphaMode: "AlphaMode",
      };
      if (ENUMS[prop]) return `Enum.${ENUMS[prop]}.${v}`;
      if (prop === "Texture" || prop === "TextureID" || prop === "MeshId" || prop === "ColorMap" || prop === "EmissiveMask") {
        const m = texMap && texMap[v];
        return JSON.stringify(m || v);
      }
      return JSON.stringify(v);
    }
    if (v.ns) return `NumberSequence.new({${v.ns.map((k) => `NumberSequenceKeypoint.new(${num(k[0])}, ${num(k[1])}, ${num(k[2] || 0)})`).join(", ")}})`;
    if (v.cs) return `ColorSequence.new({${v.cs.map((k) => `ColorSequenceKeypoint.new(${num(k[0])}, Color3.new(${k[1].map(num).join(", ")}))`).join(", ")}})`;
    if (Array.isArray(v)) {
      const RANGE = { Lifetime: 1, Speed: 1, Rotation: 1, RotSpeed: 1, FlipbookFramerate: 1 };
      const COLOR = { Color: 1, FillColor: 1, OutlineColor: 1, TintColor: 1, EmissiveTint: 1 };
      if (RANGE[prop]) return `NumberRange.new(${num(v[0])}, ${num(v[1])})`;
      if (COLOR[prop]) return `Color3.new(${v.map(num).join(", ")})`;
      if (prop === "SpreadAngle") return `Vector2.new(${num(v[0])}, ${num(v[1])})`;
      return `Vector3.new(${v.map(num).join(", ")})`;
    }
    return null;
  }
  SIM._luauVal = luauVal;
  SIM.toLuau = function (def, texMap) {
    const w = new World(def);
    const L = [];
    L.push(`-- ${def.name || "Effect"}: generated by roblox-vfx sim. Call build(parentCFrame) then play(handle).`);
    L.push(`local TweenService = game:GetService("TweenService")`);
    L.push(`local RunService = game:GetService("RunService")`);
    L.push(`local Lighting = game:GetService("Lighting")`);
    L.push(`local M = {}`);
    L.push(`function M.build(origin)`);
    L.push(`  origin = origin or CFrame.new()`);
    L.push(`  local folder = Instance.new("Folder"); folder.Name = ${JSON.stringify(def.name || "Effect")}`);
    L.push(`  local byPath = {}`);
    let n = 0;
    const refs = [];
    const emitInst = (it, parentVar) => {
      const v = `i${n++}`;
      const cls = it.ClassName;
      const inLighting = cls === "ColorCorrectionEffect" || cls === "BloomEffect";
      L.push(`  local ${v} = Instance.new(${JSON.stringify(cls)}); ${v}.Name = ${JSON.stringify(it.Name)}`);
      const d = DEFAULTS[cls] || {};
      for (const k in it.p) {
        if (k === "Attachment0" || k === "Attachment1" || k === "Adornee") { if (it.p[k]) refs.push([v, k, it.p[k].path()]); continue; }
        if (cls === "Highlight" && k === "Adornee") continue;
        if (k === "CFrame" && it.isA("BasePart")) { L.push(`  ${v}.CFrame = origin * ${luauVal(k, it.p[k], cls, texMap)}`); continue; }
        if (JSON.stringify(it.p[k]) === JSON.stringify(d[k]) && k !== "LightInfluence" && k !== "Enabled") continue;
        const s = luauVal(k, it.p[k], cls, texMap);
        if (s !== null) L.push(`  ${v}.${k} = ${s}`);
      }
      if (cls === "ParticleEmitter") L.push(`  ${v}.Rate = ${it.p.Rate > 0 ? luauVal("Rate", it.p.Rate) : 0}`);
      if (it.isA("BasePart")) L.push(`  ${v}.Anchored = true; ${v}.CanCollide = false; ${v}.CanQuery = false; ${v}.CanTouch = false`);
      L.push(`  ${v}.Parent = ${inLighting ? "Lighting" : parentVar}; byPath[${JSON.stringify(it.path())}] = ${v}`);
      for (const c of it.children) emitInst(c, v);
    };
    for (const it of w.root.children) emitInst(it, "folder");
    for (const [v, k, path] of refs) L.push(`  ${v}.${k} = byPath[${JSON.stringify(path)}]`);
    L.push(`  folder.Parent = workspace`);
    L.push(`  return {folder = folder, byPath = byPath}`);
    L.push(`end`);
    L.push(``);
    L.push(`local function find(h, path) return h.byPath[path] end`);
    L.push(`
-- camera effects (shake + FOV punch) through one driver: each frame it takes back the offset it
-- added last frame (unless something else moved the camera since, e.g. a tween or a cut), then adds this frame's
local CamFX = {sh = {}, fv = {}}
local function camStep()
  local cam = workspace.CurrentCamera
  local now = os.clock()
  local cf, fov = cam.CFrame, cam.FieldOfView
  local base = (CamFX.lastCF and cf == CamFX.lastCF) and cf * CamFX.lastOff:Inverse() or cf
  local bfov = (CamFX.lastFov and math.abs(fov - CamFX.lastFov) < 1e-4) and fov - CamFX.lastD or fov
  local ox, oy, oz, d = 0, 0, 0, 0
  for i = #CamFX.sh, 1, -1 do
    local s = CamFX.sh[i]; local a = (now - s.t0) / s.time
    if a > 1 then table.remove(CamFX.sh, i) else
      local k = s.amp * (1 - a) ^ 2; local ph = (now - s.t0) * s.freq
      ox += math.sin(ph * 6.1) * k; oy += math.sin(ph * 7.3 + 1) * k; oz += math.sin(ph * 5.7 + 2) * k * 0.5
    end
  end
  for i = #CamFX.fv, 1, -1 do
    local f = CamFX.fv[i]; local a = now - f.t0
    if a > f.i + f.o then table.remove(CamFX.fv, i)
    elseif a < f.i then d += f.by * TweenService:GetValue(a / f.i, Enum.EasingStyle.Quad, Enum.EasingDirection.Out)
    else d += f.by * (1 - TweenService:GetValue((a - f.i) / f.o, Enum.EasingStyle.Quad, Enum.EasingDirection.InOut)) end
  end
  local off = CFrame.new(ox, oy, oz)
  cam.CFrame = base * off
  cam.FieldOfView = math.clamp(bfov + d, 1, 120)
  CamFX.lastCF, CamFX.lastOff, CamFX.lastFov, CamFX.lastD = cam.CFrame, off, cam.FieldOfView, d
  if #CamFX.sh == 0 and #CamFX.fv == 0 then
    RunService:UnbindFromRenderStep("RVFX_CamFX"); CamFX.on = false; CamFX.lastCF = nil; CamFX.lastFov = nil
  end
end
local function camfx(kind, e)
  e.t0 = os.clock()
  table.insert(kind == "shake" and CamFX.sh or CamFX.fv, e)
  if not CamFX.on then CamFX.on = true; RunService:BindToRenderStep("RVFX_CamFX", Enum.RenderPriority.Camera.Value + 2, camStep) end
end
-- screen overlays in the player's PlayerGui: "lines" = an image re-rolled at 30 Hz (focus/speed lines), "bars" = letterbox
local function overlay(h, o)
  local plr = game:GetService("Players").LocalPlayer
  local pg = plr and plr:FindFirstChildOfClass("PlayerGui"); if not pg then return end
  local g = Instance.new("ScreenGui"); g.Name = "RVFX_" .. o.kind; g.IgnoreGuiInset = true; g.ResetOnSpawn = false; g.DisplayOrder = o.order or 40
  g.Parent = pg
  task.delay(o.time + 0.05, function() g:Destroy() end)
  if o.kind == "bars" then
    for _, top in {true, false} do
      local f = Instance.new("Frame"); f.BorderSizePixel = 0; f.BackgroundColor3 = o.color; f.BackgroundTransparency = o.tr
      f.AnchorPoint = Vector2.new(0, top and 0 or 1); f.Position = UDim2.fromScale(0, top and 0 or 1); f.Size = UDim2.fromScale(1, 0); f.Parent = g
      TweenService:Create(f, TweenInfo.new(o.fin, Enum.EasingStyle.Quart, Enum.EasingDirection.Out), {Size = UDim2.fromScale(1, o.size)}):Play()
      task.delay(math.max(0, o.time - o.fout), function() TweenService:Create(f, TweenInfo.new(o.fout, Enum.EasingStyle.Quad, Enum.EasingDirection.In), {Size = UDim2.fromScale(1, 0)}):Play() end)
    end
    return
  end
  local uri = h.folder and h.folder:GetAttribute("Overlay_" .. (o.image:gsub("[^%w_]", "_")))
  if not uri or uri == "" then warn("[RVFX] overlay image missing " .. o.image); return end
  local im = Instance.new("ImageLabel"); im.BackgroundTransparency = 1; im.Image = uri; im.ImageColor3 = o.color
  im.AnchorPoint = Vector2.new(0.5, 0.5); im.Position = UDim2.fromScale(0.5, 0.5); im.Parent = g
  local t0, fr = os.clock(), -1
  local rng = Random.new(o.seed or 1)
  local c; c = RunService.RenderStepped:Connect(function()
    local a = os.clock() - t0
    if a > o.time or not g.Parent then c:Disconnect() return end
    local vp = workspace.CurrentCamera.ViewportSize
    local D = math.sqrt(vp.X * vp.X + vp.Y * vp.Y) * (o.scale or 1.08)
    local k = math.floor(a * 30)
    if k ~= fr then fr = k; im.Rotation = o.spin and rng:NextNumber(0, 360) or (o.rot or 0); local s = 1 + rng:NextNumber(-0.04, 0.04); im.Size = UDim2.fromOffset(D * s, D * s) end
    local fade = math.min(1, a / math.max(o.fin, 1e-3), (o.time - a) / math.max(o.fout, 1e-3))
    im.ImageTransparency = 1 - (1 - o.tr) * math.clamp(fade, 0, 1)
  end)
end
`);
    L.push(`function M.play(h)`);
    const simOnly = new Set();
    for (const it of w.all) if (it.spec && it.spec.simOnly) simOnly.add(it.path());
    const isSimOnly = (name) => { const it = name && w.find(name); return !!(it && [...simOnly].some((p) => it.path() === p || it.path().startsWith(p + "."))); };
    for (const e of w.events) {
      const t = (e.t || 0).toFixed(4);
      const act = e.do || e.action;
      if (act === "hit") {
        L.push(`  task.delay(${t}, function() if h.onHit then h.onHit({damage = ${e.damage || 0}, knock = Vector3.new(${(e.knock || [0, 0, 0]).join(", ")}), reaction = ${JSON.stringify(e.reaction || "flinch")}, stun = ${e.stun == null ? 0.35 : e.stun}, time = ${e.time == null ? 0.22 : e.time}${e.ultimate ? ", ultimate = true" : ""}}) end end)`);
        continue;
      }
      if (act === "face") {
        L.push(`  task.delay(${t}, function() local m = ${e.actor ? `h.actorModels and h.actorModels[${JSON.stringify(e.actor)}]` : "h.caster"}; if h.setFace and m then h.setFace(m, ${JSON.stringify(e.face || "face")}) end end)`);
        continue;
      }
      if (act === "ghost") {
        L.push(`  task.delay(${t}, function() if M.ghost then M.ghost(h, ${e.time || 0.3}, Color3.new(${(e.color || [0.8, 0.9, 1]).join(", ")}), ${e.transparency == null ? 0.35 : e.transparency}, ${e.actor ? JSON.stringify(e.actor) : "nil"}, ${e.parts ? `{${e.parts.map((x) => JSON.stringify(x)).join(", ")}}` : "nil"}, ${e.keep ? "true" : "false"}) end end)`);
        continue;
      }
      if (act === "timescale") {
        const root = e.target ? `find(h, ${JSON.stringify((w.find(e.target) || { path: () => e.target }).path())})` : "h.folder";
        L.push(`  task.delay(${t}, function() local r = ${root}; if not r then return end; local ti = TweenInfo.new(${e.time || 0}, Enum.EasingStyle.${e.style || "Quad"}, Enum.EasingDirection.${e.dir || "Out"}); for _, d in r:GetDescendants() do if d:IsA("ParticleEmitter") then ${e.time ? `TweenService:Create(d, ti, {TimeScale = ${e.value == null ? 0 : e.value}}):Play()` : `d.TimeScale = ${e.value == null ? 0 : e.value}`} end end end)`);
        continue;
      }
      if (act === "target") {
        L.push(`  task.delay(${t}, function() if M.hideTarget then M.hideTarget(h, ${e.hide ? "true" : "false"}) end end)`);
        continue;
      }
      if (e.target && isSimOnly(e.target)) continue;
      const tgt = e.target ? `find(h, ${JSON.stringify((w.find(e.target) || { path: () => e.target }).path())})` : "nil";
      if (act === "emit") L.push(`  task.delay(${t}, function() local x = ${tgt}; if x then if x:IsA("ParticleEmitter") then x:Emit(${e.count || 1}) else for _, d in x:GetDescendants() do if d:IsA("ParticleEmitter") then d:Emit(d:GetAttribute("EmitCount") or 1) end end end end end)`);
      else if (act === "set") { const it = w.find(e.target); L.push(`  task.delay(${t}, function() ${tgt}.${e.prop} = ${luauVal(e.prop, decodeProp(it, e.prop, e.value), it && it.ClassName, texMap)} end)`); }
      else if (act === "enable") L.push(`  task.delay(${t}, function() ${tgt}.Enabled = true ${e.duration ? `task.delay(${e.duration}, function() ${tgt}.Enabled = false end)` : ""} end)`);
      else if (act === "disable") L.push(`  task.delay(${t}, function() ${tgt}.Enabled = false end)`);
      else if (act === "tween") {
        const it = w.find(e.target);
        const to = e.prop === "CFrame" && e.by ? null : decodeProp(it, e.prop, e.to);
        const isPartCF = e.prop === "CFrame" && it && it.isA("BasePart");
        let goal = e.prop === "CFrame" && e.by ? `x.CFrame * ${luauVal("CFrame", CF.fromSpec(e.by))}` : luauVal(e.prop, to, it && it.ClassName, texMap);
        if (isPartCF && !e.by) goal = `h.origin and h.origin * ${goal} or ${goal}`;
        const from = e.from !== undefined ? `x.${e.prop} = ${luauVal(e.prop, decodeProp(it, e.prop, e.from), it && it.ClassName, texMap)}; ` : "";
        L.push(`  task.delay(${t}, function() local x = ${tgt}; ${from}TweenService:Create(x, TweenInfo.new(${e.time || 0.25}, Enum.EasingStyle.${e.style || "Quad"}, Enum.EasingDirection.${e.dir || "Out"}, 0, ${e.reverses ? "true" : "false"}), {${e.prop} = ${goal}}):Play() end)`);
      } else if (act === "shake") L.push(`  task.delay(${t}, function() camfx("shake", {amp = ${e.amp || 0.5}, freq = ${e.freq || 30}, time = ${e.time || 0.3}}) end)`);
      else if (act === "bloom") L.push(`  task.delay(${t}, function() local was = {}; for _, b in Lighting:GetChildren() do if b:IsA("BloomEffect") and not table.find(h.lighting or {}, b) then was[b] = b.Enabled; b.Enabled = false end end; task.delay(${e.time || 0.1}, function() for b, v in was do b.Enabled = v end end) end)`);
      else if (act === "fov") L.push(`  task.delay(${t}, function() camfx("fov", {by = ${e.by || -8}, i = ${e.i || 0.05}, o = ${e.o || 0.35}}) end)`);
      else if (act === "overlay") { const c = e.color || [1, 1, 1];
        L.push(`  task.delay(${t}, function() overlay(h, {kind = ${JSON.stringify(e.kind || "lines")}, time = ${e.time || 1}, color = Color3.new(${c.join(", ")}), tr = ${e.transparency == null ? 0.2 : e.transparency}, fin = ${e.fin == null ? 0.08 : e.fin}, fout = ${e.fout == null ? 0.2 : e.fout}, size = ${e.size || 0.11}, image = ${JSON.stringify(e.image || "sim:focus_lines")}, spin = ${e.spin === false ? "false" : "true"}, rot = ${e.rot || 0}, scale = ${e.scale || 1.08}, seed = ${e.seed || 1}, order = ${e.order || 40}}) end)`); }
      else if (act === "camera") L.push(`  task.delay(${t}, function() local cam = workspace.CurrentCamera; cam.CameraType = Enum.CameraType.Scriptable; local goal = (h.origin or CFrame.new()) * CFrame.lookAt(Vector3.new(${e.pos.join(", ")}), Vector3.new(${e.at.join(", ")}))${e.roll ? ` * CFrame.Angles(0, 0, math.rad(${e.roll}))` : ""}; ${e.time ? `if CamFX.tw then CamFX.tw:Cancel() end; CamFX.tw = TweenService:Create(cam, TweenInfo.new(${e.time}, Enum.EasingStyle.${e.style || "Quad"}, Enum.EasingDirection.${e.dir || "Out"}), {CFrame = goal${e.fov ? `, FieldOfView = ${e.fov}` : ""}}); CamFX.tw:Play()` : `if CamFX.tw then CamFX.tw:Cancel(); CamFX.tw = nil end; cam.CFrame = goal${e.fov ? `; cam.FieldOfView = ${e.fov}` : ""}`} end)`);   // a cut cancels a running camera tween (it kept running in Roblox and overwrote the cut: Detroit v3 take)
      else if (act === "path") {
        const P = e.points.map((v) => `Vector3.new(${v.join(", ")})`).join(", ");
        const off = luauVal("CFrame", CF.fromSpec(e.offset || [0, 0, 0, 0, 0, 0])), piv = luauVal("CFrame", CF.fromSpec(e.pivot || [0, 0, 0, 0, 0, 0]));
        L.push(`  task.delay(${t}, function() local x = ${tgt}; local P = {${P}}; local pts, cum = {}, {0}; for i = 1, #P - 1 do local p0, p1, p2, p3 = P[math.max(i - 1, 1)], P[i], P[i + 1], P[math.min(i + 2, #P)]; for s = 0, 15 do local u = s / 16; pts[#pts + 1] = 0.5 * ((2 * p1) + (p2 - p0) * u + (2 * p0 - 5 * p1 + 4 * p2 - p3) * u * u + (3 * p1 - p0 - 3 * p2 + p3) * u * u * u) end end; pts[#pts + 1] = P[#P]; for i = 2, #pts do cum[i] = cum[i - 1] + (pts[i] - pts[i - 1]).Magnitude end; local total = cum[#pts]; local function at(d) d = math.clamp(d, 0, total); for i = 2, #pts do if cum[i] >= d then local f = (d - cum[i - 1]) / math.max(cum[i] - cum[i - 1], 1e-6); return pts[i - 1]:Lerp(pts[i], f) end end; return pts[#pts] end; local hv = x:FindFirstChild("Hinge") or Instance.new("NumberValue"); hv.Name = "Hinge"; hv.Parent = x; local pid = (x:GetAttribute("RvfxPath") or 0) + 1; x:SetAttribute("RvfxPath", pid); local t0 = os.clock(); local c; c = RunService.Heartbeat:Connect(function() if not x.Parent or x:GetAttribute("RvfxPath") ~= pid then c:Disconnect() return end; local a = math.clamp((os.clock() - t0) / ${e.time || 1}, 0, 1); local d = TweenService:GetValue(a, Enum.EasingStyle.${e.style || "Linear"}, Enum.EasingDirection.${e.dir || "InOut"}) * total - ${e.lag || 0}; local p = at(d); local q = at(d + 0.5) - at(d - 0.5); if q.Magnitude > 1e-5 then local cf = CFrame.lookAt(p, p + q) * CFrame.Angles(0, 0, math.rad(${e.roll || 0} + ${e.spin || 0} * (os.clock() - t0))) * ${off} * ${(e.hingeAxis || "X") === "X" ? "CFrame.Angles(math.rad(hv.Value), 0, 0)" : (e.hingeAxis === "Y" ? "CFrame.Angles(0, math.rad(hv.Value), 0)" : "CFrame.Angles(0, 0, math.rad(hv.Value))")} * ${piv}; x.CFrame = h.origin and h.origin * cf or cf end end) end)`);
      } else if (act === "spin") {
        const ax = e.axis || "Y", rate = e.rate == null ? 360 : e.rate, time = e.time || 1;
        const R = (v) => (ax === "X" ? `CFrame.Angles(${v}, 0, 0)` : ax === "Y" ? `CFrame.Angles(0, ${v}, 0)` : `CFrame.Angles(0, 0, ${v})`);
        L.push(`  task.delay(${t}, function() local x = ${tgt}; if not x then return end; local t0 = os.clock(); local last, prev = nil, 0; local c; c = RunService.Heartbeat:Connect(function() if not x.Parent then c:Disconnect() return end; local a = math.min(os.clock() - t0, ${time}); local ang = math.rad(${rate} * a); local cur = x.CFrame; local base = cur; if last and (cur.Position - last.Position).Magnitude < 1e-3 and cur.LookVector:Dot(last.LookVector) > 0.99999 and cur.UpVector:Dot(last.UpVector) > 0.99999 then base = cur * ${R("-prev")} end; local out = base * ${R("ang")}; x.CFrame = out; last = out; prev = ang; if a >= ${time} then c:Disconnect() end end) end)`);
      } else if (act === "toss") L.push(`  task.delay(${t}, function() local x = ${tgt}; x.Anchored = false; x.CanCollide = true; x.AssemblyLinearVelocity = Vector3.new(${(e.vel || [0, 30, 0]).join(", ")}); x.AssemblyAngularVelocity = Vector3.new(${(e.spin || [0, 0, 0]).map((d) => (d * Math.PI / 180).toFixed(3)).join(", ")}) end)`);
      else if (act === "swing") { const ax = e.axis || "X"; const pv = e.pivot || [0, 0, 0]; const rot = ax === "X" ? "math.rad(sv.Value), 0, 0" : ax === "Y" ? "0, math.rad(sv.Value), 0" : "0, 0, math.rad(sv.Value)";
        L.push(`  task.delay(${t}, function() local x = ${tgt}; local sv = x:FindFirstChild("Swing"); if not sv then sv = Instance.new("NumberValue"); sv.Name = "Swing"; sv.Parent = x; local base = x.CFrame; local pv = CFrame.new(${pv.join(", ")}); local c; c = RunService.Heartbeat:Connect(function() if not x.Parent then c:Disconnect() return end; x.CFrame = base * pv * CFrame.Angles(${rot}) * pv:Inverse() end) end; ${e.from != null ? `sv.Value = ${e.from}; ` : ""}TweenService:Create(sv, TweenInfo.new(${e.time || 0.3}, Enum.EasingStyle.${e.style || "Quad"}, Enum.EasingDirection.${e.dir || "Out"}), {Value = ${e.to || 0}}):Play() end)`); }
      else if (act === "hinge") L.push(`  task.delay(${t}, function() local x = ${tgt}; local hv = x:FindFirstChild("Hinge"); if hv then TweenService:Create(hv, TweenInfo.new(${e.time || 0.2}, Enum.EasingStyle.${e.style || "Quad"}, Enum.EasingDirection.${e.dir || "Out"}), {Value = ${e.to || 0}}):Play() end end)`);
      else if (act === "clear") L.push(`  task.delay(${t}, function() ${tgt}:Clear() end)`);
      else if (act === "destroy" || act === "hide") L.push(`  task.delay(${t}, function() ${tgt}:Destroy() end)`);
    }
    L.push(`  task.delay(${(def.duration || 3).toFixed(2)} + 1, function() h.folder:Destroy() end)`);
    L.push(`end`);
    L.push(`return M`);
    return L.join("\n");
  };

  // ------------------------------------------------------------ recipe import
  // A roblox-vfx library recipe (harvested) -> a sim effect definition.
  SIM.fromRecipe = function (rec) {
    const kids = [];
    const timeline = [];
    (rec.layers || []).forEach((L, i) => {
      const off = L.offset || [0, 0, 0];
      const att = { class: "Attachment", name: `A${i}`, CFrame: [off[0], off[1], off[2], 0, 0, 0], children: [] };
      const props = Object.assign({}, L.props || {});
      if (L.class === "ParticleEmitter" && L.emit && L.emit.mode === "burst") { props.Rate = 0; timeline.push({ t: 0.1, do: "emit", target: `Root.A${i}.${L.name || "Layer" + i}`, count: L.emit.count || 10 }); }
      att.children.push({ class: L.class, name: L.name || "Layer" + i, props });
      kids.push(att);
    });
    return {
      name: rec.name, duration: rec.duration || 2,
      instances: [{ class: "Part", name: "Root", CFrame: [0, 3, 0, 0, 0, 0], Size: [1, 1, 1], Transparency: 1, children: kids }],
      timeline,
    };
  };

  // ------------------------------------------------------------ export
  if (typeof module !== "undefined" && module.exports) module.exports = SIM;
  root.VFXSIM = SIM;
})(typeof window !== "undefined" ? window : globalThis);
