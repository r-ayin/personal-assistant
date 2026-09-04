# DESIGN.md — 个人助手「生命记忆」设计合约 v4 · 年轮 · 墨迹（亮色）

> Category: Personal Memory Organism — Ink & Growth Rings
> 设计哲学：记忆不是数据库，是一个活着的有机体——一棵被锯开断面的树。
> 一圈年轮 = 一段人生时期；环宽 = 该时期的记忆密度；同心层级 = 关系的亲疏（Dunbar 分层）；
> 朱砂 = 落印，标记不可改写的证据。
> v4（2026-09-01）从「晨纸菌林」翻作「年轮 · 墨迹」：概念不变（活的有机体），图案全换。
> 动效合约同步从「呼吸与烛火」翻作「**生长与断裂**」：墨线自生长、印章盖下、墨滴入水，
> 允许 spring 过冲与快速交错——用户已批准全面放开（见 §6.5 变更理由）。
> 界面上的一切面向用户的词汇均为中文（数据层英文键由 `lib/labels.ts` 显示层翻译）。
>
> **Token 单一真源是 `app/globals.css` 的 `:root`**。本包内 `tokens.css` / `tailwind-v4.css`
> 只是它的规范化参考件；两处不一致时，以 globals.css 为准并回头修参考件。

## 1. 视觉主题与氛围

- **基调**：瓷白纸面 + 松烟墨线。像一册摊开的宣纸图谱，墨线在纸面自行生长，朱砂偶尔落印。
- **隐喻系统**：
  - **时刻（moments）** = 盖了朱砂印的纸片，左缘印线可被"盖章"生长
  - **记忆库** = 同心年轮（环 = 时期，环宽 = 密度，层级 = 关系亲疏）
  - **对话** = 墨迹逐字生长，召回的记忆以靛青墨点标注
  - **上传（录音/转写）** = 墨滴入水，canvas 晕开
  - **背景** = 双层年轮微差速反转（摩尔纹干涉）+ feTurbulence 毛边墨晕 + 等高线漂移 + 纸颗粒
- **亮底三原则**：发光/拖尾在白底上几乎不可见，冲击力一律来自
  ① 高对比墨线自生长（stroke-dashoffset / pathLength）② 摩尔纹干涉 ③ 朱砂高饱和对比 + 动力排版。
- **绝对禁止**：企业感、表格堆砌、灰白卡片、无意义 emoji、拟物图标、霓虹辉光依赖、
  冷色渐变文字（`background-clip:text` + 子元素 transform，见 §3）。

## 2. 色彩（Color）

单一真源：`app/globals.css :root`。四强调色语义分工不可换：

- **瓷白三段**：`--porcelain-0 #F5F5F2`（页面）→ `--porcelain-1 #EDEDE8`（浮层）→ `--porcelain-2 #FCFCFA`（卡片）
- **松烟墨四级**：`--ink-900 #14161A` / `--ink-700` / `--ink-500` / `--ink-300`（文本三级映射为 `--text-main/dim/weak`）
- **朱砂 `--cinnabar #D6382B`**：唯一高饱和强调——印章、证据、时刻、激活指示
- **靛青 `--indigo #1E4D7B`**：交互 / 链接 / 进行中（`--interactive`）
- **石绿 `--mineral #2C7A58`**：成功 / 健康（`--positive`）；**赭石 `--ochre #A2701F`**：提醒 / 注意（`--caution`）
- **线条**：`--hairline / --hairline-mid / --hairline-strong`；年轮线 `--ring-line`；激活缘 `--edge-active`
- **alpha 梯度**：`--ink-02..18`、`--cin-04..28`、`--ind-04..40`、`--min-08..30`、`--och-08..20`。
  页面内联样式一律 `var(--xxx)`，**杜绝硬编码 rgba/hex**（构建前 grep 校验）。新色需求先加 token。
- 组件只认语义别名 `--accent/--interactive/--positive/--caution`，换主题时只改这四行映射。

## 3. 字体（Typography）

- **标题/时刻引文/低语**：思源宋体 `--font-serif`（Noto Serif SC），字重 600~700
- **正文**：思源黑体 `--font-sans` 400/500；**等宽**：`--font-mono` 仅时间戳与计数
- **页面大标题 `.pa-title`**：**实色墨 + 朱砂下划线自生长**（scaleX 0→1，overshoot）。
  **禁用 `background-clip:text` 渐变标题**：子元素带 transform/filter 会打断父级裁剪，
  整段标题隐形（v3 TitleStagger 的真实事故）。逐字动效因此才成为可能。
