# 判定机制详解

本文描述游戏（single-page three.js 应用）内部判定链的逆向结果。所有数值均来自页面 bundle 中的常量表。

## 0. 单位系统

| 概念 | 内部单位 | 显示 |
|---|---|---|
| 长度 | 1 | 5 cm |
| 奶油直径 `creamDiameter` | 0.36 | 1.8 cm |
| 单层高度增量 `a` | 0.153 | 0.765 cm |
| band 高度 `bandHeight` | 0.72 | 3.6 cm |
| 底盘半径 `od` | 0.5 | 2.5 cm |

`a = creamDiameter / 2 × flattening = 0.18 × 0.85 = 0.153`

## 1. 高度

```
height = max(height, 落点y + a × radiusScale)
```

- **单调不减**，一旦达到就不会回落
- `radiusScale` 在正常堆叠中为 1，在收尾锥（`finish`）中从 1 降到 0.04
- 显示分数 = `floor(height × 5 × 10 + 0.5) / 10`

**推论**：单个落点最多把塔顶抬高 0.765cm。想更高，只能靠更多落点或更长存活时间。

## 2. 一个落点的三种命运

奶油在指针位置挤出，延迟 `travelSeconds = 0.22` 秒后落地。落地位置为：

```
落点 = 0.6 × 挤出时的指针位置 + 0.4 × 当前指针位置
```

这构成一层天然低通滤波——指针的高频抖动会被削弱。

落地时按优先级走三个分支：

### 2.1 正常堆叠 `land`

| 步骤 | 规则 |
|---|---|
| 漂移修正 | 加上 `pileSlump`（静止时的缓慢漂移，`pileDrift = 0.08`） |
| 塔轴拉回 | `restPosition` 迭代 6 次，把落点朝塔的弯曲轴线拉（塔完全竖直时跳过） |
| 边缘钳制 | 若塔顶仍在底盘范围内，把落点钳到 `od + 0.18 × 0.95` 半径上 |
| **位移限速** | 落点从上一个点朝目标移动，**每帧最多 0.031 单位** |
| 高度求解 | `supportHeight`：遍历所有 `stroke` 差 ≥ 0.72 的旧点，取最高支撑 |
| 高度钳制 | 再限制在 `上一层y ± max(0.8 × 位移, 0.2 × 限速)` 内 |

**限速的来历**：`extrusionLengthPerSecond × fixedDt × 2.5 = 0.74 × 1/60 × 2.5 = 0.0308`

这是整局游戏的**根本速度上限**——任何策略都无法让落点单帧移动超过这个量。

### 2.2 挂载 `dropBelow`

**触发条件**（满足其一）：

1. `|目标点 − 上一点在塔轴上的投影| > creamDiameter/2 × missShift = 0.45`
2. 累计悬空 `overhanging > hangLength × creamDiameter = 0.36`

**行为**：

- 在目标周围 `0.36` 水平半径内寻找能接住的最高点
- 把新点挂到 `该点y + a × (1 + radiusScale) = 该点y + 0.306`
- 一次性把 `stroke` 推 `0.72`，并把 `overhang` 清零

第二条最为关键：**它绕过了「需要积累 0.72 的 stroke」这个隔离条件**，让每帧都能换层。

### 2.3 洒了 `spill`

```
canCatch(x, z) = hypot(x, z) < od + creamDiameter/2 + rimGrip = 0.73
```

若直接判断失败，会用 `restPosition` 把落点拉回塔轴后再判一次。两次都失败则 `fail('spill')`，**游戏立即结束**。

## 3. `supportHeight` 与 `stroke` 隔离

```
supportHeight(x, z, 基础高度, 过滤条件) =
    遍历所有 points（从最旧开始）：
        若 stroke_current − stroke_point < 0.72  →  break
        若水平距离 < 该点半径        →  s = max(s, 该点y + 支撑高度)
```

`points` 按时间顺序存储，`stroke` 单调递增，所以：

