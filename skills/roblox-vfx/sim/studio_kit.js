// Studio kit exporter: an effect definition -> a Luau ModuleScript that works
// in a real game, plus the list of assets it needs uploaded.
//
//   node studio_kit.js <effect.json> <out_dir>
//
// Why not SIM.toLuau() as-is: a game Script may NOT write MeshPart.MeshId or
// SurfaceAppearance.ColorMap (capability error at runtime; an execute_luau probe
// "works" because it runs as the plugin). So the kit has two halves:
//   M.buildTemplate(assets, parent)  EDIT MODE, plugin / command bar: builds every
//                                    instance once (meshes via CreateMeshPartAsync,
//                                    textures set) and parks it under `parent`.
//   M.spawn(origin, template) + M.play(h)   RUNTIME, LocalScript: clones the
//                                    template (a clone performs no property write),
//                                    places it at `origin`, plays the timeline.
// Not exported: the sim's R6 caster animation ("rig") and "ghost" afterimages;
// put a dummy at the origin to judge scale.
"use strict";
const fs = require("fs");
const path = require("path");
const SIM = require("./vfxsim.js");

function collect(w, def) {
  const tex = new Set(), mesh = new Set();
  const visit = (it) => {
    for (const k in it.p) {
      const v = it.p[k];
      if (typeof v === "string" && v.startsWith("sim:")) (k === "MeshId" ? mesh : tex).add(v);
    }
    it.children.forEach(visit);
  };
  w.root.children.forEach(visit);
  for (const e of def.timeline || []) for (const k of ["value", "to", "from"]) if (typeof e[k] === "string" && e[k].startsWith("sim:")) tex.add(e[k]);
  for (const e of def.timeline || []) if ((e.do || e.action) === "overlay" && (e.kind || "lines") === "lines") tex.add(e.image || "sim:focus_lines");
  return { textures: [...tex].sort(), meshes: [...mesh].sort() };
}

// Roblox draws a Beam/Trail texture TRANSPOSED relative to the sim: the image's HEIGHT runs along the
// beam (top at Attachment0 / a trail's head) and its WIDTH across it (measured 2026-10-27, probes/
// beam_uv_sheet.jpg). Sim beam textures run along their width, so every Beam/Trail texture is
// exported as a transposed copy "<id>__vt" (tools/sync_vt.py writes the PNG). Without it the
// Kamehameha drew as ~9 blocks with streaks running ACROSS the beam.
function transposeBeamTextures(def) {
  const d = JSON.parse(JSON.stringify(def));
  const walk = (n) => {
    if ((n.class === "Beam" || n.class === "Trail") && n.props && typeof n.props.Texture === "string" && n.props.Texture.startsWith("sim:") && !n.props.Texture.endsWith("__vt"))
      n.props.Texture = n.props.Texture + "__vt";
    for (const c of n.children || []) walk(c);
  };
  for (const n of d.instances || []) walk(n);
  return d;
}

// Roblox draws a SurfaceAppearance's EMISSIVE everywhere the mask's colour is bright, ignoring the ColorMap's alpha
// (v4 take: the Rasenshuriken disc was a glowing white square, the Kamehameha crack decal a blue rectangle). The
// sim's textures are white + alpha, so the mask is exported as a premultiplied copy "<id>__em" (black where
// transparent; tools/sync_vt.py writes it).
function premultipliedEmissive(def) {
  const d = JSON.parse(JSON.stringify(def));
  const walk = (n) => {
    if (n.class === "SurfaceAppearance" && n.props && typeof n.props.EmissiveMask === "string" && n.props.EmissiveMask.startsWith("sim:") && !n.props.EmissiveMask.endsWith("__em"))
      n.props.EmissiveMask = n.props.EmissiveMask + "__em";
    for (const c of n.children || []) walk(c);
  };
  for (const n of d.instances || []) walk(n);
  return d;
}

