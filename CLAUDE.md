# CLAUDE.md — personal-assistant

## 项目定位
全自动个人助手：数据完全本地；24h 被动听用户说话（录音设备→大脑，传输用户自理）；自动蒸馏成数字分身（人格/习惯/思维/技能/知识），并主动给建议/安抚/推荐。安卓 App + Web 控制端；大脑跑本地电脑或云服务器。

## 当前阶段
development（用户 2026-06-28 直导式构建，`planning/status.json` locked=true）。MVP=深核主干：ASR→记忆→蒸馏→对话→主动。App/Web/推荐后补。

## 架构与模块
- `src/personal_assistant/asr/` — 接入 watch + VAD + 转写 + 说话人分离。`Transcriber` 接口 + `FasterWhisperTranscriber`(prod,lazy import) + `StubTranscriber`(dev,喂样例文本)。
- `src/personal_assistant/storage/` — SQLite(片段/记忆元数据+embedding BLOB) + DuckDB(习惯/时段分析) + numpy 余弦检索。
- `src/personal_assistant/memory/` — LLM 从片段抽取事实/事件/偏好/意图/情绪 → 记忆库 + 检索。
- `src/personal_assistant/distill/` — 蒸馏引擎：反思循环 → 更新结构化人格档案 `persona/profile.json`（版本化、带证据引用、不接受 LLM 散文自评）。
- `src/personal_assistant/proactive/` — 事件触发器扫新记忆/蒸馏增量关键信息 → 生成干预（建议/安抚/推荐）→ 推送（dev 走 CLI/摘要）。
- `src/personal_assistant/chat/` — 被动对话：人格档案(system prompt)+记忆检索。
- `src/personal_assistant/llm/` — 可插拔 LLM/Embedder：stub/anthropic_proxy/ollama/openai_compat。
- `src/personal_assistant/api/` — FastAPI：/chat /segments /profile /triggers /ingest。

## 开发约束（本机）
- 无 GPU、无 torch、无 ollama、无 ffmpeg、HuggingFace 不可达、外部 DNS 受限、pip 装不了新包（files.pythonhosted 超时）。
- 故全栈 **stdlib + 已装包(numpy/duckdb/fastapi/uvicorn/pydantic)**：配置 JSON(免 pyyaml)、LLM/Embedder 用 urllib 直发(免 SDK)、文件监听轮询(免 watchdog)、调度线程(免 apscheduler)、测试 unittest(免 pytest)。
- ASR 默认 stub（读 .txt 转录稿；faster-whisper 真后端写齐 lazy import，GPU 盒+HF 可用时切）。
- Embedder 默认 hashing（确定性零网络；真 GLM embedding-3 在 GPU 盒切 openai_compat）。
- **会话代理 `127.0.0.1:58597/v1/anthropic` 实测可用作真 LLM**（AnthropicProxyLLM，路径 /v1/messages）。配额有限、随会话存活。
- 环境覆盖后端：`PA_LLM_BACKEND` / `PA_ASR_BACKEND` / `PA_EMBEDDER`（见 config.py）。

## 运行
```bash
.venv/bin/python -m personal_assistant.cli pipeline --once   # 跑接入→ASR→入库
.venv/bin/python -m personal_assistant.cli distill           # 跑蒸馏
.venv/bin/python -m personal_assistant.cli chat              # 被动对话
.veniv/bin/python -m personal_assistant.cli proactive        # 主动触发
.venv/bin/uvicorn personal_assistant.api.main:app --reload   # API
.venv/bin/pytest -q                                          # 测试
```

## 设计原则（沿用 autonomous-studio）
1. 确定性 > LLM 自评：outcome/evidence 用可观察事实，不接受散文。
2. 可插拔：所有外部依赖（LLM/ASR/Embedder）走接口，dev stub / prod real 一键切。
3. 最小改动：只改完成当前任务必须改的部分。
4. 不直接动 main 的自治优化走 opt-worktree；本项目是用户直导式构建，直接提交本项目 main（autonomous gate 已解除）。

## 不可用
本机无 GPU/HF，faster-whisper 真模型、Ollama、云端真 GLM key 均不可在此验证；相关代码写齐并单测接口，真验证留 GPU 盒。
