# personal-assistant — 进度

> 直导式构建（2026-06-28 启动）。MVP 深核主干：ASR→记忆→蒸馏→对话→主动。

## 当前状态（2026-06-28）
- ✅ **深核 MVP 端到端跑通**（开发盒）：
  - stub 后端全链路 PASS；**真 GLM-5.2（会话代理）LLM 全链路 PASS**——蒸馏/对话/主动干预产出高质量、证据落地结果。
  - ASR 用 stub（读 .txt 转录稿；faster-whisper 真后端写齐，GPU 盒+HF 可用时切）。
  - 全本地存储：SQLite(片段/记忆/人格版本/干预) + DuckDB(时段统计) + data/persona/profile.json。
- 可插拔架构经实测：`PA_LLM_BACKEND=anthropic_proxy` 一键切真 LLM，管线无改动。
- API(FastAPI) 路由齐全：/health /ingest /segments /memories /profile /chat /distill /triggers。

## 阶段
- [x] **Phase 0** 脚手架 + ASR 接口(stub+faster_whisper lazy) + 后端骨架
- [x] **Phase 1** 接入(轮询 watch)→ASR→片段库(SQLite+DuckDB)
- [x] **Phase 2** 记忆抽取(LLM) + 入库(embedding) + 余弦检索
- [x] **Phase 3** 蒸馏引擎 + 人格档案（反思循环、证据引用、版本化）
- [x] **Phase 4** 被动对话（人格档案 + 检索）
- [x] **Phase 5** 主动触发引擎（intention_reminder/emotional_support/topic_pattern → 干预 → CLI/日志）
- [ ] 后补（v1.1+）：推荐深化 / 安卓 App / Web 控制端 / pyannote 多说话人 / faster-whisper 真模型(GPU 盒)

## 实测命令
```bash
python3 -m personal_assistant.cli test                              # stub 全链路
PA_LLM_BACKEND=anthropic_proxy python3 -m personal_assistant.cli test  # 真 GLM-5.2 全链路
python3 -m personal_assistant.cli status                            # 看计数+档案
python3 -m personal_assistant.cli serve                             # 起 API
```

## 纪律
- 直导式构建，直提本项目 main（autonomous gate 已解除）。
- 真后端验证留 GPU 盒（本机无 GPU/HF；会话代理 LLM 已实测可用）。
