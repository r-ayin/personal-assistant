# PRD — 全自动个人助手

> v0.3（2026-06-28）。数据完全本地、24h 被动听你说的一切、自动蒸馏成数字分身，并主动给建议/安抚/推荐的个人 AI 助手。安卓 App + Web 控制端；大脑跑本地电脑或云服务器。

## 用户价值
- **被动记录**：自动接收设备转录（无时间戳→系统加记录时间戳），区分说话人，沉淀可检索记忆。
- **蒸馏**：零散记忆→结构化人格档案（人格/价值观/习惯/技能/知识/思维/偏好/情绪），随经验进化。
- **日历/提醒**：从说话内容自动抽事件+时间→绝对日期日历（"什么时候发生的"秒检索）；意图→定时提醒到点触发。
- **主动干预**：关键时机（意图/情绪/截止/反复话题）主动给建议、安抚。
- **对话**：以你的风格/知识对话，懂你的分身。
- **推荐**：基于人格+记忆推荐书/影/做事方式，每条可溯源。
- **隐私**：数据全本地。

## 锁定决策（2026-06-28）
1. LLM 大脑：可插拔——本地 Ollama 默认 + 云端 GLM-5.2 端点（dev 实测会话代理可用）。
2. 硬件：用户有 GPU 本地电脑/服务器（开发盒≠GPU 盒）。
3. 音频到达：设备**已自带转录（无时间戳）**；接入层 watch inbox 收 .txt/.srt（+可选音频）；时间戳=系统收文记录时间（`time_kind='received'`，非真实发生时间）。
4. MVP：核心几功能做深。

## 技术栈
Python+FastAPI；faster-whisper(CTranslate2,免torch,ASR 回退)+可插拔 pyannote 分离；自研记忆层(SQLite+DuckDB+numpy 检索)；线程调度；Ollama/anthropic_proxy/openai_compat LLM(urllib 直发)；Kotlin+Compose 安卓(v1.1)；Next.js 面板(v1.1)。全栈 stdlib+已装包，零三方 SDK。人格微调(QLoRA)留 v2。

## 已完成
- **v0.1 深核**：ASR→记忆→蒸馏→对话→主动（端到端跑通，stub+真 GLM）。
- **v0.2**：说话人区分(音频+文字融合,TextDiarizer/PyannoteDiarizer)；自动日历(temporal 确定性日期解析+检索)；定时提醒(到点触发+循环重排)；反幻觉 verify(when_dt 确定性重解+溯源+不落地即删+assert)；真实时间戳(now_iso 本地实时+chat_log+time_kind)。
- **v0.3（本轮）**：推荐引擎——基于人格档案+记忆，推荐书/影/做事方式；反幻觉：每条推荐须引 persona 维度/memory id，不得编造用户偏好。

## 反幻觉与真实时间（核心约束）
- 时间戳=记录时间(收文 now)，`time_kind='received'` 标注，非真实发生时间。
- 日历 when_dt 只用 `temporal.resolve` 确定性规则（禁 LLM 编造日期）。
- 每次 ingest 后 `verify.run_all()` 脚本复查：when_dt 重解+溯源+不落地即删；`assert_no_hallucination` 断言。
- 推荐：基于真实 persona/memory，每条引证，不编造用户偏好。

## 非目标（v1）
安卓 App、Web 控制端、人格 LoRA 微调、多说话人关系建模、pyannote 真声纹(GPU 盒)、faster-whisper 真模型(GPU 盒)。

## 验收
stub + 真 GLM-5.2 全链路跑通 + 反幻觉断言通过；真后端(ASR/embedding/本地 LLM)留 GPU 盒验证。
