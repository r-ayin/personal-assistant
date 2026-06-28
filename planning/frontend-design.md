# 全自动个人助手 — 前端详细设计文档（完整版）

> v0.4 对齐 · 2026-06-28 · 覆盖后端已实现的全部功能 + 待补 LLM 配置面板
> 用途：供在外部独立实现前端后回接后端 `api.py`（FastAPI，19 端点已存在 + 3 个待补端点见 §3）。

## 1. 概述

**定位**：大脑（FastAPI + SQLite/DuckDB + 可插拔 LLM）跑本地或云；前端是**控制端 + 对话端**，仅经 REST 消费后端。两套前端：
- **Web 控制面板**：Next.js(App Router) + TS + Tailwind + shadcn/ui —— 全功能管理与可视化。
- **Android App**：Kotlin + Jetpack Compose —— 随身对话、被动录音/上传转录、提醒通知。

**硬约束（贯穿前端）**：
1. **本地优先 / 隐私**：API key 永不出现在前端代码或 localStorage；原始数据不前端持久化。
2. **反幻觉可见**：每条数据尽量带溯源 chip；时间戳显式标 `time_kind`；LLM 生成内容与确定性解析结果视觉区分。
3. **诚实配置**：思考程度档位映射各 provider 真实 API 字段（已查官方文档，见 §6.11 与附录 A），不前端捏造 budget 数字。

**覆盖功能清单**（v0.1–v0.4 全部已设计功能）：
1. 被动接入与转录流（ingest/transcript/speaker） 2. 记忆库（memories+检索+溯源） 3. 数字分身蒸馏（distill/persona_versions） 4. 对话（chat+chat_log+真实时间戳） 5. 主动干预（proactive/interventions） 6. 自动日历（calendar/events/temporal） 7. 定时提醒（reminders/scheduler） 8. 反幻觉体检（verify） 9. 推荐引擎（recommend/联网搜索） 10. 个人 wiki（wiki_pages） 11. 设置：LLM 可插拔配置面板（model/上下文/max_tokens/思考程度/api/key）

## 2. 整体架构

```
[设备转录 .txt/.srt] ──┐
[Android 录音/上传] ───┤──> inbox 目录 ──> ingest ──> segments ──> memory/distill/...
[Web 手动触发] ────────┘                                          │
                                                                  ▼
                              SQLite(segments/memories/events/reminders/chat_log/
                                      wiki_pages/persona_versions/interventions/speakers)
                                                  │  FastAPI (api.py)
                        ┌─────────────────────────┴──────────────────────┐
                        ▼                                                ▼
                Web 控制面板 (Next.js)                           Android App (Compose)
```
- 前端只持 `BASE_URL`(+ 可选本地鉴权 token)。
- Android "24h 被动听" = 前台服务持续采音→分段→(端/服务端)转写→投递 inbox（对齐决策 3：设备自带转录，inbox watch-dir）。

## 3. 后端 API 契约（前端依赖，实测自 `api.py`）

### 已存在端点（19）

| 方法 | 路径 | 用途 | 关键字段 |
|---|---|---|---|
| GET | `/health` | 健康+后端模式 | `llm`/`asr`/`embedder`/`speaker` |
| POST | `/ingest` | 扫 inbox 灌转录 | `scan_inbox()` 结果 |
| GET | `/segments` | 段落流(限100) | `id,source_file,start_sec,end_sec,text,speaker,language,created_at,processed,time_kind` |
| GET | `/memories` | 记忆(末50) | `id,segment_id,kind,content,evidence,created_at,processed` |
| GET | `/profile` | 当前人格 | `version,change_summary,profile{8维度}` |
| POST | `/chat` | 对话 | 入`{message}` 返`{reply}` |
| GET | `/chat-log` | 对话历史 | `logs[]{role,content,created_at}` |
| POST | `/verify` | 反幻觉体检 | `rep + assertion` |
| POST | `/distill` | 触发蒸馏 | 蒸馏结果 |
| POST | `/triggers` | 触发主动干预 | `{fired:[...]}` |
| GET | `/calendar?q=` | 日历检索("明天/上周") | `{count,events[]}` |
| GET | `/events` | 全部事件 | `{events[]}` |
| GET | `/reminders` | 提醒列表 | `{reminders[]}` |
| POST | `/reminders/check` | 到点检查并触发 | `{fired:...}` |
| GET | `/speakers` | 说话人注册表 | `{speakers[]{name,label,note,created_at}}` |
| GET | `/recommend?kind=&q=` | 推荐 | `{count,recommendations[]{item,reason,based_on}}` |
| GET | `/wiki?tag=&q=` | wiki 检索 | `{pages[]{id,title,body,tags,source_ids,link_ids,created_at}}` |
| POST | `/wiki/build` | wiki 增量构建 | `{built:...}` |

