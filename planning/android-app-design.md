# 全自动个人助手 — Android App 设计方案（完整版）

> 版本 v0.6-design · 2026-06-29 · 对齐后端 v0.5（FastAPI 21 端点 + SQLite/DuckDB + 可插拔 LLM）
> 状态：**设计稿**（未实现）。放置路径：`personal-assistant/planning/android-app-design.md`
> 配套：`planning/frontend-design.md`（Web 端 14 节）、`planning/prd-llm-config.md`、`web/`（已落地 Web 控制面板）
>
> **⚠️ 定位修正（2026-06-29 用户澄清，实现以此为准）**：app = **纯前端显示 + 对话**。数据、ASR/转录、记忆/蒸馏/解析全部跑在电脑/服务器大脑；**录音/转录由硬件设备直发电脑，app 不参与**。故本稿 §3.2 InboxPage（上传转录）与 §4 前台录音服务 ListeningService **已从实现中移除**；app 实际屏为 10 个（chat/memory/persona/calendar/reminder/verify/recommend/wiki/settings/dashboard）。下方原文保留作历史设计记录。

---

## 0. 概述

### 0.1 定位

大脑（FastAPI + SQLite/DuckDB + 可插拔 LLM）跑本地电脑或云服务器；**Android App 是随身端**，承担三类角色：

1. **对话端**：与数字分身对话（`POST /chat` + `GET /chat-log`）。
2. **被动录音 / 上传转录端**：24h 前台服务采音 → 分段 → 转写 → 投递 inbox（`POST /inbox/upload` + `POST /ingest`）。
3. **提醒 / 主动干预通知端**：到点提醒与主动建议以系统通知呈现（`POST /reminders/check`、`POST /triggers`）。

App **仅经 REST 消费后端**，本身不跑 LLM、不存原始大脑数据。Web 控制面板（`web/`，已落地）是全功能管理端；App 是高频随身端，两者共用同一套后端契约与设计语义。

### 0.2 三条硬约束（贯穿全文，不得违反）

1. **本地优先 / 隐私**：API key 永不出现在 App 代码或持久化存储；原始音频默认不前端持久化；App 本地仅持 `BASE_URL` + 可选鉴权 token（加密存）。
2. **反幻觉可见**：每条数据尽量带溯源 chip；时间戳显式标 `time_kind`（`received` 记录时间 / `occurred` 发生时间）；LLM 生成内容与确定性解析结果视觉区分。
3. **诚实配置**：思考程度档位（off·低·中·高）映射各 provider 真实 API 字段，App **不前端捏造 budget 数字**，而是展示后端 `native_preview`。

### 0.3 后端 REST 契约（实测自 `api.py`，设计落于此）

共 21 端点。逐屏映射见 §3 与 §6 总表。关键：`/inbox/upload` 是**原始 body + `?filename=` 查询参数，免 multipart**（dev 盒装不了 python-multipart）；`/settings/llm` 的 key **掩码不回显**；`/profile` 后端 shape 是**扁平 8 维文本**（前端若带 score 须对齐策略，见 §3.4）。

---

## 一、整体架构与技术栈

### 1.1 技术栈选型

| 层 | 选型 | 理由 |
|---|---|---|
| 语言/UI | **Kotlin + Jetpack Compose + Material 3** | 现代 Android 唯一推荐路径；Compose 与 M3 是官方主流（对齐用户资源文档"现在主流写法"） |
| 网络 | **Retrofit2 + OkHttp + kotlinx.serialization** | 稳定、契约友好；`/inbox/upload` 用 `@Streaming` + 原始 `RequestBody` 发 body，`@Query("filename")` 传名，天然适配免 multipart 契约 |
| 本地缓存/离线 | **Room** + **DataStore (Preferences, Encrypted)** | Room 缓存 segments/memories/events/reminders/chat_log 以支持离线浏览；EncryptedDataStore 存 BASE_URL/token |
| DI | **Hilt** | 官方、与 ViewModel/Compose 集成成熟 |
| 异步 | **Kotlin Coroutines + Flow** | 单向数据流基础；`/chat` 若后端未来加流式可平滑接 SSE |
| 通知 | **NotificationManager + Channels** | listening / reminder / intervention / chat 四通道 |
| 调度 | **WorkManager** + **AlarmManager** | WorkManager：ingest 周期、reminders/check 周期、上传 retry；AlarmManager：精确到点提醒兜底 |
| 设计→代码 | **Relay for Figma / Figma-to-Compose** | 设计师 Figma + M3 Design Kit，Relay 产出 Compose 代码 + 主题资源 |
| 动画 | **lottie-android** | 蒸馏生成、空状态、listening 波形等 AE 动画 |
| 图表 | **Compose 自绘（Canvas）为主，MPAndroidChart 仅 legacy** | 项目图表需求轻（persona 雷达/时间线），Compose Canvas 足够且避免 Views 互操作；MPAndroidChart 是 Views 体系，仅在有重度图表需求时引入（见 §2.3） |

