# CLAUDE.md — personal-assistant

## 项目定位
全自动个人助手：数据完全本地；24h 被动听用户说话（**设备自带转录**，传输用户自理）；自动蒸馏成数字分身（人格/习惯/思维/技能/知识）；区分说话人（音频+文字融合）；自动整理日历+定时提醒；主动给建议/安抚/推荐。安卓 App + Web 控制端（后补）；大脑跑本地电脑或云服务器。

## 当前阶段
development（用户 2026-06-28 直导式构建，`planning/status.json` locked=true）。v0.1 深核 + v0.2 说话人/日历/提醒/反幻觉 均端到端跑通。

## 架构与模块（包在根级 `personal_assistant/`，扁平模块）
- `config.py` — 加载 .env + config/default.json，${VAR} 替换，PA_*_BACKEND 环境覆盖。
- `llm.py` — 可插拔 LLM/Embedder：StubLLM(智能桩,带 [TASK:*] 分发) / AnthropicProxyLLM(会话代理,urllib) / OllamaLLM / OpenAICompatLLM；HashingEmbedder / OpenAICompatEmbedder。
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
- `api.py` — FastAPI：/health /ingest /segments /memories /profile /chat /distill /triggers /calendar /events /reminders /verify /chat-log。
- `cli.py` — 子命令：pipeline / distill / chat / proactive / calendar / reminders / speakers / verify / status / serve / test。

## 反幻觉与真实时间（核心约束）
- **真实时间戳**：所有 created_at/when/chat_log 用 `storage.now_iso()`=系统本地实时；temporal 解析的 reference=真实 `datetime.now()`。
- **日历时间真实**：when_dt **只用 `temporal.resolve`（确定性规则）**，**禁止 LLM 编造日期**（无 LLM 日期兜底）。LLM 只抽 when_raw 短语。
- **脚本复查**：每次 ingest 后 `verify.run_all()` 自动跑——重解 when_dt、溯源 when_raw/记忆到源转录、不落地即删。`verify.assert_no_hallucination()` 供测试/CLI 断言。

## 开发约束（本机）
- 无 GPU/torch/ollama/ffmpeg、HuggingFace 不可达、pip 装不了新包(files.pythonhosted 超时)、无 venv(ensurepip 缺)。
- 故全栈 **stdlib + 已装包(numpy/duckdb/fastapi/uvicorn/pydantic)**：配置 JSON、LLM/Embedder urllib 直发、文件监听轮询、调度线程、测试函数式。
- ASR 默认 stub（设备已自带转录，ASR 非必需）；faster-whisper 真后端 lazy import(GPU 盒)。
- Embedder 默认 hashing；说话人默认 text（pyannote 真声纹需 GPU 盒+HF token）。
- **会话代理 `127.0.0.1:58597/v1/anthropic` 实测可用作真 LLM**（路径 /v1/messages，随会话存活）。
- 环境覆盖：`PA_LLM_BACKEND` / `PA_ASR_BACKEND` / `PA_EMBEDDER`。

## 运行
```bash
python3 -m personal_assistant.cli test                              # stub 全链路
PA_LLM_BACKEND=anthropic_proxy python3 -m personal_assistant.cli test  # 真 GLM-5.2
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
