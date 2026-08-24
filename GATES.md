# personal-assistant — 质量门禁

## CRITICAL
- [x] stub 后端端到端跑通：pipeline→distill→chat→proactive 全链路无异常 — 2026-07-19 验证：102 pytest 全绿
- [x] 可插拔接口单测：stub/real 后端互换不影响管线 — 2026-07-19 验证：test_llm_config.py 10/10 + test_pluggable.py 41/41 + test_real_backends.py 3/3 + test_temporal.py 47/47
- [x] 蒸馏产出 persona/profile.json 合法 JSON + 带证据引用 + 版本化 — 2026-06-29 验证：distill.py save_persona_version + evidence 追踪 + change_summary 引用记忆
- [x] 数据全本地：无任何外发（LLM/ASR 调用除外，且可切本地） — 2026-06-29 验证：.gitignore 排除 data/+.env；LLM/ASR 走接口可切 stub

- [x] 单一 PA 后端：Electron 安装验证无 backend runtime、无新监听端口、无 Worker — 2026-07-31
- [x] 页面聊天不转弹幕：真实 WS page 收到 `chat_reply`，overlay 未收到；有效 `barrage` 事件 ID 端到端一致 — 2026-07-31
- [x] 本地 Worker 所有权与释放：独占/共享 consumer 真实 CUDA 验证，最终 Worker 退出且显存回到基线 — 2026-07-31
- [x] 认证边界：`/health`/`/web` 公开，数据与设置 API 无 token 为 401，Bearer 与 WS 使用同一 token 来源 — 2026-07-31
## IMPORTANT
- [x] pytest 全绿 — 2026-06-29 实测：52 passed in 3.05s
- [x] .env 不入 git（.gitignore 覆盖） — 2026-06-29 验证：.gitignore 第 6 行 `.env`
- [x] faster-whisper 真后端类 lazy import（dev 无该包不崩） — 2026-06-29 验证：asr.py:73 `from faster_whisper import WhisperModel  # lazy` 在方法内
- [x] 主动触发有证据引用（哪条记忆触发、为何） — 2026-06-29 验证：proactive.py:48 evidence 参数 + :81/:87 evidence 聚合

- [x] PA 全量回归 — 2026-07-31 实测：200 passed, 3 skipped
- [x] Web 门禁 — 2026-07-31 实测：21 passed，TypeScript 无错误，Next 静态导出成功
- [x] Desktop 门禁 — 2026-07-31 实测：27 passed，视觉冒烟、NSIS 构建、安装器隔离与 ASAR 白名单通过
- [x] 响应式浏览器验收 — 2026-07-31：1440×900 与 390×844 各 6 页，无页面横向溢出或裁切控件
## NICE
- [ ] DuckDB 习惯分析有可读视图
- [x] CLI 子命令齐全（pipeline/distill/chat/proactive/serve） — 2026-06-29 验证：14 个子命令（pipeline/distill/chat/proactive/verify/calendar/reminders/speakers/recommend/wiki/status/llm/serve/test）
- [x] API 有基本健康检查 — 2026-06-29 验证：api.py:45 `@app.get("/health")`
