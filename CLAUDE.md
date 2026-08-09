# CLAUDE.md — personal-assistant

## 项目定位
全自动个人助手：数据完全本地；24h 被动听用户说话（**设备自带转录**，传输用户自理）；自动蒸馏成数字分身（人格/习惯/思维/技能/知识）；区分说话人（音频+文字融合）；自动整理日历+定时提醒；主动给建议/安抚/推荐。安卓 App + Web 控制端（后补）；大脑跑本地电脑或云服务器。

## 当前阶段
development（用户 2026-06-28 直导式构建）。v0.8 ESP32 双模式固件 + 语音链路修复（07-25）。

## 最近工作 (2026-07-25)
- **语音链路修复**：TTS opus 编码修复（`decode(audio=0)` + libopus）、ASR 反幻觉过滤（黑名单+低置信段）、延迟优化（预热+VAD缩短+语音模式）
- **Hermes 记忆导入**：17 份持久记忆 → 25 条写入 PA 记忆系统 + 人格蒸馏
- **微信记录导入（待完成）**：4.x 口令待 cdb 断点捕获（`E:\x-tool\wcdb-key-tool\run_cdb.py`）
- **后端**：端口 8004，空库重启，`start-pa.bat` 或手动 `python -m personal_assistant.cli serve`

## 架构与模块（包在根级 `personal_assistant/`，扁平模块）
- `config.py` — 加载 .env + config/default.json，${VAR} 替换，PA_*_BACKEND 环境覆盖。
- `llm.py` — 可插拔 LLM/Embedder：StubLLM(智能桩,带 [TASK:*] 分发) / AnthropicProxyLLM(会话代理,urllib) / OllamaLLM / OpenAICompatLLM / GLMAnthropicLLM(GLM anthropic 端点)；HashingEmbedder / OpenAICompatEmbedder。**5 旋钮可配**(model/context_window/max_tokens/thinking_effort off·低·中·高/base_url/api_key)+全局覆盖层；`_thinking_body` 按官方文档映射 4 家 provider 原生思考字段；`effective_llm_config()`+`mask_key()` 供 cli/api。
- `transcript.py` — 解析设备转录（.txt 每行/带时间戳/说话人标签 / .srt）→ Utterance。
- `asr.py` — Transcriber 接口 + StubTranscriber + FasterWhisperTranscriber(lazy,prod)；IngestionPipeline(纯音频回退路径)。
- `speaker.py` — 说话人区分：Diarizer 接口 + TextDiarizer(dev,文字+标签) + PyannoteDiarizer(prod,lazy,音频声纹+文字融合) + SpeakerRegistry。
- `ingest.py` — 接入编排：转录解析→说话人归属→入库→记忆抽取+日历事件+提醒→**verify 反幻觉复查**。
- `storage.py` — SQLite(片段/记忆/人格版本/干预/说话人/事件/提醒/chat_log/kv) + DuckDB(时段统计) + numpy 余弦检索；`now_iso()`=系统本地实时。
- `memory.py` — LLM 抽 fact/event/preference/intention/emotion/skill → embedding → 检索。
- `distill.py` — 蒸馏引擎：反思循环→persona/profile.json（9 维、版本化、证据引用）。
- `calendar.py` — 事件抽取（LLM 抽 when_raw）→ **temporal 确定性解析绝对日期**（无 LLM 日期兜底）→ 检索。
- `reminders.py` — 提醒抽取→确定性解析→ReminderScheduler 到点触发（循环重排）。
- `temporal.py` — 中文时间表达解析（中文数字+阿拉伯；相对/绝对/循环）；`find_exprs` 供 verify 溯源。
- `verify.py` — **反幻觉脚本**：确定性重解 when_dt 覆盖、when_raw/记忆内容溯源到源转录、不落地即删；`assert_no_hallucination`。
- `proactive.py` — 主动触发（intention/emotional/topic）→ 干预 → CLI/日志。
- `chat.py` — 被动对话（人格档案 + 检索）。
- `api.py` — FastAPI：/health /ingest /segments /memories /profile /chat /distill /triggers /calendar /events /reminders /verify /chat-log /speakers /recommend /wiki + /settings/llm(GET/POST) /inbox/upload。
- `cli.py` — 子命令：pipeline / distill / chat / proactive / calendar / reminders / speakers / verify / status / llm / serve / test。