- 字号阶梯：12/13/14/16/20/26/34/52

## 4. 空间与信息架构

- 全局框架：左侧墨线导轨（76px，hover 展开 232px，overshoot 曲线）+ 主内容区 + 底部一线墨痕呼吸条
- **5 目的地 × tab**（单一真源 `lib/nav.ts`）：今天(4)/对话(0)/画像(4)/记忆(3)/系统(4)；
  tab 走 `?tab=` 查询参数（`lib/useTab.ts`），切换用带方向的横向转场而非整页重载
- 内容区最大宽度 1360px；卡片圆角收紧（`--r-lg 16px`），薄瓷底 + 发丝硬边 + 冷灰短促投影

## 5. 页面清单（v4 信息架构）

| 目的地 | 路由 | tab | 核心表达 |
|------|------|-----|----------|
| 今天 | `/` 与 `/today/` | 此刻 / 日程 / 提醒 / 推荐 | 年轮核自生长（环数=记忆年数，每第 7 环加粗）+ 计数逐位弹入 + 日程/提醒双栏 |
| 对话 | `/chat/` | —（无 tab） | 消息入场 + 最新回答逐字 spring 生长，证据以墨点浮层展示原文 |
| 画像 | `/portrait/` | 我 / 关系圈 / 单人档案 / 复杂度指标 | 诚实占位（等后端 P2/P4/P5），不编造假画像 |
| 记忆 | `/memory/` | 时刻 / 检索 / 知识 | 朱砂印纸片墙 + 混合召回 + 实体卡片与关系图 |
| 系统 | `/system/` | 摄入 / 助手人格 / 校验 / 设置 | 墨滴入水投喂区（canvas）+ 人格工作台 + 分拣 + 极简设置 |

9 个旧路由（/calendar /reminders /recommend /memories /wiki /inbox /persona /verify /settings）
由 `components/LegacyRedirect.tsx` 客户端重定向到对应 tab。端点接线矩阵见 `USAGE.md`。

## 6. 动效规范（Motion）——「生长与断裂」

**原则**：运动即生长与断裂。生长 = 墨线自画、印章压下、墨滴晕开、逐字立起；
断裂 = 快速切换、overshoot 回弹、硬边收束。曲线与 spring 预设单一真源 `lib/motion.ts`
（CSS 侧一一对应 `--ease-out/overshoot/snap/ink`，改一处必须同步另一处）。

### 6.1 允许的动效语汇（每条附实现样例）

1. **spring 过冲**（v3 明令禁止，v4 放开）——入场回弹、tab 游标滑动：
   ```tsx
   import { SPRING } from "@/lib/motion";
   <motion.span layoutId="tab-ink" transition={SPRING.bouncy} />
   ```
2. **快速交错**（30~60ms stagger 配 overshoot 曲线，制造"生长"感）：
   ```tsx
   <motion.div initial="hidden" animate="show"
     variants={{ show: { transition: { staggerChildren: 0.045 } } }}>
     {items.map(x => <motion.span key={x} variants={slideOvershoot} />)}
   </motion.div>
   ```
3. **SVG path 自生长**（亮底冲击力的第一来源；`pathLength` 0→1）：
   ```tsx
   import { RING_HIDDEN, RING_SHOW, ringDraw } from "@/lib/motion";
   <motion.circle r={r} initial={RING_HIDDEN} animate={RING_SHOW}
     transition={ringDraw(1.2, i * 0.1)} style={{ pathLength: undefined }} />
   ```
4. **动力排版逐字 3D**（`charReveal`：rotateX -52°→0 + spring；只对实色文字用，见 §3）：
   ```tsx
   <motion.h1 className="pa-title" style={{ perspective: 600 }}
     initial="hidden" animate="show"
     variants={{ show: { transition: { staggerChildren: 0.035 } } }}>
     {title.split("").map((ch, i) => <motion.span key={i} className="char-span" variants={charReveal}>{ch}</motion.span>)}
   </motion.h1>
   ```
