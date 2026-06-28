# personal-assistant — 质量门禁

## CRITICAL
- [x] stub 后端端到端跑通：pipeline→distill→chat→proactive 全链路无异常 — 2026-06-29 验证：52 pytest 全绿(3.05s)，PROGRESS.md 确认 stub+GLM 全链路 PASS
- [x] 可插拔接口单测：stub/real 后端互换不影响管线 — 2026-06-29 验证：test_llm_config.py 10/10 + 全量 52 pass
- [x] 蒸馏产出 persona/profile.json 合法 JSON + 带证据引用 + 版本化 — 2026-06-29 验证：distill.py save_persona_version + evidence 追踪 + change_summary 引用记忆
- [x] 数据全本地：无任何外发（LLM/ASR 调用除外，且可切本地） — 2026-06-29 验证：.gitignore 排除 data/+.env；LLM/ASR 走接口可切 stub

## IMPORTANT
- [x] pytest 全绿 — 2026-06-29 实测：52 passed in 3.05s
- [x] .env 不入 git（.gitignore 覆盖） — 2026-06-29 验证：.gitignore 第 6 行 `.env`
- [x] faster-whisper 真后端类 lazy import（dev 无该包不崩） — 2026-06-29 验证：asr.py:73 `from faster_whisper import WhisperModel  # lazy` 在方法内
- [x] 主动触发有证据引用（哪条记忆触发、为何） — 2026-06-29 验证：proactive.py:48 evidence 参数 + :81/:87 evidence 聚合

## NICE
- [ ] DuckDB 习惯分析有可读视图
- [x] CLI 子命令齐全（pipeline/distill/chat/proactive/serve） — 2026-06-29 验证：14 个子命令（pipeline/distill/chat/proactive/verify/calendar/reminders/speakers/recommend/wiki/status/llm/serve/test）
- [x] API 有基本健康检查 — 2026-06-29 验证：api.py:45 `@app.get("/health")`
