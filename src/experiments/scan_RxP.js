// sim30: 前几批的结论是"高度 = 速度 x 稳定时长"。
// p=0.28 快但 19.2s 就漂；p=0.30 稳但慢。这里不设停手时刻，
// 让每条轨迹跑到自己失衡为止，看"稳定时长 x 速度"的真实上限在哪。
const { run } = require('./sim_run.js');

function circ(R, p, oz) {
  return (t) => {
    const a = 2 * Math.PI * t / p;
    return { x: R * Math.cos(a), z: oz + R * Math.sin(a) };
  };
}

const rows = [];
for (const R of [0.51, 0.55, 0.58, 0.62, 0.66]) {
  for (const p of [0.28, 0.30, 0.32, 0.34]) {
    const r = run(circ(R, p, -0.08), 45);
    rows.push({ R, p, cm: r.cm, t: r.t, fail: r.fail });
    console.log(`R=${R.toFixed(2)} p=${p.toFixed(2)}  h=${r.cm.toFixed(1).padStart(6)}cm  t=${r.t.toFixed(1).padStart(5)}s  ${r.fail ?? 'ok(45s)'}`);
  }
}
rows.sort((a, b) => b.cm - a.cm);
console.log('\ntop5:');
for (const o of rows.slice(0, 5))
  console.log(`  R=${o.R} p=${o.p}  ${o.cm.toFixed(1)}cm @ ${o.t.toFixed(1)}s  ${o.fail ?? 'ok'}`);
