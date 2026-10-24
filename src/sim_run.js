const { Md } = require('./sim_core.js');
const cfg = { fixedDt:1/60, creamDiameter:.36, extrusionLengthPerSecond:.74, dragPerScreenWidth:2.1, nozzleGap:.7, operationAreaRatio:.3, settleSeconds:.35 };

function run(policy, maxSec = 400, opts = {}) {
  const m = new Md(cfg);
  const dt = 1/60;
  let t = 0, prev = null, lastH = 0, stall = 0;
  while (t < maxSec) {
    const p = policy(t, m);
    const mx = prev === null ? 0 : -(p.x - prev.x) / dt;
    const mz = prev === null ? 0 : -(p.z - prev.z) / dt;
    m.step(dt, { pouring: true, x: p.x, z: p.z, motionX: mx, motionZ: mz });
    prev = p; t += dt;
    if (m.height > lastH + 1e-4) { lastH = m.height; stall = 0; } else stall += dt;
    if (m.failureReason) break;
    if (stall > 8) break; // no growth for 8s -> dead end
  }
  return { height: m.height, cm: m.height * 5, t, fail: m.failureReason, stall, bands: m.bands.length, points: m.points.length, m };
}

const circle = (R, period, phase = 0) => (t) => {
  const a = 2 * Math.PI * t / period + phase;
  return { x: R * Math.cos(a), z: R * Math.sin(a) };
};

function report(name, r) {
  console.log(`${name.padEnd(26)} h=${r.cm.toFixed(1).padStart(6)}cm  t=${r.t.toFixed(1)}s  fail=${r.fail ?? 'ok'}  stall=${r.stall.toFixed(1)}`);
}

if (require.main === module) {
  report('still', run(() => ({ x: 0, z: 0 })));
  report('R68 p2.2 (browser 22.7)', run(circle(0.2975, 2.2)));
  report('R45 p1.6 (browser 21.7)', run(circle(0.197, 1.6)));
  report('R45 p1.6 v2', run(circle(0.197, 1.6)));
  for (const R of [0.25, 0.35, 0.45, 0.55, 0.65]) {
    for (const p of [1.6, 2.2, 3.0, 4.0]) report(`R${(R*227).toFixed(0)}px p${p}`, run(circle(R, p)));
  }
}
module.exports = { run, circle, cfg, Md };
