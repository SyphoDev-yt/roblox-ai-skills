// v5 physics audit: for every hit of every effect, where the OLD scripted target was (start + every earlier
// knock, completed, hanging) vs where the physical body really is when the hit lands. A gap > 2 studs means the
// move's effects (authored on the old positions) now miss the body: re-author that beat.
//   node sim/tools/phys_audit.js [prefix ...]    effects with {"do":"hit"} events and a sim target (Foe); the rest are skipped
// Pass: no gap > 2, no "sinks" (< -0.1), no "hovers" (> 0.1), every body that ends down "recovers".
const path = require("path");
const fs = require("fs");
const SIM = require(path.join(__dirname, "..", "vfxsim.js"));
const DIR = path.join(__dirname, "..", "effects");
const want = process.argv.slice(2);
const files = fs.readdirSync(DIR).filter((f) => f.endsWith(".json") && (!want.length || want.some((w) => f.startsWith(w))));
for (const f of files.sort()) {
  const def = JSON.parse(fs.readFileSync(path.join(DIR, f), "utf8"));
  const hits = (def.timeline || []).filter((e) => e.do === "hit").sort((a, b) => a.t - b.t);
  if (!hits.length) continue;
  const w = new SIM.World(def);
  const torso = w.all.find((it) => it.spec && it.spec.simOnly && it.Name === "FooTorso".replace("Foo", "Foe"));
  if (!torso) continue;
  let exp = torso.p.CFrame.p.slice();
  const out = [];
  for (const h of hits) {
    w.seek(Math.max(0, h.t - 1 / 120));
    const b = w.foe.Foe;
    const act = b ? b.pos : torso.p.CFrame.p;
    const gap = Math.hypot(act[0] - exp[0], act[1] - exp[1], act[2] - exp[2]);
    if (gap > 2) out.push(`  t=${h.t.toFixed(2)} ${h.reaction} dmg ${h.damage}: old [${exp.map((v) => v.toFixed(1))}] body [${act.map((v) => v.toFixed(1))}] (${b ? b.mode : "stand"}) gap ${gap.toFixed(1)}`);
    exp = exp.map((v, i) => v + (h.knock || [0, 0, 0])[i]);
  }
  // every frame: the lowest point of the body while it gets up (v5 probe: the old get-up put the legs ~0.9 into the floor)
  let low = Infinity, hover = -Infinity;
  for (let tt = 0; tt <= def.duration; tt += 1 / 30) {
    w.seek(tt);
    const bb = w.foe.Foe;
    if (bb && bb.mode === "getup" && tt - bb.up.t0 > 1 / 60) { const l = w.foeLowest(bb); low = Math.min(low, l); hover = Math.max(hover, l); }
  }
  w.seek(def.duration);
  const end = w.foe.Foe;
  const endMode = end ? end.mode : "stand";
  // the Director's recover() at DURATION: a body that is down gets up on screen before the reset
  let rec = "";
  if (end && end.mode !== "stand") {
    end.stayDown = false;
    end.ready = 0;
    let tt = def.duration;
    for (; tt <= def.duration + 2.5 && end.mode !== "stand"; tt += 1 / 30) {
      w.seek(tt);
      if (end.mode === "getup" && tt - end.up.t0 > 1 / 60) { const l = w.foeLowest(end); low = Math.min(low, l); hover = Math.max(hover, l); }
    }
    rec = end.mode === "stand" ? `, recovers in ${(tt - def.duration).toFixed(2)} s` : ", STILL DOWN 2.5 s after the end";
  }
  if (low < -0.1) out.push(`  get-up sinks to y ${low.toFixed(2)}`);
  if (hover > 0.1) out.push(`  get-up hovers: lowest point up to ${hover.toFixed(2)} above the floor`);
  console.log(`${f.replace(".json", "")}: ${hits.length} hits, ${out.length} off, ends ${endMode} at [${(end ? end.pos : exp).map((v) => v.toFixed(0))}]${rec}${low < Infinity ? `, get-up low ${low.toFixed(2)}` : ""}`);
  for (const l of out) console.log(l);
}
