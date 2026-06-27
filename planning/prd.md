# PRD — 全自动个人助手（v1 / 深核 MVP）

## 一句话
数据完全本地、24h 被动听你说的一切、自动蒸馏成数字分身（人格/习惯/思维/技能/知识），并主动给建议/安抚/推荐的个人 AI 助手。安卓 App + Web 控制端；大脑跑本地电脑或云服务器。

## 用户价值
- 被动：自动记录+理解你每天说的所有话，沉淀为可检索记忆。
- 蒸馏：把零散记忆蒸馏成结构化人格档案，随经验积累进化。
- 主动：在关键时机（意图/情绪/截止日/反复话题）主动给建议、安抚、推荐。
- 对话：以你的风格/知识与你对话，像懂你的分身。
- 隐私：数据全本地。

## 锁定决策（2026-06-28）
1. LLM 大脑：可插拔——本地 Ollama 默认 + 云端 GLM-5.2 端点。
2. 硬件：用户有 GPU 本地电脑/服务器。
3. 音频到达：暂用样例音频开发，设备形态后定；接入层 watch inbox 目录。
4. MVP：核心几功能做深——ASR→记忆→蒸馏→对话→主动 主干做深；推荐/App/Web 后补。

## 技术栈
Python+FastAPI；faster-whisper(CTranslate2,免torch,VAD) + 可插拔 pyannote 分离；自研记忆层(SQLite+DuckDB+numpy检索)；APScheduler；Ollama/anthropic_proxy/openai_compat LLM(OpenAI兼容)；Kotlin+Compose 安卓(v1.1)；Next.js 面板(v1.1)；Docker Compose。人格微调(QLoRA)留 v2，MVP 用提示词人格。

## MVP 范围（深核）
- Phase 0 脚手架+ASR+后端骨架
- Phase 1 接入→VAD→ASR→声纹→片段库
- Phase 2 记忆抽取+检索
- Phase 3 蒸馏引擎+人格档案（反思循环，证据引用，版本化）
- Phase 4 被动对话（人格+检索）
- Phase 5 主动触发（3-5 触发→建议/安抚/推荐，dev 推送走 CLI/摘要）

## 非目标（v1）
推荐深化、安卓 App、Web 控制端、人格 LoRA 微调、多说话人关系建模。

## 验收
stub 后端全链路跑通 + 接口单测全绿；真后端在 GPU 盒验证（faster-whisper 大模型 + Ollama + 真 GLM key）。