> **库取舍说明**：`material-components-android`（Views 体系）与 `SmartRefreshLayout`（Views 体系）**不引入新代码**——纯 Compose 项目用 M3 组件 + `pullToRefresh` Modifier 即可，避免 Views 互操作复杂度。`awesome-android-ui` 作为**灵感清单**参考交互模式，不直接依赖。这与用户资源文档"Jetpack Compose 生态 = 现在主流写法"一致。

### 1.2 分层架构（MVI 单向数据流）

```
┌───────────────────────────────────────────────┐
│  Compose UI (Screen)                          │  纯函数，渲染 UiState，发 Intent
│  └─ 通用组件: TimeChip/SourceChip/VerifyBadge │
├───────────────────────────────────────────────┤
│  ViewModel  ←  StateFlow<UiState>             │  Intent → reduce → UiState
├───────────────────────────────────────────────┤
│  Repository                                   │  聚合 Remote + Local，离线降级
├──────────────────────┬────────────────────────┤
│ RemoteDataSource     │ LocalDataSource        │
│ (Retrofit PaApi)     │ (Room DAO + DataStore) │
└──────────────────────┴────────────────────────┘
                        │
                        ▼  HTTPS (+ 可选鉴权)
                FastAPI 大脑 (本地电脑/云)
```

- **UiState**：每屏一个 `data class …UiState(loadState, data, error)`，`loadState ∈ Idle/Loading/Success/Error/Empty`。
- **Intent**：用户动作封装为 sealed class，`ViewModel.handle(intent)` 内 reduce。
- **字段透传**：DTO 必须保留 `evidence / source_ids / time_kind / native_preview / api_key_masked / version / change_summary / when_raw / when_dt` 等字段一路到 UiState——这是反幻觉可见性的数据层前提（见 §5.4）。

### 1.3 配置与隐私落地

- `BASE_URL` + 可选 `AUTH_TOKEN` 存 **EncryptedDataStore**（Android Keystore 加密），永不写死在代码。
- **API key 不落 App**：LLM key 由后端持有；App 的设置面板（§3.11）调用 `POST /settings/llm` 写运行态覆盖时，key 字段直接发往后端、后端不回显（`GET /settings/llm` 只回 `api_key_masked`）。App 本地**绝不缓存明文 key**。
- **后端发现**：手填 `BASE_URL` 为主路径；可选局域网 mDNS（`NSD`）发现本地大脑服务作为加分项。离线时 App 读 Room 缓存降级展示（只读）。

### 1.4 Gradle 模块划分

```
:app               // 入口、Application、导航图、通知
:core:ui           // 设计系统(Theme/Color/Type) + 通用组件(TimeChip/SourceChip/VerifyBadge/Timeline)
:core:data         // Retrofit PaApi + DTO + Room + DataStore + Repository 实现
:core:common       // Result/LoadState/时间工具/反幻觉字段工具
:feature:chat      // 对话屏
:feature:inbox     // 录音/上传转录屏 + 前台录音服务
:feature:memory    // segments/memories
:feature:persona   // 蒸馏/persona
:feature:calendar  // 日历/事件
:feature:reminder  // 提醒
:feature:verify    // 反幻觉体检
:feature:recommend // 推荐
:feature:wiki      // 个人 wiki
:feature:settings  // LLM 配置面板
```

### 1.5 SDK 与权限策略