## 反幻觉与真实时间（核心约束）
- **时间戳=记录时间(收文时刻)，非真实发生时间**：段 `created_at` = 系统收到转录的 `now()`，`time_kind='received'` 显式标注。设备转录**无时间戳**，真实发生时间不可得（需设备时间戳或音频强制对齐 WhisperX，届时 `time_kind='occurred'`）。`start_sec/end_sec` 仅录音内偏移，不冒充墙钟。chat_log 同理用 `now()`。temporal 解析 reference=该记录时间。
- **日历时间真实**：when_dt **只用 `temporal.resolve`（确定性规则）**，**禁止 LLM 编造日期**（无 LLM 日期兜底）。LLM 只抽 when_raw 短语。
- **脚本复查**：每次 ingest 后 `verify.run_all()` 自动跑——重解 when_dt、溯源 when_raw/记忆到源转录、不落地即删。`verify.assert_no_hallucination()` 供测试/CLI 断言。

## 开发约束（本机）
- 无 GPU/torch/ollama/ffmpeg、HuggingFace 不可达、pip 装不了新包(files.pythonhosted 超时)、无 venv(ensurepip 缺)。
- 故全栈 **stdlib + 已装包(numpy/duckdb/fastapi/uvicorn/pydantic)**：配置 JSON、LLM/Embedder urllib 直发、文件监听轮询、调度线程、测试函数式。
- ASR 默认 stub（设备已自带转录，ASR 非必需）；faster-whisper 真后端 lazy import(GPU 盒)。
- Embedder 默认 hashing；说话人默认 text（pyannote 真声纹需 GPU 盒+HF token）。
- **会话代理 `127.0.0.1:58597/v1/anthropic` 实测可用作真 LLM**（路径 /v1/messages，随会话存活）。
- 环境覆盖：`PA_LLM_BACKEND` / `PA_ASR_BACKEND` / `PA_EMBEDDER` / `PA_LLM_MODEL` / `PA_LLM_BASE_URL` / `PA_LLM_API_KEY` / `PA_LLM_MAX_TOKENS` / `PA_LLM_THINKING`(off·低·中·高) / `PA_LLM_THINKING_FORMAT`(glm·openai·qwen·anthropic)。

## 运行
```bash
python3 -m personal_assistant.cli test                              # stub 全链路
PA_LLM_BACKEND=anthropic_proxy python3 -m personal_assistant.cli test  # 真 GLM-5.2
python3 -m personal_assistant.cli llm                               # 查生效 LLM 配置(key 掩码)
PA_LLM_BACKEND=openai_compat PA_LLM_THINKING=高 python3 -m personal_assistant.cli llm  # 改思考程度
python3 -m personal_assistant.cli pipeline --once                   # 灌 inbox 转录
python3 -m personal_assistant.cli calendar 明天                     # 日历检索
python3 -m personal_assistant.cli verify                            # 反幻觉复查
python3 -m personal_assistant.cli serve                             # API
```

## 设计原则
1. 确定性 > LLM 自评：时间/完成/可溯源性由脚本判定。
2. 可插拔：LLM/ASR/Embedder/Speaker 走接口，dev stub / prod real 一键切。
3. 反幻觉：每个 LLM 抽取环节后脚本溯源复查，不落地即删。
4. 最小改动；直导式构建直提本项目 main（autonomous gate 已解除）。

## guild 专家团（开发顾问 · 自动启用）

本项目配置了专属专家团（guild 框架，本地数据），5 位专家已灌入 17 份核心文档。

**自动机制**：每轮对话前 UserPromptSubmit hook 自动检索 guild 记忆并注入上下文。
你在回复时 **必须** 引用注入的 guild 记忆块（如有）。若 hook 注入的记忆与当前问题无关，你可忽略。

