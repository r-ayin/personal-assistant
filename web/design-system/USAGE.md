# USAGE.md —— 年轮 · 墨迹设计系统 · Agent 构建指南

> 本文件是前端重构的执行合约。任何页面动工前，按顺序读完：
> 1. `app/globals.css` 的 `:root`（**token 单一真源**；`tokens.css` 只是它的参考镜像）
> 2. `DESIGN.md`（设计哲学、页面清单与「生长与断裂」动效合约）
> 3. `components.html`（组件规范样品，浏览器打开可见）
> 4. 本文件（页面 × 端点矩阵、交互细节、质量门槛）

## 铁律（违反即返工）

1. **一切面向用户的文字是中文**；数据层英文键经 `lib/labels.ts` 翻译，缺映射先补 labels.ts 再展示。
2. **色值只用 `app/globals.css :root` 的 CSS 变量**；禁止硬编码 hex/rgba（globals.css 与 design-system 参考件自身除外）。四色语义不可换：朱砂=唯一强调/证据，靛青=交互，石绿=成功，赭石=提醒。新颜色需求先加 token。
3. **动效合约 = DESIGN.md §6「生长与断裂」**：曲线/spring 预设单一真源 `lib/motion.ts`（CSS 侧 `--ease-out/overshoot/snap/ink` 一一对应）；允许 spring 过冲、快速交错、scroll-driven、SVG pathLength 自生长、canvas 墨滴、clip-path 揭示、3D rotateX。**reduced-motion 三层降级不可破**（MotionConfig / globals.css media 块 / 组件内 useReducedMotion 静态分支）。
4. **可见性铁律**：禁止 `initial={{opacity:0}}` 直接包住整页或大块容器，一切淡入走 `components/Reveal.tsx`；**同屏高频闪烁元素 ≤1 处**（频率 <3Hz、面积 <10% 屏，光敏性安全阈值见 DESIGN.md §6.2）。
5. 标题/引文/低语用衬线 `--font-serif`；正文黑体；时间戳与计数用 `--font-mono`。页面大标题实色墨 + 朱砂下划线，**禁 `background-clip:text` 渐变**（子元素 transform 打断裁剪会整段隐形）。
6. 空状态 = `empty-seed`（未长成的年轮 + 宋体低语）；加载 = 光点呼吸，**禁止转圈 spinner**。
7. 页面布局：5 目的地 × tab（单一真源 `lib/nav.ts`，tab 走 `?tab=`）；内容区 `max-width: 1360px`，section 间距 ≥64px，卡片薄瓷底 + 发丝硬边 + `--r-lg` 圆角。

## 技术约束

- Next.js 15 App Router，`output: "export"`，`distDir: "dist"`，`basePath: "/web"`；页面必须是 `"use client"`（静态导出无服务端运行时）。
- 数据层 `lib/api.ts`（类型化 fetch + Bearer token，token 存 sessionStorage `pa-api-token`）；不要绕过它直接 fetch。
- 动效栈：framer-motion（入场/转场编排）+ gsap ScrollTrigger（scroll-driven，见 `components/ScrollReveal.tsx`）+ CSS（常驻氛围）+ canvas 2D（墨滴，见 `components/InkDropCanvas.tsx`）。
- 构建校验：`npm run typecheck` 必须零错误；token 审计零未定义引用。

## 后端端点 × 页面接线矩阵

后端 = FastAPI（`personal_assistant/api.py`），Bearer 端点需 token。响应形状见 `lib/types.ts`。