- **minSdk = 29（Android 10）**，**targetSdk = 34+**。前台服务 + 通知 + 录音权限的现行政策要求：Android 14+ 前台服务须声明 `foregroundServiceType="microphone"`，运行时须先获 `RECORD_AUDIO` 再 `startForeground`；`POST_NOTIFICATIONS`（Android 13+）运行时授权。
- 权限清单：`RECORD_AUDIO`、`POST_NOTIFICATIONS`、`FOREGROUND_SERVICE`、`FOREGROUND_SERVICE_MICROPHONE`（Android 14+）、`INTERNET`、`ACCESS_NETWORK_STATE`、`RECEIVE_BOOT_COMPLETED`（开机重启 listening 服务可选）、`SCHEDULE_EXACT_ALARM`（精确提醒，Android 12+ 需用户授权）。

---

## 二、设计系统与 UI 库选型

### 2.1 色彩：Web 语义 token → Material 3 ColorScheme

复用 `frontend-design.md §4` 的语义色，映射到 M3 角色（暗色为主）：

| 语义 | Web 值 | M3 角色（暗色） | 说明 |
|---|---|---|---|
| 暗底 | `#0E1116` | `background` / `surface` | App 默认暗主题 |
| 靛蓝（主） | `#5B8DEF` | `primary` | 主操作、选中态、对话气泡（己方） |
| 溯源绿 | `#3FB68B` | `secondary` / `secondaryContainer` | `SourceChip`、溯源链接 |
| 反幻觉金 | `#E0A458` | `tertiary` / `tertiaryContainer` | `TimeChip` 的 `time_kind` 角标、确定性解析标记 |
| 警示红 | `#E0584F` | `error` | verify 失败、危险操作 |

```kotlin
// core/ui/Color.kt
val PaDarkColors = darkColorScheme(
    background = Color(0xFF0E1116),
    surface = Color(0xFF0E1116),
    primary = Color(0xFF5B8DEF),
    onPrimary = Color.White,
    secondary = Color(0xFF3FB68B),        // 溯源绿
    onSecondary = Color(0xFF0E1116),
    tertiary = Color(0xFFE0A458),         // 反幻觉金
    onTertiary = Color(0xFF0E1116),
    error = Color(0xFFE0584F),
)
// 浅色方案对称定义 PaLightColors（同语义，提亮 background/surface）
```

**动态取色（Dynamic Colors）**：Android 12+ 可启用 `dynamicColorScheme(context)`，但本项目视觉强语义（绿=溯源、金=反幻觉）建议**默认关闭**动态取色以保语义稳定，仅在"跟随系统壁纸"用户开关下启用，并回退到 `PaDarkColors`。

### 2.2 排版

```kotlin
val PaFontFamily = FontFamily(
    Font(R.font.pf_sc_regular),   // PingFang/思源黑体（打包字体回退中文）
)
// M3 TypeScale 映射: bodyMedium=14, bodyLarge=16, titleLarge=20, headlineMedium=24
```
正文 14/16、标题 20/24，与 Web 端一致；中文优先 PingFang/思源黑体 fallback。

### 2.3 库选型决策

| 需求 | 选型 | 备注 |
|---|---|---|
| 基础组件 | **Compose M3** | 全项目默认；`material-components-android`(Views) 仅在 legacy 互操作时 |
| 下拉刷新 | **Compose `pullToRefresh` Modifier** | 不引入 SmartRefreshLayout(Views 体系)，避免互操作 |
| 动画 | **lottie-android**（Compose `LottieAnimation`） | 蒸馏生成、空状态、listening 波形 |
| 图表 | **Compose Canvas 自绘** | persona 雷达图、时间线轻量图；重度图表再引 MPAndroidChart(Views)，需 `AndroidView` 包装 |
| 设计→代码 | **Relay for Figma** 主 + Figma-to-Compose 插件备 | 设计师 Figma + M3 Design Kit |
| 灵感 | **Mobbin / Dribbble** | 真实 App 交互模式参考 |

### 2.4 通用可复用组件（反幻觉可见性的关键载体）

对应 Web 端 `<TimeChip>/<SourceChip>/<VerifyBadge>/<Timeline>`：