5. **canvas 墨滴**（投喂区：墨滴入水晕开，不规则边缘用多谐波半径扰动）：
   ```tsx
   // components/InkDropCanvas.tsx：rAF 驱动，颜色经 getComputedStyle 读 var(--ink-900)
   ctx.globalAlpha = 0.5 * (1 - t); ctx.beginPath();
   for (let a = 0; a <= Math.PI * 2; a += 0.12) {
     const rr = radius * (1 + 0.18 * Math.sin(a * 3 + seed) + 0.1 * Math.sin(a * 7 - seed));
     ctx.lineTo(x + rr * Math.cos(a), y + rr * Math.sin(a));
   }
   ctx.fill();
   ```
6. **clip-path / 墨晕揭示**（区块从墨点里洇开）：
   ```css
   .ink-reveal { clip-path: circle(0% at 12% 50%); animation: ink-reveal 0.9s var(--ease-ink) forwards; }
   @keyframes ink-reveal { to { clip-path: circle(150% at 12% 50%); } }
   ```
7. **scroll-driven 编排**（gsap ScrollTrigger，已装 ^3.12；静态导出下客户端可用）：
   ```tsx
   gsap.fromTo(el, { y: 40, opacity: 0 }, { y: 0, opacity: 1,
     scrollTrigger: { trigger: el, start: "top 85%" }, ease: "power3.out" });
   gsap.to(el, { y: -48, scrollTrigger: { trigger: el, scrub: 0.6 } }); /* 视差 */
   ```
8. **3D 变换**（卡片悬浮 rotateX/rotateY 微倾、逐字 rotateX，父级需 `perspective`）
9. **摩尔纹常驻氛围**（双层年轮 `--moire-a:168s` / `--moire-b:181s` 反向差速，纯 CSS）
10. **盖章生长**（`.firefly-seed:hover` 朱砂左缘线 scaleY 0→1，origin top，overshoot）

### 6.2 保留的硬约束（不可协商）

- **reduced-motion 三层降级**，缺一即返工：
  ① `app/layout.tsx` 的 `<MotionConfig reducedMotion="user">`（framer 全局）；
  ② `globals.css` 的 `@media (prefers-reduced-motion: reduce)` 块（CSS 全量 !important 复位 + 氛围层关停）；
  ③ 组件内 `useReducedMotion()` 判断，降级分支**渲染纯静态可见元素**（参照 `components/Reveal.tsx`）。
  gsap / canvas 同样受 ③ 约束：reduced 时不注册 ScrollTrigger、不跑 rAF。
- **可见性铁律**：禁止 `initial={{opacity:0}}` 直接包住整页或大块容器；一切淡入必须走
  `Reveal / RevealGroup / RevealItem`（自带停摆兜底：1.4s 动画不推进就改渲染静态元素）。
  小元素（单卡、单行、字符）可用 motion，但必须配 reduced 静态分支。
- **频闪受限放行**：同屏高频闪烁元素 **≤1 处**，且必须同时满足：闪烁频率 <3Hz、
  非纯黑白全屏反转、单个闪烁区域 < 屏幕 10%。理由：WCAG 2.3.1 的癫痫安全阈值是每秒 3 次闪；
  低于该阈值且小面积的闪烁对光敏性人群风险可控，故从 v3 的全面禁止改为限量放行。
  常驻氛围（摩尔纹、墨晕、等高线）是**连续慢速**运动，不属于闪烁。
- 动画属性优先 transform / opacity / filter / stroke-dashoffset / pathLength / clip-path；
  避免布局属性（width/top/margin）动画（`ripple-ring` 的历史遗留除外，新代码用 canvas 替代）。

### 6.3 时长与节奏

- 断裂类（tab 切换、路由转场、按钮反馈）：0.18~0.34s，`EASE.snap`
- 生长类（入场、path 自画、盖章）：0.5~1.4s，`EASE.out / EASE.ink / SPRING.bouncy`
- 常驻氛围：46s~181s 极慢循环；同一元素不叠加两种以上运动

### 6.4 关键落点清单（v4 已实现）

