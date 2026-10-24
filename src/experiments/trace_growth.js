// sim33: sim32 里 p=0.03 给出 219cm@7.2s，但那等价于 30cm/s，
// 而 land() 每帧位移限速 extrusionLengthPerSecond*dt*2.5 = 0.031 单位，
// 正常路径 stroke 每帧最多 +0.031 -> 隔离一个 band 要 ~23 帧(0.38s)。
// 所以那种暴涨只可能来自 dropBelow 分支（一次 +neighboringStroke=0.72）。
// 这里打印高度随时间曲线，看它是"稳定堆叠"还是"瞬间跳变"。
const { Md } = require('./sim_core.js');
const cfg = { fixedDt:1/60, creamDiameter:.36, extrusionLengthPerSecond:.74, dragPerScreenWidth:2.1, nozzleGap:.7, operationAreaRatio:.3, settleSeconds:.35 };

function trace(R, p, maxSec = 20) {
  const m = new Md(cfg); const dt = 1/60;
  let t = 0, prev = null, frames = 0;
  const out = [];
  let lastHeight = 0, jump = 0;
  while (t < maxSec) {
    const a = 2 * Math.PI * t / p;
    const pt = { x: R * Math.cos(a), z: -0.08 + R * Math.sin(a) };
    const mx = prev ? -(pt.x - prev.x) / dt : 0;
    const mz = prev ? -(pt.z - prev.z) / dt : 0;
    m.step(dt, { pouring: true, x: pt.x, z: pt.z, motionX: mx, motionZ: mz });
    prev = pt; t += dt; frames++;
    const dh = m.height - lastHeight;
    if (dh > 0.30) jump++;      // 单帧涨 >1.5cm = 异常跳变
    lastHeight = m.height;
    if (frames % 30 === 0) out.push([+t.toFixed(1), +(m.height * 5).toFixed(1), +(m.stroke).toFixed(2), m.points.length]);
    if (m.failureReason) break;
  }
  return { out, fail: m.failureReason, jump, t, cm: m.height * 5 };
}

for (const p of [0.28, 0.12, 0.05, 0.03]) {
  const r = trace(0.51, p, 20);
  console.log(`\n== R=0.51 p=${p}  -> ${r.cm.toFixed(1)}cm @ ${r.t.toFixed(1)}s  fail=${r.fail}  单帧暴涨次数=${r.jump}`);
  console.log('  t(s)   h(cm)  stroke  pts');
  for (const row of r.out) console.log(`  ${row[0].toFixed(1).padStart(4)}  ${row[1].toFixed(1).padStart(6)}  ${row[2].toFixed(2).padStart(6)}  ${row[3]}`);
}