```kotlin
@Composable
fun TimeChip(createdAt: String, timeKind: String?, modifier: Modifier = Modifier)
// 角标用 tertiary(金) 标 received/occurred；悬停/长按提示"记录时间≠发生时间"

@Composable
fun SourceChip(source: String, onClick: (String) -> Unit, modifier: Modifier = Modifier)
// source 形如 "segment:<id>" / "result:<N>" / "persona:<维度>" / "memory:<id>"
// 点击跳源；用 secondary(绿)

@Composable
fun VerifyBadge(passed: Boolean, detail: String?, modifier: Modifier = Modifier)
// ✅ passed(secondary绿) / ❌ failed(error红)；来自 /verify

@Composable
fun Timeline(items: List<TimelineItem>, modifier: Modifier = Modifier)
// segments/chat_log/reminders 通用；每项带 TimeChip + 可选 SourceChip
```

每个组件的入参契约**严格对齐后端字段**（`time_kind`、`source_ids`、`evidence`、verify 的 `rep+assertion`）。

---

## 三、逐屏设计

### 3.0 导航结构

- **底部 `NavigationBar`** 四主入口：**对话 / 记忆 / 日历 / 我的**。
- **"我的"** 内含二级入口：录音上传、数字分身、提醒、反幻觉体检、推荐、个人 wiki、设置。
- **首页 Dashboard**（"我的"顶部或首启）：`GET /health` 显示后端模式（llm/asr/embedder/speaker），最近记忆/今日事件/待办提醒概览。
- **深链/通知跳转**：reminder 通知 → RemindersPage；intervention 通知 → ChatPage（预填上下文）。

### 3.1 对话屏 ChatPage

| 项 | 内容 |
|---|---|
| 端点 | `POST /chat`（入 `{message}` 返 `{reply}`）+ `GET /chat-log`（`logs[]{role,content,created_at}`） |
| UiState | `chatLog: List<ChatMsg>`, `sending: Boolean`, `draft: String` |
| 交互 | 进入拉 `chat-log`；发送 → `POST /chat`；己方气泡 primary、分身气泡 surfaceVariant；非流式（后端当前非流），未来可平滑接 SSE |
| 通用组件 | 每条 `TimeChip(createdAt, timeKind=null)`（chat_log 仅 created_at）；`VerifyBadge` 顶部体检入口 |
| 反幻觉 | 对话 reply 若后端未来带溯源，则附 `SourceChip`；当前以"真实时间戳"标注（chat_log 真实时间戳是后端硬约束的体现） |

### 3.2 录音 / 上传转录屏 InboxPage

| 项 | 内容 |
|---|---|
| 端点 | `POST /inbox/upload`（原始 body + `?filename=`，免 multipart）+ `POST /ingest`；说话人展示 `GET /speakers` |
| UiState | `recording: Boolean`, `levels: List<Float>`（波形）, `speakers: List<Speaker>`, `uploadState` |
| 交互 | 录音按钮（前台服务，见 §4）→ 停止 → 端/服务端转写 → `POST /inbox/upload` 投 body（文本=`.txt` 转写稿）+ filename → 提示 `ingest_hint` → 可触发 `POST /ingest`；说话人列表展示 `name/label/note` |
| 通用组件 | `Timeline`（最近段落）；`SourceChip(segment:<id>)` |
| 反幻觉 | 段落 `TimeChip(createdAt, time_kind)`，`time_kind` 区分 received/occurred；溯源 `source_file` |
| 注意 | 设备自带转录（决策3），App 端可用 OnDevice ASR 或直接接收设备转写文本；音频文件可选上传，默认不持久化原始音频（§4 隐私） |

### 3.3 段落 / 记忆流 MemoriesPage

| 项 | 内容 |
|---|---|
| 端点 | `GET /segments`（限100）+ `GET /memories`（末50） |
| UiState | `segments: List<Segment>`, `memories: List<Memory>`, `tab: Segs|Mems` |
| 交互 | 顶 Tab 切换；下拉刷新（Compose `pullToRefresh`）；`Timeline` 渲染 |
| 通用组件 | `TimeChip(created_at, time_kind)`、`SourceChip(segment:<id>)`、`Timeline` |
| 反幻觉 | memory 的 `evidence` 字段透传并渲染为 `SourceChip`；`processed` 标记已处理 |

### 3.4 数字分身 PersonaPage