### 前端需后端补的端点（3，落地中）

| 方法 | 路径 | 用途 | 入/出 |
|---|---|---|---|
| GET | `/settings/llm` | 返回生效 LLM 配置（key 掩码）+ native thinking 字段预览 | 出：`{backend,model,base_url,api_key_masked,context_window,max_tokens,thinking_effort,thinking_format,native_preview}` |
| POST | `/settings/llm` | 写运行态覆盖 | 入：`{model?,context_window?,max_tokens?,thinking_effort?,base_url?,api_key?,backend?}` |
| POST | `/inbox/upload` | 上传转录文件到 inbox（原始 body + `?filename=` 查询参数，免 multipart 依赖） | 入：body=文件内容、`filename` 查询；出：`{saved,bytes,ingest_hint}` |

> 在端点未上线前，前端设置面板可先用 Mock 数据开发；上线后切换即可。

## 4. 设计系统

- **色彩**：暗底 `#0E1116`；主色靛蓝 `#5B8DEF`；溯源绿 `#3FB68B`；反幻觉金 `#E0A458`；警示红 `#E0584F`。
- **排版**：正文 14/16，标题 20/24；中文优先 PingFang/思源黑体 fallback。
- **通用组件**：
  - `<TimeChip>`：`created_at` + `time_kind` 角标（`received`/`occurred`），悬停提示"记录时间≠发生时间"。
  - `<SourceChip>`：`segment:<id>` / `result:<N>` / `persona:<维度>` / `memory:<id>`，可点跳源。
  - `<VerifyBadge>`：✅passed / ❌failed（来自 `/verify`）。
  - `<Timeline>`：segments/chat_log/reminders 通用。
  - `<PersonaRadar>`：八维雷达。
  - `<MemoryCard>`：kind 标签 + evidence 溯源。
  - `<DeterministicBadge>` 🔒：确定性规则结果（`when_dt`）专用，区别于 LLM 生成。

## 5. Web 路由

```
/dashboard  仪表盘  /inbox  接入转录流  /memories  记忆库  /persona  数字分身
/calendar  日历  /reminders  提醒  /chat  对话  /recommend  推荐
/wiki  个人知识库  /verify  反幻觉体检  /settings  设置(LLM 配置)
```

## 6. 各功能模块详细设计

> 格式：**故事 / 布局 / 组件树 / 数据绑定 / 交互 / 反幻觉体现**

### 6.1 被动接入与转录流
- 顶部"立即扫描 inbox"（`POST /ingest`）；`<Timeline>` 渲染 `/segments`，按 `speaker` 染色（A=user 蓝、B=他人灰，来自 TextDiarizer）。
- 组件树：`InboxPage > IngestButton + SegmentTimeline > SegmentItem > SpeakerBadge·TimeChip·text`。
- 绑定：`GET /segments`；`speaker.label` 来自 `/speakers`。
- 交互：点段→展开其关联 memories/events/reminders（按 `segment_id` 反查）。
- 反幻觉：`time_kind='received'` 必须可见并悬停解释。
- Android：录音/选文件→`POST /inbox/upload`。

### 6.2 记忆库
- 搜索框（语义检索）+ kind 过滤（event/preference/intention/emotion）+ `<MemoryCard>` 列表。
- 绑定：`GET /memories`；`evidence` → `<SourceChip segment:id>` 跳 `/inbox` 高亮。
- 反幻觉：evidence 必落地；无 evidence 的卡显示警告角标。

### 6.3 数字分身
- `<PersonaRadar>` 八维 + 各维度文本 + 版本下拉（`persona_versions`）+ "重新蒸馏"（`POST /distill`）。
- 绑定：`GET /profile`。
- 反幻觉：维度内容旁附"基于 N 条记忆"（`profile.knowledge[].evidence`）。

### 6.4 对话
- 气泡列表（`/chat-log`）+ 输入框（`POST /chat`）。
- 绑定：`GET /chat-log`（含 `created_at`）；发送后追加 `{reply}`。
- 反幻觉：每气泡 `<TimeChip>` 真实系统时间戳；助手回复若引记忆附 `<SourceChip>`（待后端 reply 携带时启用）。

### 6.5 主动干预
- `/dashboard` 顶部"今日干预"卡 + `/reminders` 同区；`POST /triggers` 手动触发。
- 绑定：`interventions`（trigger_kind/evidence/message）。
- 反幻觉：每条显示 `evidence` 溯源（哪些记忆触发）。

