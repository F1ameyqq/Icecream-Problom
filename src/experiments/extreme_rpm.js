// sim32: spill 判的是"落点到塔顶中心的距离"(R < od + .18 + .05)，与每帧步长无关。
// 所以 p 可以压得极小：每帧落点大跨跳变 -> stroke 一步涨过 neighboringStroke(.72)
// -> 相邻点互不算支撑 -> 每层独立涨满，不靠"时间累积"。
const { run } = require('./sim_run.js');

const circ = (R, p, oz) => (t) => {
  const a = 2 * Math.PI * t / p;
  return { x: R * Math.cos(a), z: oz + R * Math.sin(a) };
};

const rows = [];
function go(name, pol, maxSec = 25) {
  const r = run(pol, maxSec);
  rows.push({ name, cm: r.cm, t: r.t, fail: r.fail });
  console.log(`${name.padEnd(22)} h=${r.cm.toFixed(1).padStart(6)}cm  t=${r.t.toFixed(1).padStart(5)}s  ${r.fail ?? 'ok'}`);
}

for (const R of [0.30, 0.45, 0.51, 0.58, 0.65]) {
  for (const p of [0.01, 0.02, 0.03, 0.05, 0.08, 0.12]) {
    go(`R=${R} p=${p}`, circ(R, p, -0.08));
  }
  console.log('');
}
rows.sort((a, b) => b.cm - a.cm);
console.log('top5:');
for (const o of rows.slice(0, 5)) console.log(`  ${o.name.padEnd(22)} ${o.cm.toFixed(1)}cm @ ${o.t.toFixed(1)}s ${o.fail ?? 'ok'}`);