| 项 | 内容 |
|---|---|
| 端点 | `GET /profile`（`version, change_summary, profile{9维度}`）+ `POST /distill`（触发蒸馏） |
| UiState | `version, changeSummary, profile9: Map<Dim,String>, distilling: Boolean` |
| 交互 | 9 维度卡片/雷达图（Compose Canvas）；`change_summary` 高亮；"重新蒸馏"按钮 → `POST /distill` |
| 通用组件 | `VerifyBadge`（蒸馏后可跳 verify） |
| 反幻觉 / shape 对齐 | **后端 profile 是扁平 8 维文本**，Web 前端带 score 是占位（`api.js` 注"非真实评估"）。**App 不捏造 score**：直接渲染文本维度；若要雷达图，仅用文本长度/有无作"已填充度"可视化，明确标注"非真实评分"。 |
| 动画 | 蒸馏进行时 lottie 动画 |

### 3.5 日历 CalendarPage

| 项 | 内容 |
|---|---|
| 端点 | `GET /calendar?q=`（检索"明天/上周/本月"）+ `GET /events`（全部事件） |
| UiState | `query: String`, `events: List<Event>`, `allEvents: List<Event>` |
| 交互 | 顶部搜索框（中文自然语言："明天""上周""本月"）→ `GET /calendar?q=`；列表/日视图；全量 `GET /events` |
| 通用组件 | `TimeChip`、`Timeline` |
| 反幻觉 | **`when_raw`（LLM 抽取原文）vs `when_dt`（temporal 确定性解析绝对日期）视觉区分**：`when_raw` 用 tertiary(金) 标"LLM 原文"、`when_dt` 用 secondary(绿) 标"确定性解析"，长按提示差异。这是反幻觉硬约束的核心落地之一。 |

### 3.6 提醒 RemindersPage

| 项 | 内容 |
|---|---|
| 端点 | `GET /reminders` + `POST /reminders/check` |
| UiState | `reminders: List<Reminder>`, `fired: List<String>` |
| 交互 | 列表；"立即检查"按钮 → `POST /reminders/check`；到点经 §4 通知通道推送 |
| 通用组件 | `TimeChip`、`Timeline` |
| 反幻觉 | 循环类提醒重排后的时间用 `time_kind` 标注；溯源 `when_raw` |

### 3.7 反幻觉体检 VerifyPage

| 项 | 内容 |
|---|---|
| 端点 | `POST /verify`（`rep + assertion`） |
| UiState | `report: VerifyRep`, `assertion: Boolean` |
| 交互 | "运行体检" → `POST /verify`；展示 `rep` 与 `assertion`；逐条 `VerifyBadge` |
| 通用组件 | `VerifyBadge`（本屏主舞台） |
| 反幻觉 | 本屏即反幻觉的可见总览：列出 when_dt 确定性重解覆盖、when_raw/记忆内容溯源到源转录、不落地即删的条目 |

### 3.8 推荐 RecommendPage

| 项 | 内容 |
|---|---|
| 端点 | `GET /recommend?kind=&q=`（`{count,recommendations[]{item,reason,based_on}}`） |
| UiState | `kind: String`, `q: String`, `recs: List<Recommendation>` |
| 交互 | kind 切换（书/影/做事方式）+ 查询 → `GET /recommend` |
| 通用组件 | `SourceChip(based_on)` —— `based_on` 形如 `persona:<维度>` 或 `result:<N>` |
| 反幻觉 | 推荐内容须溯源到搜索结果（`result:<N>`）或 persona 维度，`SourceChip` 可点跳源 |

### 3.9 个人 wiki WikiPage

| 项 | 内容 |
|---|---|
| 端点 | `GET /wiki?tag=&q=`（`pages[]{id,title,body,tags,source_ids,link_ids,created_at}`）+ `POST /wiki/build` |
| UiState | `tag: String?`, `q: String`, `pages: List<WikiPage>` |
| 交互 | 按标签/词检索；"增量构建"按钮 → `POST /wiki/build`；页内 `link_ids` 互链跳转 |
| 通用组件 | `SourceChip(source_ids)`、`TimeChip` |
| 反幻觉 | wiki body 溯源到 `source_ids`（记忆 id），记忆溯源到源转录——链式溯源在 `SourceChip` 点击中体现 |

### 3.10 主动干预

