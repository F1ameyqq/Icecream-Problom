import sys, time
from playwright.sync_api import sync_playwright

R_U   = float(sys.argv[1]) if len(sys.argv) > 1 else 0.40
PER   = float(sys.argv[2]) if len(sys.argv) > 2 else 0.85
OFFZ  = float(sys.argv[3]) if len(sys.argv) > 3 else -0.08
ALPHA = float(sys.argv[4]) if len(sys.argv) > 4 else 0.0
MAXS  = float(sys.argv[5]) if len(sys.argv) > 5 else 0.02
STOP  = float(sys.argv[6]) if len(sys.argv) > 6 else 28.0
RISK  = float(sys.argv[7]) if len(sys.argv) > 7 else 1.1
TAG    = sys.argv[8] if len(sys.argv) > 8 else "M"
STOPCM = float(sys.argv[9]) if len(sys.argv) > 9 else 999.0
SLOW   = float(sys.argv[10]) if len(sys.argv) > 10 else 0.0
DGUARD = float(sys.argv[11]) if len(sys.argv) > 11 else 0.0
BETA   = float(sys.argv[12]) if len(sys.argv) > 12 else 0.0
CCG    = float(sys.argv[13]) if len(sys.argv) > 13 else 0.0
P2     = float(sys.argv[14]) if len(sys.argv) > 14 else 0.0
PT     = float(sys.argv[15]) if len(sys.argv) > 15 else 0.0
LISS   = float(sys.argv[16]) if len(sys.argv) > 16 else 1.0

CORE = open("sim_core.js", encoding="utf-8").read()