| 目的地 × tab | 面板 | 情感表达 | 必接端点 |
|---|---|---|---|
| `/` = `/today/?tab=now` | 今天 · 此刻 | 年轮核自生长（环数=记忆年数）+ 计数逐位弹入 + 衬线低语 | `GET /status`（年轮核计数）、`GET /events`、`GET /reminders`、`GET /moments`（今日低语取一条未归还时刻） |
| `/today/?tab=schedule`（旧 `/calendar/`） | 日程 | 时间线靛青节点 | `GET /events`（按日分组时间线）、`GET /calendar?q=`（搜索） |
| `/today/?tab=reminders`（旧 `/reminders/`） | 提醒 | 赭石倒计时环 | `GET /reminders`、`POST /reminders/check`（手动检查） |
| `/today/?tab=recommend`（旧 `/recommend/`） | 推荐 | 推荐卡片瀑布 | `POST /recommend`（kind 选择：book/music/… 用中文标签） |
| `/chat/` | 对话 | 墨迹逐字生长，证据墨点浮层 | `POST /chat`、`GET /chat-log`、证据以墨点 tooltip 展示原文 |
| `/memory/?tab=moments`（旧 `/memories/`） | 时刻 | 朱砂印纸片墙 + 混合召回搜索 | `GET /moments`、`GET /memories`、`GET /memories/recall?q=` |
| `/memory/?tab=search` | 检索 | 诚实占位（等 P3 混合检索升级） | 待接 |
| `/memory/?tab=knowledge`（旧 `/wiki/`） | 知识 | 实体卡片墙 + 关系图（边线 pathLength 自生长） | `GET /wiki`（主题标签云）、`GET /wiki?q=`（搜索）、link_ids 渲染为 SVG 连线 |
| `/portrait/`（4 tab） | 画像 | 诚实占位（等后端 P2/P4/P5），不编造假画像 | `GET /profile`、`POST /profile/feedback` + `DELETE /profile/feedback/:id`（P5 后接） |
| `/system/?tab=ingest`（旧 `/inbox/`） | 摄入 | canvas 墨滴入水，薪入火 | `POST /inbox/upload`（拖拽+多文件）、`POST /ingest`（投喂后触发）、`GET /segments`（已吸收的回响列表） |
| `/system/?tab=persona`（旧 `/persona/`） | 助手人格 | 人格工作台 | `GET /assistant/personality`、**`PUT /assistant/personality`（含 409 版本冲突处理）**、**`POST /assistant/personality/preview`** |
| `/system/?tab=verify`（旧 `/verify/`） | 校验 | 石绿/朱砂粒子分拣 | `GET /verify`（六键计数，`lib/labels.ts` VERIFY_LABELS 翻译） |
| `/system/?tab=settings`（旧 `/settings/`） | 设置 | 极简：连接、LLM、数据管理 | `GET/POST /settings/llm`、`POST /distill`、`POST /ingest`、`POST /wiki/build`、**`GET /status`**、token 设置入口 |
| 全局 | 壳层 | 左侧墨线导轨 + 底部墨痕呼吸条 | `StatusStrip` 接 `GET /status`（记忆数/事件数/提醒数），60s 轮询 |

## 页面交互细节（现有实现普遍缺失的部分）

### `/` 今天
- 心灯中央数字 = `status.memories`（wiki 页数 + 时刻数），等宽字体，与心灯同呼吸。
- 「今日低语」：从 `GET /moments` 取一条未归还时刻，衬线引文 + 标签 chips（bloom 色）。
- 日程卡（lumen）与提醒卡（ember）双栏；条目入场 x-20 交错 60ms。
- 空态文案已有约定："今天还没有日程，炉火正温" / "暂无提醒，一切安好"。

### `/chat/` 对话
- 消息流：用户靠右（暖纸气泡），助手靠左（玫瑰/金发丝左边线 + 衬线）。助手最新一条逐字生长（TypewriterText，reduced-motion 时直接全显）。
- 证据 = 余烬粒子（小金点），悬浮 tooltip 展示证据原文（现在只有 title，要做成像样的浮层卡）。
- 发送中：呼吸光点，禁用输入框。
- 失败文案："（炉火熄了——这条没送出去，稍后再试）"。

### `/memories/` 记忆
- 顶部召回搜索框：`GET /memories/recall?q=&k=8`，结果展示 content + kind chip + score 微光条。
- 时刻种子墙：grid 卡片，每张卡相位呼吸（`animation-duration` 按 id 取 3~8s 伪随机），引文衬线、叙事正文、标签 chips、对话对象（counterpart，中文 chat_kind：单聊/群聊/公众号/企业号）。
- 记忆列表（知识层）：kind chip（fact=事实 等，见 MEMORY_KIND_LABELS）+ content + 时间。