| 项 | 内容 |
|---|---|
| 端点 | `POST /triggers`（`{fired:[...]}`） |
| 交互 | 后端返回 `fired` 干预列表 → 以**系统通知**（intervention 通道）+ ChatPage 卡片形式呈现 |
| 通用组件 | 干预卡片内附 `SourceChip`（溯源到 persona/记忆） |
| 反幻觉 | 干预依据须可溯源 |

### 3.11 设置 SettingsPage

| 项 | 内容 |
|---|---|
| 端点 | `GET /settings/llm`（回 `backend,model,base_url,api_key_masked,max_tokens,thinking_effort,thinking_format,native_preview,uses_max_completion_tokens`，**不回显 context_window/key**）+ `POST /settings/llm`（写覆盖 `{model?,context_window?,max_tokens?,thinking_effort?,base_url?,api_key?,backend?}`，返回 `{backend, applied, effective}`） |
| UiState | `settings: LlmSettings`, `nativePreview: String`, `usesMaxCompletionTokens: Boolean`, `saving: Boolean` |
| 交互 | 5+ 旋钮：model / context_window / max_tokens / thinking_effort(off·低·中·高) / base_url / api_key / backend（白名单 stub/anthropic_proxy/ollama/openai_compat/glm_anthropic）；保存 → `POST /settings/llm`，回显 `applied` 与生效 `effective` |
| 反幻觉 / 诚实配置 | **key 不回显**：展示 `api_key_masked`；**思考档位不前端捏造 budget**：直接展示后端 `native_preview`（如"GLM-anthropic: thinking.budget_tokens=12288"）+ `uses_max_completion_tokens`（OpenAI o 系改发 max_completion_tokens），标注"按官方文档映射"；用户选档位后由后端算原生字段 |
| 通用组件 | `VerifyBadge`（配置变更后可跳 verify） |

---

## 四、前台录音服务 · 数据管线 · 通知 · 隐私

### 4.1 24h 被动听前台服务

- **采音**：`AudioRecord`（PCM）+ 端侧 VAD（静音切分）；按"说话段"成段，不连续写盘。
- **转写**：优先**端转写**（设备自带转录 / OnDevice ASR，对齐决策3"设备已自带转录"）；服务端 `asr.py` 为可选回退（GPU 盒真模型待上）。
- **投递**：转写文本 → `POST /inbox/upload`（body=文本，`?filename=...txt`，**免 multipart**）→ 后端 watch inbox → `POST /ingest` 灌入。后端返回 `ingest_hint`。
- **常驻前台通知**：listening 通道，"正在听…"可见，用户可一键暂停。

### 4.2 电池 / 功耗

- 采音占空比策略：VAD 静音段不投递；息屏后降频轮询；Doze/后台限制下用前台服务保活 + WorkManager 周期兜底。
- 上传 retry：WorkManager 指数退避，断网缓存转写文本待发。

### 4.3 隐私落地（硬约束1）

- **API key 永不出现在 App**（§1.3）。
- **原始音频默认不持久化**：仅落转录文本上传；如需音频（如声纹注册），加密短期留存、上传/注册后即删。
- **HTTPS + 可选鉴权**：BASE_URL 必须支持 HTTPS（或局域网可信）；AUTH_TOKEN 走请求头。
- **用户控制**："暂停 listening"开关；"一键清本地缓存"（清 Room，不动后端数据）。

### 4.4 提醒 / 干预通知

- **AlarmManager 精确到点兜底** + **WorkManager 周期 `POST /reminders/check`** 双保险；`fired` 触发 reminder 通道通知。
- **intervention**：`POST /triggers` 返回 `fired` → intervention 通道通知，点击跳 ChatPage。
- **通知 Channel**：`listening`（前台常驻）、`reminder`（到点）、`intervention`（主动建议）、`chat`（分身回复，可选）。

### 4.5 反幻觉在录音链路的体现

- 段落 `time_kind`：录音投递时间(received) vs 段落实际发生时间(occurred)在通知与列表均标注。
- 溯源 `source_file`：每段可回溯到投递文件名。

### 4.6 权限请求时序

1. 首启：解释 → 请求 `POST_NOTIFICATIONS`。
2. 启用 listening：解释 → 请求 `RECORD_AUDIO` → 获授权后 `startForeground(microphone)`。
3. 启用精确提醒：请求 `SCHEDULE_EXACT_ALARM`（Android 12+）。