BOOT = r"""
([coreSrc, params]) => {
  for (const t of ['pointercancel','lostpointercapture'])
    window.addEventListener(t, e => e.stopImmediatePropagation(), true);

  const mod = { exports: {} };
  new Function('module', 'exports', coreSrc)(mod, mod.exports);
  const { Md } = mod.exports;

  const area = document.querySelector('#operation-area');
  const ell = document.querySelector('#operation-area ellipse');
  const rr = ell.getBoundingClientRect();
  const CX = rr.x + rr.width/2, CY = rr.y + rr.height/2;
  const PPU = document.documentElement.clientWidth / 2.1;

  area.setPointerCapture = () => {};
  area.releasePointerCapture = () => {};
  area.hasPointerCapture = () => false;

  // overlay
  const c = document.createElement('canvas');
  c.style.cssText = 'position:fixed;inset:0;pointer-events:none;z-index:2147483647';
  document.body.appendChild(c);
  const g = c.getContext('2d');
  function resize(){ c.width = innerWidth; c.height = innerHeight; }
  resize(); addEventListener('resize', resize);
  let cur = null, path = [];
  addEventListener('pointermove', e => { cur = {x:e.clientX,y:e.clientY}; path.push({x:cur.x,y:cur.y,t:performance.now()}); });
  (function loop(){
    const now = performance.now();
    path = path.filter(p => now - p.t < 1500);
    g.clearRect(0,0,c.width,c.height);
    g.lineWidth = 2.5; g.strokeStyle = 'rgba(255,60,60,0.9)';
    g.beginPath(); path.forEach((p,i)=> i?g.lineTo(p.x,p.y):g.moveTo(p.x,p.y)); g.stroke();
    if (cur){ g.beginPath(); g.arc(cur.x,cur.y,9,0,7); g.fillStyle='rgba(255,60,60,0.9)'; g.fill();
              g.beginPath(); g.arc(cur.x,cur.y,3,0,7); g.fillStyle='#fff'; g.fill(); }
    requestAnimationFrame(loop);
  })();

  const CFG = { fixedDt:1/60, creamDiameter:.36, extrusionLengthPerSecond:.74,
                dragPerScreenWidth:2.1, nozzleGap:.7, operationAreaRatio:.3, settleSeconds:.35 };

  window.__m = {
    model: new Md(CFG),
    t: 0, last: 0, prev: null, timer: null,
    params, CX, CY, PPU, running: false, log: [],
  };
  const M = window.__m;

  // 塔的质量加权质心（单位：内部单位，乘 5 得 cm）
  M.cc = () => {
    let cx = 0, cz = 0, mm = 0;
    for (const b of M.model.bands) { const m = b.mass || 0; if (m > 0) { mm += m; cx += b.x*m; cz += b.z*m; } }
    return mm > 1e-9 ? [cx/mm, cz/mm] : [0, 0];
  };

  // 质心回中：页面在 integrate 里对指针做弦插值（圆弧被拉成直线，落点偏向圆内侧），
  // 每层偏一点，累积成质心的单向漂移 —— 这是 y1 三局都在 18s 后开始外歪的原因。
  // 用约 1s 时间常数把圆心往"质心的反向"拉，只平移圆心，不改变转速（stroke 机制不变）。
  M.cbx = 0; M.cbz = 0;
  function ccTrim(dt){
    const g = M.params.ccGain;
    if (!g) return;
    const cc = M.cc();
    const k = Math.min(1, dt);
    M.cbx += (-g * cc[0] - M.cbx) * k;
    M.cbz += (-g * cc[1] - M.cbz) * k;
  }

  const PID = 78;
  function fire(kind, sx, sy){
    area.dispatchEvent(new PointerEvent(kind, {
      bubbles:true, cancelable:true, pointerId:PID, pointerType:'touch',
      isPrimary:true, clientX:sx, clientY:sy, button:0, buttons: kind==='pointerup'?0:1
    }));
  }

  function control(){
    const { R, p, oz, alpha, maxShift, beta } = M.params;
    let sx = 0, sz = 0;
    for (const j of M.model.joints) { sx += j.ax; sz += j.az; }
    let ox = -alpha * sx, oz2 = -alpha * sz;
    // 阻尼项（D 控制）：alpha 只对倾角本身做 P 控制，塔一晃就靠它拉回来，
    // 没有对"正在以多快的速度倾"做反应，所以会振荡。beta 用倾角变化率。
    if (beta && M.pt) {
      const dts = 1/60;
      ox -= beta * (sx - M.pt[0]) / dts;
      oz2 -= beta * (sz - M.pt[1]) / dts;
    }
    M.pt = [sx, sz];
    const d = Math.hypot(ox, oz2);
    if (d > maxShift) { ox *= maxShift/d; oz2 *= maxShift/d; }
    // 时变周期：前 pT 秒内把周期从 p 线性过渡到 p2。
    // 用途：先用正常速度(p~0.28)把底座夯稳，再切到冲刺周期(p2~0.03)。
    let pNow = M.params.p;
    if (M.params.pT > 0) {
      pNow = M.params.p + (M.params.p2 - M.params.p) * Math.min(1, M.t / M.params.pT);
    } else if (M.params.pT < 0) {
      // 负的 PT = 阶跃：前 |PT| 秒用 p 稳定堆叠，之后直接切到 p2 冲刺。
      pNow = M.t < -M.params.pT ? M.params.p : M.params.p2;
    }
    // LISS != 1 时 z 轴用不同频率 => 李萨如轨迹，落点扫过圆盘内部而不只是圆周，
    // 让 dropBelow 更容易水平命中塔顶的高点（那一项能给到 0.306 单位/帧）。
    const lr = M.params.liss || 1;
    const a = 2*Math.PI*M.t/pNow;
    const az = 2*Math.PI*M.t/(pNow*lr);
    return { x: M.cbx + ox + R*Math.cos(a), z: M.cbz + oz + oz2 + R*Math.sin(az), tilt:[sx,sz] };
  }

  M.start = () => {
    M.running = true; M.t = 0; M.last = performance.now(); M.prev = null;
    M.released = false; M.relT = 0; M.settleLog = [];
    M.hiPage = -1; M.hiAt = 0; M.hf = 0; M.hEl = document.querySelector('#height');
    M.hist = []; M.lastPage = NaN; M.growth = NaN; M.log = []; M.lastSnap = 0; M.pt = null; M.dts = [];
    M.cbx = 0; M.cbz = 0;
    fire('pointerdown', CX, CY);
    const frame = (ts) => {
      if (!M.running) return;
      // 时钟必须与游戏同源：主循环 cf(e) 用的是 rAF 的 timestamp 参数，不是 performance.now()
      if (ts === undefined) ts = performance.now();
      let dt = Math.max(0, (ts - M.last)/1000);
      M.last = Math.max(M.last, ts);
      if (dt > 0.12) dt = 1/60;
      if (M.dts) { M.dts.push([M.t, dt*1000]); if (M.dts.length > 4000) M.dts.shift(); }

      if (M.released) {
        // 释放后：游戏已 pointerup，模型继续按 pouring:false 演进，直到 4 s 或失败
        M.model.step(dt, { pouring:false, x:M.prev.x, z:M.prev.z, motionX:0, motionZ:0 });
        M.relT += dt;
        if (M.relT - M.lastSnap >= 0.5) {
          M.lastSnap = M.relT;
          const tl2 = M.model.joints.reduce((a,j)=>[a[0]+j.ax,a[1]+j.az],[0,0]);
          const cc2 = M.cc();
          M.log.push([+(M.t + M.relT).toFixed(2), M.lastPage === M.lastPage ? +M.lastPage.toFixed(1) : null,
                      +(M.model.height*5).toFixed(1), +tl2[0].toFixed(2), +tl2[1].toFixed(2),
                      +M.model.risk.toFixed(2), +cc2[0].toFixed(3), +cc2[1].toFixed(3)]);
        }
        if (M.relT >= 4.0 || M.model.failureReason) { M.running = false; if (M.timer) cancelAnimationFrame(M.timer); return; }
        M.timer = requestAnimationFrame(frame);
        return;
      }

      ccTrim(dt);
      const inp = control();
      const hasDt = dt > 1e-6;
      const mx = (M.prev && hasDt) ? -(inp.x - M.prev.x)/dt : 0;
      const mz = (M.prev && hasDt) ? -(inp.z - M.prev.z)/dt : 0;
      M.model.step(dt, { pouring:true, x:inp.x, z:inp.z, motionX:mx, motionZ:mz });
      M.prev = inp; M.t += dt;
      fire('pointermove', CX - inp.x*PPU, CY - inp.z*PPU);

      // 从游戏自己的 HUD 读真实高度（不是模型预测）——分叉时以此为准
      // 每 4 帧读一次：降低主线程开销，减少自身引入的帧抖动
      if ((M.hf++ & 15) === 0) {
        M.lastPage = NaN;
        if (M.hEl) { const mm = (M.hEl.textContent || '').match(/-?\d+(?:\.\d+)?/); if (mm) M.lastPage = parseFloat(mm[0]); }
        if (M.lastPage === M.lastPage) {
          M.hist.push({ t: M.t, v: M.lastPage });
          // 窗口必须覆盖一个完整 band 周期（约 2.4s），否则层内的正常增速起伏会被误判成减速
          while (M.hist.length && M.t - M.hist[0].t > 2.6) M.hist.shift();
        }
      }
      const pc = M.lastPage;

      // 采样放在页面内部，避免跨进程 DOM 查询干扰被测页面
      if (M.t - M.lastSnap >= 0.5) {
        M.lastSnap = M.t;
        const tl = M.model.joints.reduce((a,j)=>[a[0]+j.ax,a[1]+j.az],[0,0]);
        const cc0 = M.cc();
        M.log.push([+M.t.toFixed(2), pc === pc ? +pc.toFixed(1) : null,
                    +(M.model.height*5).toFixed(1), +tl[0].toFixed(2), +tl[1].toFixed(2),
                    +M.model.risk.toFixed(2), +cc0[0].toFixed(3), +cc0[1].toFixed(3)]);
      }

      // 高度停滞 = 页面里的塔已经到顶/已塌，不能再等
      if (pc === pc) {
        if (pc > M.hiPage + 0.05) { M.hiPage = pc; M.hiAt = M.t; }
      }
      // 高速轨迹下每个 band 只要 ~0.33s，页面正常每 0.2s 就该涨一次。
      // 0.9s 的窗口太迟钝，塌陷已经发生才报；0.6s 能早 0.3s 收手。
      const stalled = (pc === pc) && (M.t - M.hiAt > 0.6);

      // 增速衰减 = 塔接近极限的前兆（比 risk 阶跃早得多）
      let growth = NaN;
      if (M.hist.length >= 2) {
        const h0 = M.hist[0], h1 = M.hist[M.hist.length - 1];
        const span = h1.t - h0.t;
        if (span > 2.2) growth = (h1.v - h0.v) / span;
      }
      M.growth = growth;
      const slow = (M.params.slowRate > 0) && (M.t > 18) &&
                   (growth === growth) && (growth < M.params.slowRate);

      // 页面与模型高度分离 = 这局已走上另一条轨迹，极限偏低，立刻收手锁住当下高度
      const split = (M.params.dGuard > 0) && (M.t > 20) && (pc === pc) &&
                    (Math.abs(pc - M.model.height * 5) > M.params.dGuard);

      if (M.t >= M.params.stopT || pc >= M.params.stopCm || stalled || slow || split ||
          M.model.risk >= M.params.riskStop || M.model.failureReason) {
        M.why = M.model.failureReason ? 'modelfail' : stalled ? 'stall' : slow ? 'slow' : split ? 'split'
              : (pc >= M.params.stopCm) ? 'height' : (M.t >= M.params.stopT) ? 'time' : 'risk';
        M.stop();
        M.timer = requestAnimationFrame(frame);   // 继续调度，进入上面的 released 分支
        return;
      }
      M.timer = requestAnimationFrame(frame);
    };
    M.timer = requestAnimationFrame(frame);
  };
  M.stop = () => {
    if (M.released) return;
    M.released = true; M.relT = 0;
    M.relHeight = M.model.height*5; M.relRisk = M.model.risk;
    fire('pointerup', CX - (M.prev?M.prev.x:0)*PPU, CY - (M.prev?M.prev.z:0)*PPU);
  };
  M.stat = () => ({
    t: M.t, relT: M.relT, released: M.released, why: M.why ?? null,
    pageCm: M.lastPage ?? null,
    modelCm: M.model.height*5, fail: M.model.failureReason,
    tilt: M.model.joints.reduce((a,j)=>[a[0]+j.ax,a[1]+j.az],[0,0]),
    risk: M.model.risk, phase: M.model.points.length, growth: M.growth,
  });
  return { CX, CY, PPU };
}
"""