### 6.6 自动日历
- 搜索框（`GET /calendar?q=明天`）+ 事件列表（title/when_dt/who/where）。
- 绑定：events 表；`when_dt` 由 `temporal.resolve` 确定性解析。
- 反幻觉：每事件并排 `when_raw`（源表达）+ `when_dt`（确定性解析）+ `<SourceChip segment>`；`when_dt` 挂 🔒确定性徽章，明确非 LLM 编造。

### 6.7 定时提醒
- 列表（what/when_dt/recurring/fired）+ "检查到点"（`POST /reminders/check`）。
- 绑定：reminders 表；循环类显示 recurring 标签。
- 交互：Android 端 `fired` 走本地通知通道；Web 仅展示。
- 反幻觉：同日历，`when_raw`+`when_dt`+源段并排。

### 6.8 反幻觉体检
- `POST /verify` 报告：逐事件 `when_dt 重解一致性` + `when_raw/内容溯源源转录` + 不落地项；顶 `<VerifyBadge>`。
- 绑定：`verify.run_all()` + `assertion`。
- 反幻觉：本页即反幻觉显式呈现；不落地项一键跳源核查。

### 6.9 推荐引擎
- kind 切换（book/movie/action）+ 可选 query + 推荐卡（item/reason/based_on）。
- 绑定：`GET /recommend`；`based_on` → `<SourceChip persona:维度>` 或 `result:N`。
- 反幻觉：`item` 须落地搜索结果（"来自联网搜索"标记）；`based_on` 非空维度才显示；无结果→空状态而非假数据。

### 6.10 个人 wiki
- 左标签云 + 右页面（title/body/source_ids/links）+ "增量构建"（`POST /wiki/build`）。
- 绑定：`GET /wiki?tag=&q=`；`source_ids` → 可点 `<SourceChip memory:id>`；`link_ids` → 页内互链。
- 反幻觉：每页 body 旁"落地 N 条源记忆"；source_ids 必须真实记忆 id（点开跳 `/memories` 命中）。

### 6.11 设置：LLM 可插拔配置面板 ★
**故事**：前端直接查看/设置生效 LLM 配置——**模型、上下文窗口、输出 max_tokens、思考程度(off/低/中/高)、API(base_url)、key**，全局覆盖当前激活后端，对齐 `cli llm`。

**布局**（三区）：
1. **当前生效**（只读卡，`GET /settings/llm`）：active backend、model、base_url、key 掩码（`前4…后4`）、context_window、max_tokens、thinking_effort 档位、思考原生字段预览（`native_preview`）。
2. **全局覆盖**（表单，`POST /settings/llm`）：model / context_window(token) / max_tokens(token) / thinking_effort(select: off·低·中·高) / base_url / api_key(password)。
3. **后端切换**：stub / anthropic_proxy / ollama / openai_compat / glm_anthropic 单选（= `PA_LLM_BACKEND` 语义）。

**思考程度档位→provider 原生字段映射**（前端只发档位枚举，映射在后端 `llm.py`；下表已查官方文档，非捏造）：

| 档位 | GLM(openai_compat) | GLM(anthropic 端点) | OpenAI o 系 | Qwen3(openai_compat) | Anthropic Claude |
|---|---|---|---|---|---|
| off | `thinking:{type:"disabled"}` | 省略 | 省略 | `enable_thinking:false` | 省略 |
| 低 | `thinking:{type:"enabled"}`* | `thinking:{type:"enabled",budget_tokens:4096}` | `reasoning_effort:"low"` | `enable_thinking:true,thinking_budget:4096` | `thinking:{type:"enabled",budget_tokens:4096}` |
| 中 | `thinking:{type:"enabled"}`* | `...budget_tokens:12288` | `reasoning_effort:"medium"` | `...thinking_budget:12288` | `...budget_tokens:12288` |
| 高 | `thinking:{type:"enabled"}`* | `...budget_tokens:24576` | `reasoning_effort:"high"` | `...thinking_budget:24576` | `...budget_tokens:24576` |

\* **关键诚实约束**：GLM 的 OpenAI 兼容端点(`open.bigmodel.cn/api/paas/v4`)只支持 `thinking.type:"enabled"|"disabled"` **开/关两档，无 budget 旋钮**；故低/中/高三档在 GLM openai_compat 下**塌缩为"开"**。要区分须走 GLM 的 **Anthropic 兼容端点**(`open.bigmodel.cn/api/anthropic`，支持 `thinking.budget_tokens`，min 1024 且 < max_tokens)——即后端的 `glm_anthropic` 后端。GLM 默认思考为开，off 须显式 disable。