---

## 五、导航 · 状态管理 · 数据层 · 测试 · 分阶段交付

### 5.1 导航

Compose Navigation（`NavHost`）。底部 `NavigationBar`：对话/记忆/日历/我的；二级页经"我的"或快捷入口。深链：`pa://reminder/{id}`、`pa://intervention`。通知 PendingIntent 跳转。

### 5.2 状态管理

每屏 `ViewModel` + `StateFlow<UiState>`；`Repository` 聚合 Retrofit + Room；统一 `LoadState`（Idle/Loading/Success/Error/Empty）；离线降级读 Room 缓存（只读）。

### 5.3 数据层（Retrofit 接口示例，对齐契约）

```kotlin
interface PaApi {
    @POST("chat")
    suspend fun chat(@Body body: ChatIn): ChatOut              // {message} -> {reply}

    @GET("memories")
    suspend fun memories(): MemoriesOut                         // 末50

    @Streaming @POST("inbox/upload")
    @Headers("Content-Type: text/plain")
    suspend fun uploadInbox(
        @Body body: RequestBody,                               // 原始 body(免 multipart)
        @Query("filename") filename: String,
    ): InboxUploadOut                                          // {saved,bytes,ingest_hint}

    @GET("settings/llm")
    suspend fun llmSettings(): LlmSettings                     // api_key_masked + native_preview

    @POST("settings/llm")
    suspend fun updateLlm(@Body body: LlmSettingsIn): LlmSettings

    @GET("calendar")
    suspend fun calendar(@Query("q") q: String): CalendarOut   // "明天/上周/本月"
}
```

DTO 用 `data class` + `kotlinx.serialization`，保留 `evidence/source_ids/time_kind/native_preview/when_raw/when_dt/version/change_summary/api_key_masked` 等字段。Room 缓存实体对应 segments/memories/events/reminders/chat_log。DataStore 存 BASE_URL/token/theme。

### 5.4 反幻觉与诚实配置在数据层的体现

- **字段透传**：DTO → UiState 全程保留溯源/时间/原生预览字段，不丢字段、不重命名。
- **诚实配置**：App 不算 budget，只展示 `native_preview`；档位选择发后端，由后端按 provider 算原生字段（对齐后端 v0.5 `_thinking_body` 实测映射）。

### 5.5 测试

- **单元**：Repository/ViewModel with fakes（DTO 字段透传断言、离线降级）。
- **仪器**：Compose UI 测试（关键屏渲染、TimeChip/SourceChip 显示）。
- **契约测试**：后端已有 stub 模式（`/health` 返回模式），App 用 stub 后端做 e2e（与后端 `tests/test_e2e.py` stub 链路对齐）。

### 5.6 分阶段交付（对齐项目 MVP 哲学"核心做深"）

| 阶段 | 范围 | 对齐端点 |
|---|---|---|
| **M1** | 对话 + 录音上传 + 记忆流 | `/chat` `/chat-log` `/inbox/upload` `/ingest` `/segments` `/memories` `/health` |
| **M2** | 日历 + 提醒 + 通知 | `/calendar` `/events` `/reminders` `/reminders/check` |
| **M3** | 蒸馏/persona + verify + wiki + 推荐 + 主动干预 | `/profile` `/distill` `/verify` `/wiki` `/wiki/build` `/recommend` `/triggers` `/speakers` |
| **M4** | 设置面板 + 前台服务稳定 + 隐私加固 | `/settings/llm`(GET/POST) + 前台服务/权限/通知完善 |

### 5.7 风险与未决

- **设备形态未定**（决策3）：录音/上传形态后定，M1 先支持"上传已有转写文本"路径，录音前台服务作为 M1 可选/M4 稳定。
- **GPU 盒真 ASR/embedding/本地 LLM 未上**：App 端转写先用 OnDevice 或设备自带；真后端依赖 GPU 盒（开发盒≠GPU 盒）。
- **真后端待 GPU 盒**：App 全程可用 stub 后端开发，真链路验证留 GPU 盒。
- **`/chat` 非流式**：当前 `POST /chat` 返 `{reply}` 整体返回；App 按非流式实现，预留 SSE 接口位。

---

