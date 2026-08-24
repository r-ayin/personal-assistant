# 测试用例

## 测试用例 — Token 清理 + 记忆架构融合（v0.10，进行中）

> 对应 planning/prd.md 验收标准与异常边界表 | 2026-08-08

### 正常流程

#### Token 清理
- [ ] 场景：git grep 旧 token 于跟踪文本文件 → 期望：零命中（bin 除外）
- [ ] 场景：新 PA_API_TOKEN 请求 GET /health（Bearer） → 期望：200
- [ ] 场景：旧 token 请求 API → 期望：401（后端重启后）
- [ ] 场景：test_ws.py 在无 PA_API_TOKEN 环境运行 → 期望：pytest.skip，不计失败

#### L1 去重
- [ ] 场景：灌入含 5 条记忆的转录 → 期望：memories 新增 5 条，均带 priority（0-100）
- [ ] 场景：同一转录二次灌入 → 期望：memories 行数不变（skip 生效），计数报告 skipped≥1
- [ ] 场景：两条 bigram 重叠>0.6 的同 kind 记忆 → 期望：merge 为一条，content 合并、priority=高者+10（≤100）、evidence 并集
- [ ] 场景：update 判决 → 期望：target content 更新、version+1、updated_at 刷新
- [ ] 场景：priority 低于类型阈值（如 emotion=30） → 期望：抽取时丢弃不入库

#### L2 场景
- [ ] 场景：单次灌入 ≥10 条记忆 → 期望：scenes 表生成 ≥1 个场景，heat≥1
- [ ] 场景：二次灌入同主题记忆 → 期望：UPDATE 现有场景，heat+1，scenes_total 不变
- [ ] 场景：场景数达 scene_max 后再触发 → 期望：强制 MERGE，总数回落
- [ ] 场景：场景导航查询 → 期望：按 heat 降序返回

#### L3 Persona
- [ ] 场景：distill 执行成功 → 期望：persona_versions 新版本含非空 narrative（≤2000 字符）
- [ ] 场景：二次 distill（增量模式） → 期望：narrative 保留稳定信息、追加新变化
- [ ] 场景：cli distill --auto 且未处理记忆 < distill_every_n → 期望：skip 并提示

#### 混合召回
- [ ] 场景：查询同时命中 BM25 与向量 → 期望：RRF 分数 > 任一单路分数，sources=[bm25,vector]
- [ ] 场景：纯中文查询（"我喜欢跑步"） → 期望：bigram 分词命中相关记忆
- [ ] 场景：strategy=keyword → 期望：仅 BM25 结果；strategy=embedding → 仅向量结果
- [ ] 场景：chat.respond("...") → 期望：evidence 非空，user 前缀含 <relevant-memories>
- [ ] 场景：GET /memories/recall?q=测试 → 期望：200，返回 items/truncated/elapsed_ms/strategy 结构

#### CLI
- [ ] 场景：cli memory status → 期望：输出 memories/scenes/persona 计数
- [ ] 场景：cli memory recall "测试" → 期望：打印召回列表
- [ ] 场景：cli memory scenes → 期望：场景 name/heat/updated 列表

### 异常与边界（来自 PRD 异常场景表）

- [ ] E1 场景：旧库（无 priority/scene_name/version/updated_at/narrative 列）打开 → 期望：connect() 自动迁移，读写正常，旧数据默认值填充
- [ ] E2 场景：LLM 返回 action="invalid" → 期望：降级 store，记忆不丢失，无异常抛出
- [ ] E3 场景：LLM 返回场景 body 2000 字符 → 期望：截断至 1500 + 尾部标注
- [ ] E4 场景：LLM 返回 narrative 3000 字符 → 期望：截断至 2000
- [ ] E5 场景：删除 memories_fts 表后重启 → 期望：connect() 检测并全量重建，召回正常
- [ ] E6 场景：召回 timeout_ms=1（强制超时） → 期望：返回 RecallResult(truncated=True)，elapsed_ms≥1，不抛异常
- [ ] E7 场景：embedding 维度 256→384 切换后召回 → 期望：回落纯 BM25，结果非空，日志含告警
- [ ] E8 场景：无 PA_API_TOKEN 跑 test_ws.py → 期望：skip（同正常流程第 4 条）
- [ ] E9 场景：新记忆无任何召回候选 → 期望：跳过 LLM 判决直接 store
- [ ] E10 场景：stub 下连续灌入制造 >15 场景 → 期望：MERGE 收敛至 ≤scene_max

### 回归
- [ ] 全量 pytest tests/ --tb=short → 期望：原 102 passed 全绿 + 新增用例全绿，零失败
- [ ] cli test（stub e2e） → 期望：扩展链路（去重→场景→narrative→混合召回）通过

---

## 归档：PA 本地多模态 Jarvis 整合（v0.9，已完成 2026-07-31）

### 正常流程
- [x] 本地模型配置路由：`PA_LLM_BACKEND=minicpm_o` 时工厂返回 MiniCPM-o 客户端。
- [x] 文本聊天：Worker 返回文本时 `Assistant.respond` 返回非空回复和真实 PA 记忆 evidence。
- [x] 短期上下文：连续两轮聊天时第二轮 prompt 包含最近一轮，不包含无限历史。
- [x] 模型清单校验：三个文件大小和 SHA-256 都匹配时校验通过。
- [x] 感知事件：合法 perception JSON 转换为统一 PA 事件并广播。
- [x] 场景稳定：短暂 game/course 误判不会立即切换稳定场景。
- [x] 消息去重：相似助手消息在冷却窗口内只广播一次。
- [x] 课程接入：course_transcript/course_note 进入 PA 现有课程会话和记忆流程。
- [x] 本地模型状态：Worker ready/failed/stopped 映射为可查询状态。

### 异常与边界
- [x] 未知后端：`minicpm_o` 配置缺少 Worker 或模型目录时，工厂/启动返回明确错误，不回退云端。
- [x] 模型文件缺失：缺任一文件时启动被拒绝，并指出模型目录。
- [x] 模型文件损坏：大小正确但 SHA-256 错误时启动被拒绝。
- [x] Worker 未启动：聊天调用按需启动本地 Worker；失败时返回明确错误，不回退云端。
- [x] Worker 超时：请求超时转换为本地模型超时错误，不产生空回复。
- [x] 空回复：空文本被拒绝，不广播空助手消息。
- [x] 非法 perception：非法 JSON、错误类型或越界 confidence 不落盘。
- [x] 恶意数据：屏幕文字、历史上下文中包含 prompt 注入标记时仍作为 JSON 数据传入，不改变系统规则。
- [x] 暂停感知：停止后不再发送采集请求，并清理 Worker 感知状态。
- [x] 真实冒烟：固定模型、CUDA Worker、文本推理、屏幕/系统音频感知、暂停与资源释放均已验证。

### 验证层级
- 单元：模型清单、协议、聊天上下文、场景与去重策略。
- 集成：PA API/WS 使用 fake Worker 验证事件流与错误映射。
- 真实冒烟：Windows + 22 GiB GPU + 固定 Worker + 6.32 GiB 模型，文本、感知、暂停恢复。