**前端呈现**：思考程度选择器旁附动态说明文案——
- 选 GLM(openai_compat)+低/中/高 → 提示"GLM 兼容端点仅支持开/关，三档等效为开；要分档请切 glm_anthropic 后端"。
- 选 glm_anthropic / Anthropic → "按 budget_tokens 区分（min 1024, < max_tokens）"。
- 选 OpenAI → "原生 low/medium/high（o 系；GPT-5 另有 none/minimal/xhigh）"。
- 选 Qwen → "enable_thinking + thinking_budget"。

**安全**：key `type=password`，永不明文回显；写入走本地鉴权。
**对齐**：与 `cli llm` 同一配置源（运行态覆盖层 + `config/default.json` + env），保证"前端改=CLI 看=生效"。

> 真实参数依据见**附录 A**（含官方文档 URL 与各型号上下文/输出上限）。

## 7. Android App（Kotlin + Compose）

**屏幕**（Web 子集）：`DashboardScreen`、`ChatScreen`（主入口常驻）、`RemindersScreen`、`CalendarScreen`、`PersonaScreen`、`MemoriesScreen`、`SettingsScreen`。底部 Nav：对话/日历/提醒/分身/设置。

**端能力**：
- 被动录音：前台服务持续麦克采音→VAD 分段→端/服务端转写→投递 inbox。
- 文件上传：选 `.txt/.srt` → `POST /inbox/upload`。
- 提醒通知：通知通道，`/reminders/check` 命中 `fired` 时本地通知→点击跳对话。
- 离线缓存：对话历史与未上传转录本地缓存，网络恢复回放。
- 设置：含 LLM 配置表单（同 §6.11，移动端友好）。

## 8. 前端数据模型（对齐 storage 表）

```ts
type TimeKind='received'|'occurred';
interface Segment{id:string;source_file:string;start_sec:number;end_sec:number;
  text:string;speaker:string;language:string;created_at:string;processed:number;time_kind:TimeKind}
interface Memory{id:string;segment_id:string;kind:string;content:string;
  evidence:string;created_at:string;processed:number}
interface Event{id:string;title:string;when_dt:string;when_raw:string;
  who:string;where:string;source_segment:string;created_at:string}
interface Reminder{id:string;what:string;when_dt:string;when_raw:string;
  recurring:string;source_segment:string;fired:number;created_at:string}
interface ChatLog{id:number;role:string;content:string;created_at:string}
interface WikiPage{id:string;title:string;body:string;tags:string;
  source_ids:string;link_ids:string;created_at:string}
interface Speaker{name:string;label:string;note:string;created_at:string}
interface Persona{version:number;change_summary:string;profile:Profile}
interface Intervention{id:string;created_at:string;trigger_kind:string;
  evidence:string;message:string;delivered:number}
```

## 9. 状态管理与数据获取

- Web：React Query。轮询：`/reminders/check` 60s、`/triggers` 5min、`/segments` 30s、`/health` 60s；余按需。
- 乐观更新：发 chat 立即出气泡，`/chat` 返回后替换 reply。
- 缓存：key/敏感配置不进 localStorage；对话历史可缓存。

## 10. 反幻觉与真实时间呈现规范（横切）

1. 时间：凡 `created_at` 走 `<TimeChip>`，角标显式 `time_kind`；`received` 悬停"系统记录时间，非真实发生时间"。
2. 溯源：凡 `evidence`/`source_segment`/`source_ids`/`based_on` 走 `<SourceChip>`，可点跳源。
3. 确定性 vs 生成：`when_dt` 挂 🔒确定性徽章；LLM 生成（回复/推荐/reason）不挂。
4. 体检可见：`/verify` 徽章入 `/dashboard` 顶栏，failed 红色高亮。

## 11. 隐私与安全

- 本地优先：除上传转录/对话请求不外发；前端不存原始数据。
- key：`password` + 掩码回显 + 仅经 `POST /settings/llm` 写后端。
- 鉴权：本地 token（局域可选）；CORS 限本地网段。
- 录音权限：Android 运行时权限 + 前台服务通知（合规可见）。

## 12. 技术栈与工程