**主动查询**（当 hook 注入不足时）：
```bash
# 直接用 Python 查（guild 数据库在 E:/x-tool/guild/guild.db）
PYTHONPATH=E:/x-tool/guild python3 -c "
from guild.memory import MemoryStore, get_embedder
store = MemoryStore(embedder=get_embedder())
hits = store.archival_search('<expert_id>', query='<关键词>', limit=5)
for h in hits: print(h['title'], h['content'][:200])
store.close()
"
```

**5 位专家**：
| ID | 领域 | 关注 |
|----|------|------|
| pa-architect | architecture, design | 模块边界、数据流 |
| pa-backend | api, schema, backend | FastAPI、SQLite、LLM |
| pa-frontend | frontend, nextjs, react | Web + Android |
| pa-firmware | embedded, esp32 | ESP-IDF、PCM |
| pa-qa | testing, qa | 测试覆盖、反幻觉 |

<!-- STUDIO:BEGIN v6.2 -->
## Studio 研发流程（激活中）

planning/status.json 存在时，所有任务遵循以下规则。

### 铁律

1. **状态优先**：任何任务开始前先确认当前阶段。阶段决定行为边界——开发阶段不做部署，PRD 阶段不写代码。status.json 是唯一可信源。
2. **代码是现状唯一可信源**：报告进度、列待办、判断功能是否完成时，必须先搜代码确认实际状态，不能只看 prd.json 或任务文件就下结论。prd.json 是"计划做什么"，代码才是"实际做了什么"。
3. **规划与执行分离**：协调者不直接改项目文件，代码编写委托给执行 agent（serial-agent-handoff）。自主模式下串行开发时执行 agent 可直接提交；并行开发时只有控制器可以提交。
4. **自主模式优化走 worktree（不碰 main）**：进入 Studio 自主模式后建标记文件，优化改动提交到 optimization worktree，人审 diff 才合并。用户直接指挥的提交（无标记）不受限——本项目为直导式构建，直提 main。
5. **阶段推进可追溯**：阶段完成后立即更新 status.json（含推进原因和时间戳）。只能前进或合理回退，不能跳跃。
6. **主线保护**：临时问题不改 status.json。切换功能主线需用户明确确认。新会话进入若有进行中任务，先报告状态再行动。locked=true 表示有专属任务，其他会话只读不改。
7. 🚫 **PRD 确认硬关卡（HARD-GATE）**：prd.json 只能在用户明确说"确认/approved/可以了/没问题"后生成。模糊表态不算确认。自主模式也不能绕过此关卡。
8. **业务语言汇报**：所有汇报用产品/运营视角表达，禁技术黑话。待确认项说清选项和后果。
9. **最小改动**：写代码只改完成当前任务必须改的部分。不重构无关代码、不抽取只用一次的公共函数、不"顺手"重命名已有符号、不格式化整个文件。

### 阶段路由（按需 Read，不要全读）
做完一个阶段、验证通过后，把 status.json 的 currentStage 推进到下一阶段：需求→prd→development→prd-review→verification→review→deployment→archiving→archived。

| 你要做什么 | 读哪个 phase 文件 |
|---|---|
| 聊需求 / 写 PRD / 生成 prd.json | `phases/phase-build.md`（含覆盖检查强制步骤） |
| 写代码 / 单任务审查 / 全量 PRD 对照 | `phases/phase-dev.md` |
| E2E 验证 / 评审 / 部署 / 归档 / 回退 | `phases/phase-ship.md` |

路径前缀：`~/.agents/skills/autonomous-studio/`

### 新会话恢复规则
- 若 status.json 存在：先读 → 判断 currentStage → 报告当前状态
- currentStage=prd：先读 `planning/prd-decisions.md`，汇总已确认/待讨论要点
- currentStage=development：读 prd.json + **搜代码核实**每条任务实际状态（铁律 2），用业务语言报告
- locked=true：告知有任务进行中，询问是否接力
<!-- STUDIO:END -->