| 落点 | 语汇 | 文件 |
|---|---|---|
| 年轮核（今天页） | SVG path 自生长 + 计数逐位弹入 + scroll 视差 | `components/panels/TodayNowPanel.tsx`（RingCore） |
| 页面标题 | 逐字 charReveal + 朱砂下划线 | `components/PageTransition.tsx` + `.pa-title` |
| tab 游标 | layoutId + spring 过冲 | `components/TabRail.tsx` |
| 时刻卡 | 盖章生长 + inkSpread 入场 | `components/ui.tsx`（SeedCard）+ `.firefly-seed` |
| 对话最新回答 | 逐字 spring | `components/ui.tsx`（TypewriterText） |
| 投喂区 | canvas 墨滴入水 | `components/InkDropCanvas.tsx` |
| 长页区块 | gsap ScrollTrigger 揭示 + 视差 | `components/ScrollReveal.tsx` |
| 关系图边线 | path 自生长 | `components/wiki-mycelium-graph.tsx` |
| 氛围层 | 摩尔纹 + 墨晕 + 等高线 | `components/AmbientField.tsx` + globals.css |

### 6.5 v3 → v4 变更理由

v3 合约规定「呼吸与烛火」：0.5~1.4s 长尾缓出、禁弹跳 spring、禁频闪。v4 全部推翻，
因为**用户已明确批准动效全面放开、重写动效合约**。技术动因有二：
① 亮色底上辉光与拖尾几乎不可见，v3 靠"光"制造生命感的手法失效，只能换用线条生长、
干涉纹与高饱和对比；② v3 的克制曲线让 5 目的地 × tab 的新信息架构显得迟钝——tab 切换
需要"断裂"感（snap + 方向性推移），入场需要"生长"感（overshoot + 快速交错）。
**唯一从 v3 原样保留的约束是 reduced-motion 完整降级与可见性铁律**——那是无障碍底线，不是风格选择。

## 7. 组件规范

- **按钮**：主 `.btn-lumen`（墨黑底，hover 转朱砂 + 上浮）/ 次 `.btn-ghost`（发丝边）/ 危险 `.btn-danger`（朱砂）；圆角 `--r-md`
- **输入框** `.input-glow`：瓷白底 + 聚焦墨黑描边 + 3px `--ink-06` 柔环
- **卡片** `.glass-card`：薄瓷底 + 发丝硬边 + 冷灰短促投影；hover 上浮 4px（overshoot）
- **时刻卡** `.firefly-seed`：朱砂左缘 3px + 底部极淡朱砂洇染呼吸（`--phase` 伪随机 3~8s）+ hover 盖章生长
- **标签/Chips**（`Tag`）：圆角 999，四色 alpha 底；文字一律中文
- **空状态** `.empty-seed`：一圈未长成的年轮（ring-form 扩散）+ 宋体低语
- **加载** `LoadingDots`：光点呼吸，不用转圈

## 8. 中文化合约（i18n）

- 数据层保留稳定英文键（wish/vulnerability/…），显示层经 `lib/labels.ts` 统一翻译：
  wish=心愿、vulnerability=脆弱、gratitude=感激、regret=遗憾、love=爱、courage=勇气；
  fact=事实、skill=技能、knowledge=知识；预设 温柔/理性/活泼/教练；
  主动性 安静/克制/均衡/主动/陪伴；回复长度 简短/适中/详尽；
  循环 daily=每日/weekly=每周/monthly=每月/yearly=每年/once=单次/weekdays=工作日；
  校验结果 events_kept=保留事件 等六键；后端字符串内嵌英文标签经 localizeDisplayText 兜底。
- 新增英文枚举必须同步补充映射；未映射键原样回退，构建后审计扫描页面确认零英文面向词。

## 9. 技术约束

- Next.js 15 App Router，静态导出（output=export, distDir=dist, basePath=/web），页面全部 `"use client"`；Tailwind 3.4 + 手写 globals.css
- 动效栈：framer-motion ^11（入场/转场编排）+ gsap ^3.12 ScrollTrigger（scroll-driven）+ CSS（常驻氛围）+ canvas 2D（墨滴）
- 动效预设单一真源 `lib/motion.ts`；token 单一真源 `app/globals.css :root`
- 数据层 `lib/api.ts`（类型化 fetch，Bearer token）；显示层 `lib/labels.ts`
- 质量门槛：`npm run build` 通过、`tsc --noEmit` 零错误、`npm test` 全过、
  token 审计零未定义引用（`--phase` 类带兜底值的局部变量可豁免）、
  grep 无硬编码 rgba/hex（globals.css 与 design-system 参考件除外）
