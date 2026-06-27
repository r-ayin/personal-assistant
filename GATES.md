# personal-assistant — 质量门禁

## CRITICAL
- [ ] stub 后端端到端跑通：pipeline→distill→chat→proactive 全链路无异常
- [ ] 可插拔接口单测：stub/real 后端互换不影响管线
- [ ] 蒸馏产出 persona/profile.json 合法 JSON + 带证据引用 + 版本化
- [ ] 数据全本地：无任何外发（LLM/ASR 调用除外，且可切本地）

## IMPORTANT
- [ ] pytest 全绿
- [ ] .env 不入 git（.gitignore 覆盖）
- [ ] faster-whisper 真后端类 lazy import（dev 无该包不崩）
- [ ] 主动触发有证据引用（哪条记忆触发、为何）

## NICE
- [ ] DuckDB 习惯分析有可读视图
- [ ] CLI 子命令齐全（pipeline/distill/chat/proactive/serve）
- [ ] API 有基本健康检查