- **只有「够旧」的点参与支撑**
- 紧邻的 0.72 stroke 窗口内的点，全部被忽略

这就是「每层 0.38 秒」的来源：`0.72 / 0.0308 ≈ 23 帧 ≈ 0.38 秒`。

**高速大圈**之所以有效，就是因为快速旋转让 `stroke` 以接近上限的速度累积，于是支撑集迅速退化成「几乎只有上一个独立层」，每层能涨满。

## 4. 失稳判定 `balance`

塔按 band 建模（每 `bandHeight = 0.72` 一个 band），每个 band 有质量、质心、倾角 `(ax, az)`。

每层的驱动力矩：

```
力矩 = 质量 × gravity × max(0, 质心偏离下层支撑轮廓的距离)
抗倾覆 = adhesion × 宽度³ / 半径
刚度   = stiffness × 宽度^stiffnessExponent × 细塔惩罚 / 半径
```

其中宽度受 `widthLimit = 1.1` 硬性截断，细塔惩罚为 `min(1, 宽度/0.7)^9`。

**失败条件**（满足其一）：

| 类型 | 判据 | 物理含义 |
|---|---|---|
| 单层 | `|ax,az| / breakAngle(0.5) ≥ 1` | 单层歪超过 28.6° |
| 整塔 | `hypot(Σax, Σaz) / toppleLean(1.2) ≥ 1` | 各层倾角叠加超过 68.8° |

**为什么越高越难**：上层质量压在下层上的力臂随高度线性增长，同样的质心偏移会产生更大的倾角。宽度被 `widthLimit` 卡死后，无法通过「堆得更粗」来抵消。

## 5. 结算判定 `settling`

松手（`pointerup`）后进入结算等待：

```
settling = !pouring && (还在空中的奶油数量 > 0 || (未失败 && 塔未静止))
```

两个条件都要清空：

1. **空中奶油落完**——`pending` 队列，最多再等 0.22 秒
2. **塔完全静止**——`resting = 最大角速度 < restSpeed(0.03)`

随后：

- `failureReason === null` → **完成！计入记录**
- `failureReason !== null` → **失去平衡了，不计入记录**

### 松手后的额外收益

松手瞬间若空中仍有奶油、且能接住，会进入 `finish` 分支：

```
高度 = 上一落点y + creamDiameter/2 × 1.25 × smoothstep(t)
半径缩放 = max(0.04, (1 − t)^0.65)
```

这一步会把剩余体积一次堆成收尾锥，**最多再加约 1.1cm**——实测最终成绩通常比停手时显示的高 1.5~2cm。

## 6. 常量速查

| 常量 | 值 | 作用 |
|---|---|---|
| `fixedDt` | 1/60 | 物理步长 |
| `creamDiameter` | 0.36 | 奶油直径 |
| `flattening` | 0.85 | 高度系数 |
| `extrusionLengthPerSecond` | 0.74 | 挤出长度率 |
| `neighboringStroke` | 0.72 | 支撑隔离阈值 |
| `missShift` | 2.5 | 挂载触发倍数 |
| `rimGrip` | 0.05 | 边缘容差 |
| `travelSeconds` | 0.22 | 落地延迟 |
| `bandDiameters` | 2 | band 高度 = 2 × 直径 |
| `widthLimit` | 1.1 | 塔宽上限 |
| `thinWidth` / `thinExponent` | 0.7 / 9 | 细塔刚度惩罚 |
| `overhangStart` / `overhangGain` | 0.44 / 2.6 | 悬空惩罚 |
| `hangDrop` / `hangLength` | 0.85 / 1 | 挂载触发 |
| `breakAngle` | 0.5 | 单层倾角阈值 |
| `toppleLean` | 1.2 | 整塔倾角阈值 |
| `restSpeed` | 0.03 | 静止判定阈值 |
| `baseStiffness` | 2 | 底层刚度倍数 |
| `pileRise` | 0.2 | 静止堆叠增速 |