## 六、端点 → 屏 映射总表

| 端点 | 方法 | 对应屏 | 关键字段 | 反幻觉落点 |
|---|---|---|---|---|
| `/health` | GET | Dashboard | llm/asr/embedder/speaker 模式 | — |
| `/ingest` | POST | InboxPage | scan_inbox 结果 | ingest_hint |
| `/inbox/upload` | POST | InboxPage | body+filename，出 saved/bytes/ingest_hint | 溯源 source_file |
| `/segments` | GET | MemoriesPage | id,source_file,text,speaker,created_at,time_kind | TimeChip(time_kind) |
| `/memories` | GET | MemoriesPage | id,segment_id,kind,content,evidence | SourceChip(evidence) |
| `/profile` | GET | PersonaPage | version,change_summary,profile9 | 不捏造 score |
| `/distill` | POST | PersonaPage | 蒸馏结果 | lottie + VerifyBadge |
| `/chat` | POST | ChatPage | message→reply | 真实时间戳 |
| `/chat-log` | GET | ChatPage | logs[]{role,content,created_at} | TimeChip |
| `/verify` | POST | VerifyPage | rep+assertion | VerifyBadge |
| `/triggers` | POST | 主动干预(通知) | fired[] | SourceChip(依据) |
| `/calendar` | GET | CalendarPage | count,events[] | when_raw vs when_dt 区分 |
| `/events` | GET | CalendarPage | events[] | TimeChip |
| `/reminders` | GET | RemindersPage | reminders[] | TimeChip |
| `/reminders/check` | POST | RemindersPage | fired | 通知通道 |
| `/speakers` | GET | InboxPage | speakers[]{name,label,note} | — |
| `/recommend` | GET | RecommendPage | recommendations[]{item,reason,based_on} | SourceChip(based_on) |
| `/wiki` | GET | WikiPage | pages[]{title,body,tags,source_ids,link_ids} | SourceChip(source_ids) 链式 |
| `/wiki/build` | POST | WikiPage | built | — |
| `/settings/llm` | GET | SettingsPage | api_key_masked,native_preview,uses_max_completion_tokens(不回显 context_window/key) | key 不回显 + 诚实配置 |
| `/settings/llm` | POST | SettingsPage | 覆盖写; 返回 {backend,applied,effective} | 不持明文 key |

---

## 七、风险与未决（汇总）

1. **设备形态未定**（决策3）：录音前台服务先做"上传转写文本"主干，录音采音作为可选/后稳。
2. **GPU 盒真后端未上**：App 用 stub 后端开发，真 ASR/embedding/LLM 验证留 GPU 盒。
3. **`/profile` shape 差异**：后端扁平 8 维文本 vs Web 前端带 score——App 不捏造 score，仅文本渲染或"已填充度"可视化。
4. **`/chat` 非流式**：按整体返回实现，预留 SSE。
5. **前台服务 + 权限政策**：Android 14+ `foregroundServiceType=microphone` 与 `POST_NOTIFICATIONS`/`SCHEDULE_EXACT_ALARM` 运行时授权须严格时序。

---

## 八、落地路径（对齐用户资源文档）

1. **设计**：Figma + **Material 3 Design Kit（官方）**，灵感参考 **Mobbin**（真实 App 截图）/ **Dribbble**（搜 `material design` / `jetpack compose UI`）。
2. **设计→开发**：**Google Relay for Figma** 或 **Figma-to-Compose 插件**交接，产出 Compose 代码 + 主题资源；复杂主题系统可用 **Supernova**。
3. **开发**：**Jetpack Compose + Material 3** 为主，复杂动画用 **lottie-android**，轻量图表用 Compose Canvas（重度再引 **MPAndroidChart**），下拉刷新用 Compose `pullToRefresh`（不引 SmartRefreshLayout 以免 Views 互操作）。缺控件去 **awesome-android-ui** 找交互模式。
4. **交付节奏**：按 §5.6 M1→M4，每阶段对齐后端端点与 stub/真后端验证。

---

> 本文档与 `frontend-design.md`（Web 端）共用后端契约与设计语义；App 复用 Web 端 token 语义但落地为 Material 3 ColorScheme + Compose 主题。所有端点映射经 §6 总表与 §3 逐屏双重核对，未捏造端点。