function kit(def) {
  def = premultipliedEmissive(transposeBeamTextures(def));
  const w = new SIM.World(def);
  const A = collect(w, def);
  const lv = SIM._luauVal;
  const L = [];
  const name = def.name || "Effect";
  L.push(`-- ${name}: roblox-vfx Studio kit (generated). Two halves:`);
  L.push(`--   M.buildTemplate(assets, parent)  EDIT MODE from the command bar / a plugin (sets MeshId + ColorMap)`);
  L.push(`--   M.spawn(origin, template) then M.play(h)  RUNTIME from a LocalScript (clones only)`);
  L.push(`-- assets = {textures = {["sim:x"] = "rbxassetid://N"}, meshes = {["sim:y"] = "rbxassetid://MESH_ID"}}`);
  L.push(`-- meshes need the MESH id (insert the uploaded model once and read .MeshId), not the model id.`);
  L.push(`local TweenService = game:GetService("TweenService")`);
  L.push(`local RunService = game:GetService("RunService")`);
  L.push(`local Lighting = game:GetService("Lighting")`);
  L.push(`local M = {NAME = ${JSON.stringify(name)}, DURATION = ${def.duration || 3}}`);
  L.push(`M.NEEDS = {textures = {${A.textures.map((s) => JSON.stringify(s)).join(", ")}}, meshes = {${A.meshes.map((s) => JSON.stringify(s)).join(", ")}}}`);
  L.push(``);
  L.push(`local function tex(assets, id) local v = assets.textures[id]; if not v then warn("[${name}] missing texture " .. id) end; return v or "" end`);
  L.push(`-- emissive SurfaceAppearance properties differ between engine versions: try each spelling, report which failed once`);
  L.push(`M.PROP_FAILS = {}`);
  L.push(`local function soft(inst, prop, value) local ok = pcall(function() inst[prop] = value end); if not ok and not M.PROP_FAILS[inst.ClassName .. "." .. prop] then M.PROP_FAILS[inst.ClassName .. "." .. prop] = true; warn("[${name}] cannot set " .. inst.ClassName .. "." .. prop) end end`);
  L.push(`local function emissiveMask(sa, uri)`);
  L.push(`  if pcall(function() sa.EmissiveMaskContent = Content.fromUri(uri) end) then return end`);
  L.push(`  if pcall(function() sa.EmissiveMask = uri end) then return end`);
  L.push(`  if not M.PROP_FAILS.EmissiveMask then M.PROP_FAILS.EmissiveMask = true; warn("[${name}] no emissive mask property on SurfaceAppearance") end`);
  L.push(`end`);
  L.push(`local meshCache = {}`);
  L.push(`local function meshPart(assets, id)`);
  L.push(`  local uri = assets.meshes[id]`);
  L.push(`  if not uri then warn("[${name}] missing mesh " .. id); return Instance.new("Part") end`);
  L.push(`  if meshCache[uri] == nil then`);
  L.push(`    local ok, mp = pcall(function() return game:GetService("AssetService"):CreateMeshPartAsync(uri) end)`);
  L.push(`    meshCache[uri] = ok and mp or false`);
  L.push(`    if not ok then warn("[${name}] CreateMeshPartAsync failed for " .. id .. " (" .. uri .. "): " .. tostring(mp)) end`);
  L.push(`  end`);
  L.push(`  return meshCache[uri] and meshCache[uri]:Clone() or Instance.new("Part")`);
  L.push(`end`);
  L.push(``);
  L.push(`function M.buildTemplate(assets, parent)`);
  L.push(`  local folder = Instance.new("Folder"); folder.Name = M.NAME`);
  L.push(`  local I = {}   -- instances in a table: big kits (a shrine, a Susanoo) passed Luau's 200-local limit as locals`);
  let n = 0;
  const refs = [];
  const texProps = { Texture: 1, TextureID: 1, ColorMap: 1, EmissiveMask: 1 };
  const emit = (it, parentVar) => {
    if (it.spec && it.spec.simOnly) return; // the sim's stand-in target: the real target character takes the hit
    const v = `I[${n++}]`;
    const cls = it.ClassName;
    if (cls === "MeshPart") L.push(`  ${v} = meshPart(assets, ${JSON.stringify(it.p.MeshId)}); ${v}.Name = ${JSON.stringify(it.Name)}`);
    else L.push(`  ${v} = Instance.new(${JSON.stringify(cls)}); ${v}.Name = ${JSON.stringify(it.Name)}`);
    L.push(`  ${v}:SetAttribute("SimPath", ${JSON.stringify(it.path())})`);
    const d = SIM._DEFAULTS[cls] || {};
    for (const k in it.p) {
      if (k === "MeshId") continue;
      if (k === "Attachment0" || k === "Attachment1" || k === "Adornee") { if (it.p[k]) refs.push([v, k, it.p[k].path()]); continue; }
      if (JSON.stringify(it.p[k]) === JSON.stringify(d[k]) && k !== "LightInfluence" && k !== "Enabled" && k !== "Size" && k !== "CFrame") continue;
      if (k === "EmissiveMask" && typeof it.p[k] === "string") { L.push(`  emissiveMask(${v}, tex(assets, ${JSON.stringify(it.p[k])}))`); continue; }
      if (texProps[k] && typeof it.p[k] === "string" && it.p[k].startsWith("sim:")) { L.push(`  ${v}.${k} = tex(assets, ${JSON.stringify(it.p[k])})`); continue; }
      const s = lv(k, it.p[k], cls, null);
      if (s === null) continue;
      if (k === "DoubleSided") L.push(`  pcall(function() ${v}.DoubleSided = ${s} end)`);
      else L.push(`  soft(${v}, ${JSON.stringify(k)}, ${s})`);
    }
    if (cls === "ParticleEmitter") L.push(`  ${v}.Rate = ${it.p.Rate > 0 ? lv("Rate", it.p.Rate) : 0}`);
    if (cls === "Highlight") { const raw = it.spec.props && it.spec.props.Adornee; if (raw === "Dummy" || (raw && raw.Ref === "Dummy")) L.push(`  ${v}:SetAttribute("AdorneeCaster", true)`); else if (raw === "Foe" || (raw && raw.Ref === "Foe")) L.push(`  ${v}:SetAttribute("AdorneeTarget", true)`); else if (typeof raw === "string" && raw.startsWith("Actor:")) L.push(`  ${v}:SetAttribute("AdorneeActor", ${JSON.stringify(raw.slice(6))})`); }
    if (it.isA("BasePart")) L.push(`  ${v}.Anchored = true; ${v}.CanCollide = false; ${v}.CanQuery = false; ${v}.CanTouch = false; ${v}.CastShadow = false`);
    if (cls === "ColorCorrectionEffect" || cls === "BloomEffect") L.push(`  ${v}:SetAttribute("InLighting", true)`);
    L.push(`  ${v}.Parent = ${parentVar}`);
    for (const c of it.children) emit(c, v);
  };
  for (const it of w.root.children) emit(it, "folder");
  for (const e of def.timeline || []) if ((e.do || e.action) === "overlay" && (e.kind || "lines") === "lines") { const id = e.image || "sim:focus_lines"; L.push(`  folder:SetAttribute(${JSON.stringify("Overlay_" + id.replace(/[^A-Za-z0-9_]/g, "_"))}, tex(assets, ${JSON.stringify(id)}))`); }
  const byVar = {};
  for (const [v, k, p] of refs) L.push(`  for _, d in folder:GetDescendants() do if d:GetAttribute("SimPath") == ${JSON.stringify(p)} then ${v}.${k} = d end end`);
  L.push(`  folder.Parent = parent`);
  L.push(`  return folder`);
  L.push(`end`);
  L.push(``);
  L.push(`-- opts (game mode, 2026-10-30 Awakened Arena): {game = true} keeps the caster's root under the game's physics,`);
  L.push(`-- {screen = false} drops the screen-space pieces (Lighting effects, the IF* impact-frame rig) so a move someone`);
  L.push(`-- else throws never grades or blanks this player's screen. No opts = the showcase behaviour, unchanged.`);
  L.push(`function M.spawn(origin, template, opts)`);
  L.push(`  origin = origin or CFrame.new()`);
  L.push(`  local f = template:Clone()`);
  L.push(`  local byPath, light, parts = {}, {}, {}`);
  L.push(`  for _, d in f:GetDescendants() do`);
  L.push(`    local p = d:GetAttribute("SimPath"); if p then byPath[p] = d end`);
  L.push(`    if d:IsA("BasePart") then table.insert(parts, d) end`);
  L.push(`    if d:GetAttribute("InLighting") then table.insert(light, d) end`);
  L.push(`  end`);
  L.push(`  for _, d in parts do d.CFrame = origin * d.CFrame end`);
  L.push(`  local screen = not (opts and opts.screen == false)`);
  L.push(`  if not screen then for _, d in f:GetDescendants() do if d.Name:sub(1, 2) == "IF" then byPath[d:GetAttribute("SimPath") or ""] = nil; d:Destroy() end end; for _, d in light do d:Destroy() end; light = {} end`);
  L.push(`  for _, d in light do d.Parent = Lighting end`);
  L.push(`  f.Parent = workspace`);
  L.push(`  return {folder = f, byPath = byPath, origin = origin, lighting = light, screen = screen, game = opts ~= nil and opts.game == true}`);
  L.push(`end`);
  L.push(``);
  // preload: textures load late on first use (Studio test: a grey square sheet and a full-screen whiteout without it)
  L.push(`function M.preload(template)`);
  L.push(`  local list = {}`);
  L.push(`  local seen = {}`);
  // PreloadAsync on a SurfaceAppearance does not reliably fetch its maps: the Kamehameha crater drew
  // as a solid tinted square until its ColorMap streamed in (Goku run 2). Ask for every map by id too.
  L.push(`  for _, d in template:GetDescendants() do`);
  L.push(`    table.insert(list, d)`);
  L.push(`    if d:IsA("SurfaceAppearance") then for _, k in {"ColorMap", "EmissiveMask", "NormalMap", "MetalnessMap", "RoughnessMap"} do local ok, v = pcall(function() return d[k] end); if ok and typeof(v) == "string" and v ~= "" and not seen[v] then seen[v] = true; table.insert(list, v) elseif ok and typeof(v) == "Content" and v.Uri and not seen[v.Uri] then seen[v.Uri] = true; table.insert(list, v.Uri) end end end`);
  L.push(`    if d:IsA("MeshPart") then for _, k in {"MeshId", "TextureID"} do local v = d[k]; if v ~= "" and not seen[v] then seen[v] = true; table.insert(list, v) end end end`);
  L.push(`  end`);
  L.push(`  local failed = 0`);
  L.push(`  game:GetService("ContentProvider"):PreloadAsync(list, function(_, status) if status ~= Enum.AssetFetchStatus.Success then failed += 1 end end)`);
  L.push(`  return failed`);
  L.push(`end`);
  L.push(``);

  // ---------------- caster animation + held objects + afterimages (battlegrounds)
  const follow = [];
  for (const it of w.all) if (it.spec && it.spec.Follow && !it.spec.simOnly) follow.push([it.path(), it.spec.Follow, it.spec.FollowOffset || [0, 0, 0, 0, 0, 0]]);
  const foe = w.all.find((it) => it.spec && it.spec.simOnly && /Torso$/.test(it.Name));
  if (foe) L.push(`M.TARGET_AT = Vector3.new(${foe.p.CFrame.p.map((v) => (Math.round(v * 1000) / 1000)).join(", ")}) -- where the effect expects the target's torso (effect space)`);
  const rigLua = (R) => {
    const keys = (R.keys || []).slice().sort((a, b) => a.t - b.t).map((k) => {
      const pose = Object.entries(k.pose || {}).map(([j, v]) => `${j} = {${v.join(", ")}}`).join(", ");
      const st = Object.entries(k.stretch || {}).map(([j, v]) => `${j} = ${Array.isArray(v) ? `{${v.join(", ")}}` : v}`).join(", ");
      const rc = Object.entries(k.reach || {}).map(([j, v]) => `${j} = ${Array.isArray(v) ? `{${v.join(", ")}}` : `{${v}, 0.6}`}`).join(", ");
      const mv = Object.entries(k.move || {}).map(([j, v]) => `${j} = {${v.join(", ")}}`).join(", ");
      const extra = `${mv ? `, move = {${mv}}` : ""}${k.scale != null ? `, scale = ${k.scale}` : ""}${k.fade != null ? `, fade = ${k.fade}` : ""}`;
      return `{t = ${k.t}, style = ${JSON.stringify(k.style || "Quad")}, dir = ${JSON.stringify(k.dir || "InOut")}, root = {${(k.root || [0, 0, 0, 0, 0]).join(", ")}}, pose = {${pose}}${st ? `, stretch = {${st}}` : ""}${rc ? `, reach = {${rc}}` : ""}${extra}}`;
    });
    const lag = Object.entries(R.lag || {}).map(([j, v]) => `${j} = ${v}`).join(", ");
    return `{at = {${(R.at || [0, 0, 0]).join(", ")}}, facing = ${R.facing || 0}, scale = ${R.scale || 1}${R.model ? `, model = ${JSON.stringify(R.model)}` : ""}, lag = {${lag}}, keys = {\n${keys.map((k) => `  ${k},`).join("\n")}\n}}`;
  };
  if (def.rig) L.push(`M.RIG = ${rigLua(def.rig)}`);
  L.push(`M.ACTORS = {`);
  for (const a of def.actors || []) {
    const r = rigLua(a);
    L.push(`  {name = ${JSON.stringify(a.name)}, show = {${(a.show || [0, 1e9]).join(", ")}}, rig = ${r}},`);
  }
  L.push(`}`);
  L.push(`M.FOLLOW = {${follow.map(([pth, part, off]) => `{${JSON.stringify(pth)}, ${JSON.stringify(part)}, CFrame.new(${off[0]}, ${off[1]}, ${off[2]}) * CFrame.Angles(math.rad(${off[3]}), math.rad(${off[4]}), math.rad(${off[5]}))}`).join(", ")}}`);
  L.push(`local JOINTS = {"Torso", "Head", "RightArm", "LeftArm", "RightLeg", "LeftLeg"}
local LIMBS = {"RightArm", "LeftArm", "RightLeg", "LeftLeg"}
local function easeV(style, dir, a)
  if a <= 0 then return 0 elseif a >= 1 then return 1 end
  if style == "Constant" then return 0 end   -- a step key (hold until the key's time); not an Enum.EasingStyle (v4 probe: indexing it errored)
  local okS, es = pcall(function() return Enum.EasingStyle[style] end)
  local okD, ed = pcall(function() return Enum.EasingDirection[dir] end)
  return TweenService:GetValue(a, okS and es or Enum.EasingStyle.Quad, okD and ed or Enum.EasingDirection.InOut)
end
local function C(x, y, z, rx, ry, rz) return CFrame.new(x, y, z) * CFrame.Angles(math.rad(rx or 0), math.rad(ry or 0), math.rad(rz or 0)) end
-- the sim's poseAt / rigCFs, ported 1:1 (effect space; the caller applies the origin)
local function poseAtRaw(t, rig)
  local K = rig.keys
  local i = 1
  while i < #K and K[i + 1].t <= t do i += 1 end
  local a, b = K[i], K[math.min(#K, i + 1)]
  local f = 0
  if b ~= a and b.t > a.t then f = easeV(b.style, b.dir, (t - a.t) / (b.t - a.t)) end
  local pose = {stretch = {}}
  for _, j in JOINTS do
    local p, q = a.pose[j] or {0, 0, 0}, b.pose[j] or {0, 0, 0}
    pose[j] = {p[1] + (q[1] - p[1]) * f, p[2] + (q[2] - p[2]) * f, p[3] + (q[3] - p[3]) * f}
    local function sv(s) local v = (s or {})[j]; if type(v) == "table" then return v[1] or 1, v[2] or 1 end; return v or 1, 1 end
    local pk, pw = sv(a.stretch)
    local qk, qw = sv(b.stretch)
    pose.stretch[j] = {pk + (qk - pk) * f, pw + (qw - pw) * f}
  end
  local ra, rb = a.root, b.root
  pose.root = {}
  for k = 1, 5 do pose.root[k] = (ra[k] or 0) + ((rb[k] or 0) - (ra[k] or 0)) * f end
  pose.reach = {}
  for _, j in {"RightArm", "LeftArm"} do
    local p, q = (a.reach or {})[j] or {0, 0.6}, (b.reach or {})[j] or {0, 0.6}
    pose.reach[j] = {p[1] + (q[1] - p[1]) * f, p[2] + (q[2] - p[2]) * f}
  end
  pose.move = {}
  for _, j in JOINTS do
    local p, q = (a.move or {})[j], (b.move or {})[j]
    if p or q then p, q = p or {0, 0, 0}, q or {0, 0, 0}; pose.move[j] = {p[1] + (q[1] - p[1]) * f, p[2] + (q[2] - p[2]) * f, p[3] + (q[3] - p[3]) * f} end
  end
  local sa, sb = a.scale or 1, b.scale or 1
  pose.scale = sa + (sb - sa) * f
  local fa, fb = a.fade or 0, b.fade or 0
  pose.fade = fa + (fb - fa) * f
  return pose
end
function M.poseAt(t, rig)
  rig = rig or M.RIG
  local pose = poseAtRaw(t, rig)
  for j, d in rig.lag or {} do pose[j] = poseAtRaw(math.max(0, t - d), rig)[j] end   -- overlapping action
  return pose
end
function M.rigCFs(pose, rig)
  rig = rig or M.RIG
  local at, r, k = rig.at, pose.root, pose.stretch or {}
  local S = (rig.scale or 1) * (pose.scale or 1)   -- rig-local offsets scale with the body (the sim's rigCFs)
  local mv = pose.move or {}
  local base = C(at[1], at[2], at[3], 0, rig.facing, 0)
  local torso = base * C(r[1], 3 * S + r[2], r[3], r[5], r[4], 0) * C(0, 0, 0, pose.Torso[1], pose.Torso[2], pose.Torso[3])
  local function chain(px, py, pz, rot, ox, oy, oz, j) local m = j and mv[j] or {0, 0, 0}; return torso * CFrame.new(m[1], m[2], m[3]) * CFrame.new(px * S, py * S, pz * S) * C(0, 0, 0, rot[1], rot[2], rot[3]) * CFrame.new(ox * S, oy * S, oz * S) end
  local function kw(j) local v = k[j]; if type(v) == "table" then return v[1], v[2] end; return v or 1, 1 end
  local rch = pose.reach or {}
  local dR, dL = (rch.RightArm or {0})[1], (rch.LeftArm or {0})[1]
  local kRA, wRA = kw("RightArm")
  local kLA, wLA = kw("LeftArm")
  local kRL, wRL = kw("RightLeg")
  local kLL, wLL = kw("LeftLeg")
  local out = {Torso = torso, Head = chain(0, 1, 0, pose.Head, 0, 0.5, 0, "Head"), RightArm = chain(1, 0.5, 0, pose.RightArm, 0.5 * wRA, 0.5 - kRA - dR, 0, "RightArm"),
    LeftArm = chain(-1, 0.5, 0, pose.LeftArm, -0.5 * wLA, 0.5 - kLA - dL, 0, "LeftArm"), RightLeg = chain(1, -1, 0, pose.RightLeg, -0.5 * wRL, -kRL, 0, "RightLeg"), LeftLeg = chain(-1, -1, 0, pose.LeftLeg, 0.5 * wLL, -kLL, 0, "LeftLeg")}
  out.RightHand = out.RightArm * CFrame.new(0, (-kRA - 0.15) * S, 0)
  out.LeftHand = out.LeftArm * CFrame.new(0, (-kLA - 0.15) * S, 0)
  out.RightFoot = out.RightLeg * CFrame.new(0, (-kRL + 0.2) * S, -0.2 * S)
  out.LeftFoot = out.LeftLeg * CFrame.new(0, (-kLL + 0.2) * S, -0.2 * S)
  out.Chest = torso * CFrame.new(0, 0.2 * S, -0.7 * S)
  out.Root = base * C(r[1], r[2], r[3], 0, r[4], 0)
  return out
end
-- One R6 model driven by one key track: HumanoidRootPart anchored and placed every frame, each
-- Motor6D.Transform = the sim's joint rotation conjugated into the joint's frame
-- (Transform = Rc0^-1 * R * Rc0), and stretched limbs resized with the joint end held (C1 shifted
-- by (k - 1) * half the limb's length), so the pose matches the sim exactly.
local function driver(character, game)
  local hrp = character:FindFirstChild("HumanoidRootPart")
  local torso = character:FindFirstChild("Torso")
  if not (hrp and torso) then return nil end
  local animate = character:FindFirstChild("Animate")
  if animate then animate.Disabled = true end
  local hum = character:FindFirstChildOfClass("Humanoid")
  local animator = hum and hum:FindFirstChildOfClass("Animator")
  if animator then for _, tr in animator:GetPlayingAnimationTracks() do tr:Stop(0) end end
  local motors = {Torso = hrp:FindFirstChild("RootJoint"), Head = torso:FindFirstChild("Neck"), RightArm = torso:FindFirstChild("Right Shoulder"),
    LeftArm = torso:FindFirstChild("Left Shoulder"), RightLeg = torso:FindFirstChild("Right Hip"), LeftLeg = torso:FindFirstChild("Left Hip")}
  local rc0, c1, size = {}, {}, {}
  for j, m in motors do
    rc0[j] = m.C0 - m.C0.Position
    c1[j] = m.C1
    if m.Part1 then size[j] = m.Part1.Size end
  end
  if not game then hrp.Anchored = true end
  local tubes = {}
  for _, j in {"RightArm", "LeftArm"} do
    local arm = character:FindFirstChild(j == "RightArm" and "Right Arm" or "Left Arm")
    local tb = Instance.new("Part")
    tb.Name = j .. "Tube"
    tb.Shape = Enum.PartType.Cylinder
    tb.Anchored, tb.CanCollide, tb.CanQuery, tb.CanTouch, tb.CastShadow = true, false, false, false, true
    tb.Material = Enum.Material.SmoothPlastic
    tb.Color = arm and arm.Color or Color3.fromRGB(234, 184, 146)
    tb.Transparency = 1
    tb.Size = Vector3.new(1, 0.6, 0.6)
    tb.Parent = character
    tubes[j] = tb
  end
  local d = {character = character, hrp = hrp, motors = motors, tubes = tubes, scale = 1, fade = 0}
  -- fade: LocalTransparencyModifier on every part and decal (a stand fading in, a caster hidden until a fusion)
  local skin = {}
  for _, x in character:GetDescendants() do if x:IsA("BasePart") or x:IsA("Decal") then table.insert(skin, x) end end
  local function setFade(f)
    if math.abs(f - d.fade) < 0.003 then return end
    d.fade = f
    for _, x in skin do x.LocalTransparencyModifier = f end
  end
  -- scale: a key multiplier on the model as built (Model:ScaleTo scales parts AND joints); the cached joint
  -- frames and limb sizes are re-read after each rescale so the stretch code does not undo it
  local function setScale(s)
    if math.abs(s - d.scale) < 0.004 then return end
    d.scale = s
    local ok, err = pcall(function() character:ScaleTo(s) end)
    if not ok and not M.PROP_FAILS.ScaleTo then M.PROP_FAILS.ScaleTo = true; warn("[" .. M.NAME .. "] ScaleTo failed on " .. character.Name .. ": " .. tostring(err)) end
    if ok and not d.scaleLogged and math.abs(s - 1) > 0.3 then d.scaleLogged = true; local t = character:FindFirstChild("Torso"); print("[" .. M.NAME .. "] " .. character.Name .. " scale " .. string.format("%.2f", character:GetScale()) .. " torso " .. tostring(t and t.Size)) end
    for j, m in motors do rc0[j] = m.C0 - m.C0.Position; c1[j] = m.C1; if m.Part1 then size[j] = m.Part1.Size end end
  end
  function d.apply(origin, rig, pose)
    local r = pose.root
    setScale(pose.scale or 1)
    setFade(pose.fade or 0)
    local S = (rig.scale or 1) * (pose.scale or 1)
    -- game mode: the root belongs to the game's physics (replicated, owned by the player), so the root keys move
    -- the body through the RootJoint instead: same pose on screen, no fight with replication
    local D
    if game then
      -- the visual offset is where the move's path puts the root (as the showcase would place it) relative to
      -- where the root REALLY is: a client-side lunge that moved the root along the path leaves ~nothing to
      -- add (no double count, no snap back at the end), a remote player's lagging root is made up for
      D = hrp.CFrame:Inverse() * (origin * C(rig.at[1], rig.at[2], rig.at[3], 0, rig.facing, 0) * C(r[1], 3 * S + r[2], r[3], r[5], r[4], 0))
    else
      hrp.CFrame = origin * C(rig.at[1], rig.at[2], rig.at[3], 0, rig.facing, 0) * C(r[1], 3 * S + r[2], r[3], r[5], r[4], 0)
    end
    local mv = pose.move or {}
    for j, m in motors do
      local rot = pose[j]
      local o = mv[j]
      -- a joint offset (torso frame) slides the limb off its joint: Transform = Rc0^-1 * T(o) * R * Rc0
      m.Transform = rc0[j]:Inverse() * (o and CFrame.new(o[1], o[2], o[3]) or CFrame.new()) * C(0, 0, 0, rot[1], rot[2], rot[3]) * rc0[j]
      if D and j == "Torso" then m.Transform = m.C0:Inverse() * D * m.C0 * m.Transform end
    end
    for _, j in LIMBS do
      local m, s = motors[j], pose.stretch[j]
      local k, w = 1, 1
      if type(s) == "table" then k, w = s[1], s[2] elseif s then k = s end
      local rr = pose.reach and pose.reach[j]
      local rd = rr and rr[1] or 0
      if m and m.Part1 and size[j] then
        local want = Vector3.new(size[j].X * w, size[j].Y * k, size[j].Z * w)
        if (m.Part1.Size - want).Magnitude > 1e-3 then m.Part1.Size = want end
        -- hold the joint end: shift C1 by (k - 1) * half the length, and sideways by (w - 1) * half
        -- the width toward the joint's side, so a thicker limb grows outward, not into the torso;
        -- a rubber reach slides the whole limb a further rd studs out along its own line
        local jx = c1[j].Position.X
        local sx = jx > 0 and 1 or (jx < 0 and -1 or 0)
        m.C1 = CFrame.new(sx * (w - 1) * size[j].X / 2, (k - 1) * size[j].Y / 2 + rd, 0) * c1[j]
        local tb = tubes[j]
        if tb then
          if rd > 0.35 then
            -- the tube runs from inside the shoulder to 0.15 inside the slid-out limb's top, in the
            -- limb's own frame: limb top = Part1.CFrame * (0, Y*k/2, 0); shoulder end rd further up
            local top = m.Part1.CFrame * CFrame.new(0, size[j].Y * k / 2 - 0.15, 0)
            local len = rd                                  -- 0.15 inside the limb up to 0.35 above the shoulder pivot (= the sim)
            tb.Size = Vector3.new(len, rr[2], rr[2])
            tb.CFrame = top * CFrame.new(0, len / 2, 0) * CFrame.Angles(0, 0, math.rad(90))
            tb.Transparency = 0
          elseif tb.Transparency < 1 then
            tb.Transparency = 1
          end
        end
      end
    end
  end
  function d.release()
    setFade(0)
    if d.scale ~= 1 then setScale(1) end
    for j, m in motors do
      m.Transform = CFrame.new()
      if size[j] and m.Part1 then m.Part1.Size = size[j]; m.C1 = c1[j] end
    end
    for _, tb in tubes do tb:Destroy() end
    if animate then animate.Disabled = false end
  end
  return d
end
-- Drive the caster (M.RIG) and every actor (M.ACTORS: runtime copies of the caster, e.g. shadow
-- clones, shown only inside their show window) for the move's duration; parts with Follow ride
-- the rig they name ("RightHand" = caster, "Clone1.RightHand" = actor Clone1).
function M.animate(h, character)
  if not M.RIG or not character then return end
  local main = driver(character, h.game)
  if not main then warn("[" .. M.NAME .. "] caster is not an R6 rig") return end
  h.actorModels = {}
  local actors = {}
  if #M.ACTORS > 0 then
    local was = character.Archivable
    character.Archivable = true
    local folder = Instance.new("Folder")
    folder.Name = M.NAME .. "_Actors"
    h.actorFolder = folder
    local cast = game:GetService("ReplicatedStorage"):FindFirstChild("Showcase")
    cast = cast and cast:FindFirstChild("Cast")
    for _, a in M.ACTORS do
      -- an actor copies the caster, another rig ("model" = a Showcase.Cast name: The World, Vegeta) or the target ("@target")
      local src = character
      if a.rig.model == "@target" then src = h.target elseif a.rig.model then src = cast and cast:FindFirstChild(a.rig.model) end
      if not src then warn("[" .. M.NAME .. "] no model for actor " .. a.name .. " (" .. tostring(a.rig.model) .. ")"); continue end
      local wasA = src.Archivable
      src.Archivable = true
      local c = src:Clone()
      src.Archivable = wasA
      for _, x in c:GetDescendants() do if x:IsA("BillboardGui") or x:IsA("Highlight") then x:Destroy() end end
      c.Name = a.name
      for _, x in c:GetDescendants() do if x:IsA("BaseScript") then x:Destroy() end end
      local hum = c:FindFirstChildOfClass("Humanoid")
      if hum then hum.DisplayDistanceType = Enum.HumanoidDisplayDistanceType.None end
      local d = driver(c)
      if d then table.insert(actors, {spec = a, model = c, d = d, shown = false}) h.actorModels[a.name] = c end
    end
    character.Archivable = was
    folder.Parent = workspace
  end
  local t0 = os.clock()
  local hold = M.DURATION + 0.6
  local conn
  -- game mode drives the joints on Stepped: on a live character the Animator rewrites Motor6D.Transform after
  -- RenderStepped, so poses written there never showed (2026-10-30, Awakened Arena: the effects played, the body
  -- stood idle). Stepped runs after the animation step, so these poses win. The showcase (anchored dummies)
  -- keeps RenderStepped, unchanged.
  conn = (h.game and RunService.Stepped or RunService.RenderStepped):Connect(function()
    local t = os.clock() - t0
    if t > hold or not character.Parent then
      conn:Disconnect()
      main.release()
      if h.actorFolder then h.actorFolder:Destroy() end
      if h.targetHidden then M.hideTarget(h, false) end
      return
    end
    local sets = {}
    local pose = M.poseAt(t, M.RIG)
    main.apply(h.origin, M.RIG, pose)
    sets[""] = M.rigCFs(pose, M.RIG)
    for _, A in actors do
      local on = t >= A.spec.show[1] and t < A.spec.show[2]
      if on then
        local p = M.poseAt(t, A.spec.rig)
        A.d.apply(h.origin, A.spec.rig, p)
        sets[A.spec.name] = M.rigCFs(p, A.spec.rig)
        if not A.shown then A.shown = true; A.model.Parent = h.actorFolder end
      elseif A.shown then
        A.shown = false
        A.model.Parent = nil
      end
    end
    for _, f in M.FOLLOW do
      local part = h.byPath[f[1]]
      local who, pn = string.match(f[2], "^(.-)%.(.+)$")
      local cfs = sets[who or ""]
      local cf = cfs and cfs[pn or f[2]]
      if part and cf then part.CFrame = h.origin * cf * f[3] end
    end
  end)
end
-- the real target hidden while a copy of it ("@target" actor) acts (cut apart, frozen, shattered); the
-- health bar (a BillboardGui) stays up so the damage still reads
function M.hideTarget(h, on)
  local tg = h.target
  if not tg then return end
  h.targetHidden = on
  for _, x in tg:GetDescendants() do if x:IsA("BasePart") or x:IsA("Decal") then x.LocalTransparencyModifier = on and 1 or 0 end end
end
-- afterimage: an anchored copy of the caster's (or an actor's) visible body at this instant, fading out
function M.ghost(h, life, color, tr0, actor, parts, keep)
  local character = actor and h.actorModels and h.actorModels[actor] or h.caster
  if not character then return end
  local only
  if parts then
    -- sim joint names -> R6 part names ("RightArm" is "Right Arm" on a real rig; v1 matched nothing,
    -- so the Gatling's arm afterimages never appeared), plus that limb's rubber tube
    local R6 = {RightArm = "Right Arm", LeftArm = "Left Arm", RightLeg = "Right Leg", LeftLeg = "Left Leg"}
    only = {}
    for _, p in parts do only[p] = true; if R6[p] then only[R6[p]] = true end; only[p .. "Tube"] = true end
  end
  local folder = Instance.new("Folder")
  folder.Name = "Ghost"
  for _, d in character:GetDescendants() do
    if d:IsA("BasePart") and d.Transparency < 1 and d.Name ~= "HumanoidRootPart" and (not only or only[d.Name] or (d.Parent:IsA("Accessory") and false)) then
      local g = d:Clone()
      for _, c in g:GetChildren() do if not (c:IsA("SpecialMesh") or (keep and (c:IsA("Decal") or c:IsA("SurfaceAppearance")))) then c:Destroy() end end
      g.Anchored, g.CanCollide, g.CanQuery, g.CanTouch, g.CastShadow = true, false, false, false, false
      g.CFrame = d.CFrame
      if not keep then
        g.Color = color
        g.Material = Enum.Material.Neon
        if g:IsA("MeshPart") then g.TextureID = "" end
      end
      g.Transparency = tr0
      g.Parent = folder
      TweenService:Create(g, TweenInfo.new(life, Enum.EasingStyle.Quad, Enum.EasingDirection.In), {Transparency = 1}):Play()
    end
  end
  folder.Parent = workspace
  task.delay(life + 0.1, function() folder:Destroy() end)
end
`);
  // stage lighting the effect was designed under (the sim's stage); restored by play()'s cleanup
  const st = def.stage || {};
  const night = st.sky === "night";
  const fog = st.fog;
  L.push(`M.STAGE = {night = ${night ? "true" : "false"}${fog ? `, fogStart = ${fog[0]}, fogEnd = ${fog[1]}, fogColor = Color3.new(${fog[2].join(", ")})` : ""}}`);
  L.push(`function M.applyStage(h)`);
  L.push(`  local keep = {ClockTime = Lighting.ClockTime, Brightness = Lighting.Brightness, Ambient = Lighting.Ambient, OutdoorAmbient = Lighting.OutdoorAmbient, FogStart = Lighting.FogStart, FogEnd = Lighting.FogEnd, FogColor = Lighting.FogColor}`);
  L.push(`  h.restoreStage = function() for k, v in keep do Lighting[k] = v end end`);
  L.push(`  if M.STAGE.night then Lighting.ClockTime = 0; Lighting.Brightness = 0.6; Lighting.Ambient = Color3.new(0.05, 0.06, 0.1); Lighting.OutdoorAmbient = Color3.new(0.12, 0.14, 0.22) end`);
  L.push(`  if M.STAGE.fogEnd then Lighting.FogStart = M.STAGE.fogStart; Lighting.FogEnd = M.STAGE.fogEnd; Lighting.FogColor = M.STAGE.fogColor end`);
  L.push(`end`);
  L.push(``);
  // reuse the sim exporter's play() body, then fix the two origin gaps
  const full = SIM.toLuau(def, null);
  const pStart = full.indexOf("local function find(h, path)");
  let play = full.slice(pStart, full.lastIndexOf("return M"));
  // a timeline "set" of a part CFrame must be relative to the origin too
  play = play.replace(/(task\.delay\([0-9.]+, function\(\) find\(h, "[^"]+"\))\.CFrame = (CFrame\.new\([^)]*\))/g, "$1.CFrame = h.origin * $2");
  // clean up the Lighting effects with the folder
  play = play.replace(/task\.delay\(([0-9.]+) \+ 1, function\(\) h\.folder:Destroy\(\) end\)/, "task.delay($1 + 1, function() h.folder:Destroy(); for _, d in h.lighting do d:Destroy() end end)");
  if (def.camera && def.camera.pos) {
    const c = def.camera;
    // the sim starts every effect on def.camera; Studio otherwise shows the player follow cam until the first camera event
    play = play.replace("function M.play(h)\n", `function M.play(h)\n  do local cam = workspace.CurrentCamera; cam.CameraType = Enum.CameraType.Scriptable; cam.CFrame = (h.origin or CFrame.new()) * CFrame.lookAt(Vector3.new(${c.pos.join(", ")}), Vector3.new(${c.at.join(", ")})); cam.FieldOfView = ${c.fov || 70} end\n`);
  }
  play = play.replace(/for _, d in h\.lighting do d:Destroy\(\) end end\)/, "for _, d in h.lighting do d:Destroy() end; if h.restoreStage then h.restoreStage() end end)");
  play = play.replace("function M.play(h)\n", "function M.play(h)\n  if h.caster then M.animate(h, h.caster) end\n  for _, d in h.folder:GetDescendants() do if d:IsA(\"Highlight\") and d:GetAttribute(\"AdorneeCaster\") then d.Adornee = h.caster end; if d:IsA(\"Highlight\") and d:GetAttribute(\"AdorneeTarget\") then d.Adornee = h.target end; if d:IsA(\"Highlight\") and d:GetAttribute(\"AdorneeActor\") and h.actorModels then d.Adornee = h.actorModels[d:GetAttribute(\"AdorneeActor\")] end end\n");
  // game mode: camera, shake, FOV, overlays and bloom only play where h.screen is allowed, and a timeline set on a
  // piece spawn() dropped (the IF* rig) is skipped instead of erroring
  play = play.replace(/task\.delay\(([0-9.]+), function\(\) (camfx\(|local was = \{\}; for _, b in Lighting|overlay\(h,|local cam = workspace\.CurrentCamera)/g, "task.delay($1, function() if h.screen == false then return end; $2");
  play = play.replace(/task\.delay\(([0-9.]+), function\(\) find\(h, ("[^"]+")\)\.(\w+) = /g, "task.delay($1, function() local x = find(h, $2); if not x then return end; x.$3 = ");
  play = play.replace("  do local cam = workspace.CurrentCamera;", "  if h.screen ~= false then local cam = workspace.CurrentCamera;");
  L.push(play.trimEnd());
  L.push(`return M`);
  return { lua: L.join("\n"), assets: A };
}

if (require.main === module) {
  const [, , file, outDir] = process.argv;
  const def = JSON.parse(fs.readFileSync(file, "utf8"));
  const { lua, assets } = kit(def);
  fs.mkdirSync(outDir, { recursive: true });
  const base = path.basename(file, ".json");
  fs.writeFileSync(path.join(outDir, base + ".luau"), lua);
  fs.writeFileSync(path.join(outDir, base + ".assets.json"), JSON.stringify(assets, null, 1));
  console.log(base, "textures", assets.textures.length, "meshes", assets.meshes.length, "lines", lua.split("\n").length);
}
module.exports = { kit };