### `/inbox/` 投喂
- 大拖拽区：文件落入时涟漪扩散（ripple-ring），支持 .txt/.srt 多文件。
- 上传成功后提示"薪已入火"，并自动 `POST /ingest`。
- 下方「已吸收的回响」：`GET /segments` 列表（时间、说话人、文本摘要），倒序。

### `/wiki/` 知识
- 无搜索词：主题标签云（`/wiki` 返回 topics），标签大小可按页数分级（若只有名称则统一中等）。
- 有搜索词：实体卡片墙。每张卡：标题（衬线）、body 摘要、标签 chips。
- **菌丝关系图**：选中一张卡后，其 link_ids 指向的页以暖金细线相连（SVG 曲线 + 节点脉冲，复用 globals.css 的 mycelium 视觉语言）。数据不足时优雅降级为标签云提示。

### `/verify/` 校验
- 六键计数分拣成两列：保留（moss）/ 删除（bloom），数字等宽。
- 每个数字是一颗"分拣粒子"：入场时从上飘落定位。

### `/persona/` 档案
- 上半：助手人格卡——预设选择（温柔/理性/活泼/教练/自定义 chips）、滑杆（直接度/幽默度 1-5）、下拉（主动性/回复长度，中文枚举）、禁忌词 chips 输入、自定义指令 textarea。
- 「试听」按钮 → `POST /assistant/personality/preview`，三句预览（对话/提醒/感知）衬线展示。
- 「保存」→ `PUT /assistant/personality`（带 expected_version；409 时提示"档案在别处被改写"，重新拉取）。
- 下半：用户画像——`GET /profile` 的 inferred/effective 九维（个性/价值观/目标/习惯/技能/知识/思维模式/偏好/情感基线），每维可「补充/修正」→ `POST /profile/feedback`；已有反馈列表可删除（`DELETE`）。
- 所有枚举过 `lib/labels.ts`。

### `/settings/` 设置
- 连接卡：API token 输入（写入 sessionStorage）、后端健康状态（`GET /health` + `GET /status` 六格计数）。
- LLM 卡：backend 下拉（中文标签：stub=占位/ollama=本地 Ollama/openai_compat=OpenAI 兼容/anthropic_proxy=Anthropic 代理/deepseek=DeepSeek/deepseek_anthropic=DeepSeek(Anthropic 协议)/glm_anthropic=智谱(Anthropic 协议)）、model/base_url/api_key/max_tokens 输入，保存后展示 effective 配置。
- 数据管理卡：蒸馏（distill）/ 摄入（ingest）/ 重建知识（wiki/build）三个操作，按钮 + 结果低语。

### `/calendar/` `/reminders/`
- 日历：按日分组的时间线，每日一个节点光点（lumen），事件卡挂在线侧；顶部搜索框走 `/calendar?q=`。
- 提醒：每条一个倒计时环（`countdown-ring`，剩余比例=弧长），循环周期 chip（RECURRING_LABELS），「检查到期」按钮走 `/reminders/check`。

## 共享地基（重构第一波已完成，页面 agent 只消费不修改）

- `app/globals.css`：全部氛围层（ring-field 摩尔纹 / ink-wash 墨晕 / contour-field 等高线 / grain 纸颗粒）+ 语义类（glass-card/btn-*/input-glow/firefly-seed/empty-seed/pa-title…）。
- `components/ui.tsx`：GlassCard、Tag、SectionHeader、LoadingDots、TypewriterText、CountdownRing、SeedCard、WhisperLine、MonoCount 等；`components/EmptyState.tsx`。
- `components/Sidebar.tsx` / `PageTransition.tsx` / `StatusStrip.tsx` / `AmbientField.tsx` / `DestinationPage.tsx` / `TabRail.tsx` / `Reveal.tsx` / `LegacyRedirect.tsx`。
- `lib/motion.ts`（动效预设单一真源）/ `lib/nav.ts`（信息架构单一真源）/ `lib/useTab.ts`。
- `lib/api.ts` / `lib/types.ts` / `lib/labels.ts`。

页面 agent 的文件所有权：只能创建/修改 `app/<你的页面>/` 与 `components/<页面>-*/`（如需页面私有组件）。**共享文件若觉得缺东西，在自己页面内组合实现，并在交付报告中列出建议**——不许直接改共享文件。