log = open(f"model_{TAG}.log", "w", encoding="utf-8")
def L(*a): print(*a, file=log, flush=True)

with sync_playwright() as p:
    b = p.chromium.launch(channel="msedge", headless=False,
                          args=["--window-position=1879,258", "--window-size=520,1020"])
    pg = b.new_page(viewport={"width": 480, "height": 940}, device_scale_factor=1)
    pg.goto("https://softserve.nog.cc/", wait_until="networkidle", timeout=60000)
    time.sleep(4)
    pg.bring_to_front()
    params = {"R": R_U, "p": PER, "oz": OFFZ, "alpha": ALPHA, "maxShift": MAXS, "stopT": STOP, "riskStop": RISK, "stopCm": STOPCM, "slowRate": SLOW, "dGuard": DGUARD, "beta": BETA, "ccGain": CCG, "p2": P2, "pT": PT, "liss": LISS}
    info = pg.evaluate(BOOT, [CORE, params])
    L("boot", info, params)
    pg.evaluate("() => window.__m.start()")

    # 运行期几乎不打扰页面：页面内部自己记录，这里只低频查结果
    t0 = time.time()
    deadline = min(STOP + 12, 90)
    while time.time() - t0 < deadline:
        res = pg.evaluate("()=>{const e=document.querySelector('#result-screen');return e&&!e.hidden?e.innerText.replace(/\\n/g,' | '):null}")
        if res:
            L("RESULT:", res); break
        time.sleep(1.0)
    pg.evaluate("() => window.__m.stop()")
    time.sleep(3.5)
    res = pg.evaluate("()=>{const e=document.querySelector('#result-screen');return e&&!e.hidden?e.innerText.replace(/\\n/g,' | '):null}")
    L("FINAL:", res)

    rows = pg.evaluate("() => window.__m.log") or []
    st = pg.evaluate("() => window.__m.stat()")
    dts = pg.evaluate("() => window.__m.dts") or []
    if dts:
        import statistics as _st
        def _bucket(lo, hi):
            v = [d for (tt, d) in dts if lo <= tt < hi]
            if not v: return "n/a"
            return f"n={len(v):4d} mean={_st.mean(v):5.2f}ms max={max(v):6.2f}ms"
        L("frame dt 0-10s :", _bucket(0, 10))
        L("frame dt 10-20s:", _bucket(10, 20))
        L("frame dt 20-26s:", _bucket(20, 26))
        L("frame dt 26-30s:", _bucket(26, 30))
        L("frame dt 30-40s:", _bucket(30, 40))
    L(f"stop: t={st['t']:.2f}s why={st['why']} relT={st['relT']:.2f} page={st['pageCm']} model={st['modelCm']:.1f}")
    L("  t(s)   page  model   tiltX  tiltZ   risk     d    cx     cz")
    for r in rows:
        t_, pc_, mc_, ta, tb, rk = r[0], r[1], r[2], r[3], r[4], r[5]
        cx_, cz_ = (r[6], r[7]) if len(r) > 7 else (0.0, 0.0)
        dv = (pc_ - mc_) if pc_ is not None else float('nan')
        ps = f"{pc_:6.1f}" if pc_ is not None else "    --"
        L(f" {t_:6.2f} {ps} {mc_:6.1f}  {ta:+5.2f} {tb:+5.2f}  {rk:4.2f} {dv:+5.1f} {cx_:+6.3f} {cz_:+6.3f}")
    pg.screenshot(path=f"md_{TAG}_final.png")
    time.sleep(5)
    b.close()
log.close()
