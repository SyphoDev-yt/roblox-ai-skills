// Frame capture helper for review sessions: eval(await (await fetch('snap.js')).text())
// snap(effectFile, outName, times[, W, H]) -> saves out/<outName>_<i>.jpg + <outName>_times.txt, returns warnings + hit totals
window.snap = async (file, name, times, W = 640, H = 360) => {
  const d = await (await fetch('effects/' + file + '.json?' + Date.now())).json();
  app.load(d); await app.ready();
  app.world.reset(); app.world.seek(Math.max(...times)); app.R.draw(app.world); await app.ready();
  for (let i = 0; i < times.length; i++) {
    const u = app.captureFrame(times[i], W, H);
    await fetch('/save?name=' + name + '_' + i + '.jpg', { method: 'POST', body: u });
  }
  await fetch('/save?name=' + name + '_times.txt', { method: 'POST', body: 'data:text/plain;base64,' + btoa(times.map((x) => x.toFixed(2)).join(',')) });
  app.world.reset(); app.world.hits = []; app.world.seek(d.duration - 0.01);
  const hits = app.world.hits || [];
  return JSON.stringify({ warn: app.world.warnings.slice(0, 6), hits: hits.length, dmg: +hits.reduce((a, h) => a + h.damage, 0).toFixed(2) });
};