- Web：Next.js(App Router)+TS+Tailwind+shadcn/ui+React Query；Mock 模式连 `stub` 后端开发。
- Android：Kotlin+Compose+Hilt+Retrofit+DataStore。
- Web 目录：`app/(dash)/{inbox,memories,persona,calendar,reminders,chat,recommend,wiki,verify,settings}/page.tsx`；`components/{TimeChip,SourceChip,VerifyBadge,PersonaRadar,MemoryCard,Timeline,DeterministicBadge}.tsx`；`lib/{api.ts,types.ts}`。

## 13. 实施路线（对齐 PRD deferred）

- **Phase A — Web 只读+对话**：§6.1/6.2/6.3/6.4/6.8 只读 + `/dashboard`；连 stub 跑通。
- **Phase B — 写操作+推荐/wiki/设置**：§6.5–6.11 含 `/ingest`、`/distill`、`/wiki/build`、`/settings/llm`、`/inbox/upload`。
- **Phase C — Android**：对话+提醒+被动录音+设置。

## 14. 验收

- 连 stub：全页面 mock 渲染通过，`<VerifyBadge>` passed。
- 连真 GLM（`PA_LLM_BACKEND=openai_compat`）：对话/推荐/wiki 真实输出 + 溯源 chip 全可跳源。
- 反幻觉：`/verify` failed 时红色高亮且不落地项可跳源核查。
- 设置：前端改 thinking_effort=高 → `cli llm` 一致 → 后端请求体含对应 provider 原生思考字段（GLM openai_compat 下三档塌缩为开，前端文案已提示；glm_anthropic 下按 budget 分档）。

---

## 附录 A：四家 Provider 思考参数真实依据（查官方文档，非捏造）

| Provider | 思考字段 | 值结构 | 档位/范围 | 上下文窗口 | 最大输出 | 关键约束 |
|---|---|---|---|---|---|---|
| **GLM (智谱/BigModel)** | OpenAI 兼容：`thinking.type`（顶层）；Anthropic 兼容：`thinking` 对象 | openai: `{type:"enabled"\|"disabled"}`；anthropic: `{type:"enabled",budget_tokens:N}` | openai 仅开/关无 budget；anthropic budget min 1024, < max_tokens | GLM-4.6: 200K；GLM-5.2: 1M | GLM-4.6: 128K；GLM-5.2: 128K | openai_compat 端点(`/api/paas/v4`)无 budget 旋钮；要 budget 走 anthropic 端点(`/api/anthropic`)；默认思考开，off 须显式 disable；GLM-4.6/4.7 在阿里云百炼 2026-07-09 下架，bigmodel.cn 仍在 |
| **OpenAI o 系** | Chat: `reasoning_effort`(顶层字符串)；Responses: `reasoning.effort` | `"low"\|"medium"\|"high"` | o 系仅 low/medium/high（默认 medium；GPT-5 才加 none/minimal/xhigh，o 系不支持） | o1/o3/o4-mini: 200K；o1-mini: 128K | o 系: 100K；o1-mini: 65K | 推理模型须用 `max_completion_tokens` 非 `max_tokens`；无 budget_tokens；推理 token 计入输出计费 |
| **Qwen3 (百炼)** | OpenAI 兼容：`enable_thinking` + `thinking_budget`（extra_body；urllib 顶层） | bool + int | enable_thinking true/false；thinking_budget 整数(范围随型号，0=自适应) | 随型号 | 随型号 | thinking_budget 仅 enable_thinking=true 生效；流式含 `reasoning_content`；具体 budget 上限以官方文档为准 |
| **Anthropic Claude** | `thinking`(顶层对象) | `{type:"enabled",budget_tokens:N}` 或 `{type:"adaptive"}` | manual: budget min 1024, < max_tokens；adaptive: Opus4.6+/Sonnet4.6+ | Opus4.8/Sonnet4.6: 1M；Haiku4.5: 200K | Opus4.8: 128K；Sonnet4.6: 64K | budget_tokens 在 Opus4.7+ 已弃用→改 adaptive；max_tokens 须 > budget_tokens；streaming 要求 max_tokens>21333 |

**官方文档来源**：
- 智谱 GLM：docs.bigmodel.cn / open.bigmodel.cn/dev/api / docs.z.ai
- OpenAI：platform.openai.com/docs/guides/reasoning、/docs/api-reference/chat/create
- Qwen3：help.aliyun.com/zh/model-studio（qwen-api-via-openai-chat-completions、newly-released-models）
- Anthropic：docs.anthropic.com/en/docs/build-with-claude/extended-thinking、platform.claude.com/docs/en/build-with-claude/effort

> 注：附录 A 的具体 token 上限（尤其 Qwen3 thinking_budget、各型号上下文）随官方迭代变动，实现时以实时官方文档为准；字段名与结构以上表为准。
