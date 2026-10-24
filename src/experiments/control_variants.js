// sim31: sim30 证明"固定圆心匀速圆"族在 104cm 就是顶。
// 而日志显示质心 (cx,cz) 会随高度单调外漂 —— 那是页面弦插值造成的系统偏差。
// 这里测两种改族方式：
//   A. 圆心主动反向补偿（读模型自己的质心）
//   B. 时变的 R / p（底层铺宽、后期提速）
const { run } = require('./sim_run.js');

function ccOf(m) {
  let cx = 0, cz = 0, mm = 0;
  for (const b of m.bands) { const w = b.mass || 0; if (w > 0) { mm += w; cx += b.x * w; cz += b.z * w; } }
  return mm > 1e-9 ? [cx / mm, cz / mm] : [0, 0];
}

// A: 圆心按质心反向偏移
function circCC(R, p, oz, g, tau) {
  const dt = 1 / 60;
  let bx = 0, bz = 0;
  return (t, m) => {
    const [cx, cz] = ccOf(m);
    const k = Math.min(1, dt / tau);
    bx += (-g * cx - bx) * k;
    bz += (-g * cz - bz) * k;
    const a = 2 * Math.PI * t / p;
    return { x: bx + R * Math.cos(a), z: bz + oz + R * Math.sin(a) };
  };
}

// B: 时变 R / p
const ramp = (a, b, T) => (t) => a + (b - a) * Math.min(1, t / T);
function circTV(Rof, Pof, oz) {
  return (t) => {
    const a = 2 * Math.PI * t / Pof(t);
    return { x: Rof(t) * Math.cos(a), z: oz + Rof(t) * Math.sin(a) };
  };
}
const K = (v) => () => v;

const rows = [];
function go(name, pol) {
  const r = run(pol, 60);
  rows.push({ name, cm: r.cm, t: r.t, fail: r.fail });
  console.log(`${name.padEnd(30)} h=${r.cm.toFixed(1).padStart(6)}cm  t=${r.t.toFixed(1).padStart(5)}s  ${r.fail ?? 'ok'}`);
}

console.log('--- baseline ---');
go('R.51 p.28 (94.6@19.2s页面)', circTV(K(0.51), K(0.28), -0.08));

console.log('\n--- A: 圆心反向补偿 ---');
for (const g of [0.3, 0.6, 1.0])
  for (const tau of [0.5, 1.5, 4.0])
    go(`cc g=${g} tau=${tau}`, circCC(0.51, 0.28, -0.08, g, tau));

console.log('\n--- B: 时变 R（前宽后窄）---');
for (const [a, b, T] of [[0.62, 0.51, 6], [0.66, 0.51, 8], [0.58, 0.51, 4], [0.70, 0.51, 10]])
  go(`R ${a}->${b} @${T}s`, circTV(ramp(a, b, T), K(0.28), -0.08));

console.log('\n--- B: 时变 p（前慢后快）---');
for (const [a, b, T] of [[0.30, 0.28, 8], [0.32, 0.28, 10], [0.34, 0.28, 12], [0.28, 0.26, 10]])
  go(`p ${a}->${b} @${T}s`, circTV(K(0.51), ramp(a, b, T), -0.08));

console.log('\n--- B: R 宽 + p 慢 → 收 ---');
go('R.62->.51 p.30->.28 @8s', circTV(ramp(0.62, 0.51, 8), ramp(0.30, 0.28, 8), -0.08));
go('R.62->.51 p.32->.28 @10s', circTV(ramp(0.62, 0.51, 10), ramp(0.32, 0.28, 10), -0.08));

rows.sort((a, b) => b.cm - a.cm);
console.log('\ntop5:');
for (const o of rows.slice(0, 5)) console.log(`  ${o.name.padEnd(30)} ${o.cm.toFixed(1)}cm @ ${o.t.toFixed(1)}s ${o.fail ?? 'ok'}`);
