# PRD 讨论记录 — Token 清理 + TencentDB Agent Memory 架构融合

> 日期：2026-08-08 | 输入：planning/requirements.md + 双侧架构调研
> 每条共识格式：`- [x] 议题 | 结论 | 日期`

## A. Token 清理与环境变量化

- [x] A1 后端 token 来源 | 结论：`api_token()` 已支持 PA_API_TOKEN 环境变量优先（config.py:144），无需改后端代码；只需轮换 .env 中的值并清理仓库硬编码 | 2026-08-08
- [x] A2 sdkconfig.defaults.esp32s3 中的 token | 结论：移除 CONFIG_PC_TOKEN/CONFIG_PA_SERVER_TOKEN 两行，改为注释说明"从本地 sdkconfig 覆盖"；真值放 `scripts/xiaozhi-esp32/sdkconfig.local`（加入 .gitignore，不跟踪） | 2026-08-08
- [x] A3 sdkconfig.old 处理 | 结论：直接删除该文件（历史遗留配置快照，无保留价值，且含 token） | 2026-08-08
- [x] A4 tests/test_ws.py 中的 token | 结论：改为读 PA_API_TOKEN 环境变量，缺省时 pytest.skip（网络/集成测试不阻塞 CI） | 2026-08-08
- [x] A5 固件二进制（v29-v37 .bin 含 token） | 结论：保留文件但 token 已随轮换失效；不重写二进制。在 PA-TODO 记录"历史固件包含已失效 token" | 2026-08-08
- [x] A6 git 历史清理 | 结论：本期不做 filter-repo（破坏性大、影响所有克隆）；token 轮换后历史中的值即失效，风险已消除。记录到 PA-TODO 作为可选项 | 2026-08-08
- [x] A7 token 轮换方式 | 结论：用 Python secrets.token_hex(32) 生成新值写入 .env（PA_API_TOKEN）；同步更新 scripts/xiaozhi-esp32/sdkconfig.local；旧 token 立即失效（后端重启后） | 2026-08-08

## B. 记忆架构融合 — 总体策略

- [x] B1 融合方式 | 结论：不部署 Node 版 MemoryCore（技术栈/依赖不符），在 PA Python 栈内复刻其 L0-L3 分层架构与混合召回算法，适配 PA 约束（stdlib+numpy、反幻觉、可插拔） | 2026-08-08
- [x] B2 层级映射 | 结论：L0=segments+chat_log（已有）；L1=memories 表增强；L2=新增 scenes 场景层；L3=persona_versions（保留 9 维 JSON）+ 新增叙事档案 narrative | 2026-08-08
- [x] B3 范围裁剪 | 结论：不做 Memory Hub/Team/ACL/Skill 库/CodeGraph（团队功能超出个人助手范围）；保留 PA 现有 wiki（与场景层互补：wiki=主题知识，scene=情境记忆） | 2026-08-08
- [x] B4 反幻觉约束 | 结论：所有新层必须溯源——L1→segment（已有 bigram 校验）、L2 scene→L1 memory ids、L3 narrative→L1 证据；新增 verify 检查项 | 2026-08-08

## C. L1 原子记忆增强

- [x] C1 memories 表新列 | 结论：增加 `priority INTEGER DEFAULT 50`、`scene_name TEXT DEFAULT ''`、`version INTEGER DEFAULT 0`、`updated_at TEXT`；旧库迁移填默认值 | 2026-08-08
- [x] C2 类型体系 | 结论：保留 PA 现有 6 类（fact/event/preference/intention/emotion/skill），不改为 MemoryCore 的 3 类——PA 类型更细且已有测试依赖；priority 打分规则按类型分档（参照 MemoryCore prompt） | 2026-08-08
- [x] C3 去重机制 | 结论：两阶段——①向量召回 top-5 候选（复用 search_memories）②LLM 批量判决 store/update/merge/skip（新增 [TASK:DEDUP_MEMORIES] prompt + StubLLM 分支）；merge 时 content 合并、priority 取高+10 上限 100、segment_id 保留新者、evidence 合并 | 2026-08-08
- [x] C4 抽取 prompt 增强 | 结论：[TASK:EXTRACT_MEMORIES] 增加 priority 字段输出（0-100，按类型分档规则）；低 priority 丢弃阈值：fact/preference<50、event<60、emotion<40（可配） | 2026-08-08
- [x] C5 去重开关 | 结论：config `memory.dedup_enabled` 默认 true；stub 测试可关 | 2026-08-08

## D. L2 场景层（新增）

- [x] D1 存储形式 | 结论：不用 Markdown 文件（MemoryCore 用文件是给 LLM agent 读写），PA 用 SQLite 表 `scenes`：id/name/summary/body/heat/source_mem_ids(JSON)/created_at/updated_at；body 为 Markdown 文本 | 2026-08-08
- [x] D2 场景结构 | 结论：body 含章节：用户基础信息/核心特征/偏好/核心叙事(Trigger→Action→Result)/演变轨迹/待确认点；单场景 ≤1500 字符 | 2026-08-08
- [x] D3 整合策略 | 结论：LLM 判决 UPDATE(默认)>MERGE>CREATE；容量 maxScenes=15（可配）；≥上限强制 MERGE；heat：新建=1、更新+1、合并=sum+1 | 2026-08-08
- [x] D4 触发时机 | 结论：L1 抽取完成后若新增记忆 ≥ scene_min_memories（默认 10）则触发场景整合；distill 前自动先跑场景整合 | 2026-08-08
- [x] D5 场景 prompt | 结论：新增 [TASK:SCENE_INTEGRATE]，输入=现有场景列表(name+summary+heat)+新增记忆，输出=操作列表 [{action:UPDATE|MERGE|CREATE, ...}]；StubLLM 提供确定性分支 | 2026-08-08
- [x] D6 溯源 | 结论：source_mem_ids 必须全部存在于 memories 表，否则该操作丢弃（verify 检查） | 2026-08-08

## E. L3 Persona 融合

- [x] E1 双形态 | 结论：保留现有 9 维 JSON（persona_versions，供 profile_feedback 叠加与 API 消费）+ 新增叙事档案 narrative（≤2000 字符，供 chat system prompt 注入，更接近 MemoryCore 的 persona.md） | 2026-08-08
- [x] E2 narrative 生成 | 结论：distill 时同步生成——LLM 从 9 维档案+场景导航压缩为叙事体；存 persona_versions.narrative 列（新增）；增量模式（有旧 narrative 时输入旧版+变化摘要） | 2026-08-08
- [x] E3 触发条件 | 结论：沿用现有 last_distill_at 游标+手动触发；新增记忆数阈值 memory.distill_every_n（默认 50，对齐 MemoryCore triggerEveryN）供自动触发判断（cli distill --auto 检查） | 2026-08-08
- [x] E4 场景导航 | 结论：chat system prompt 注入场景导航（name+heat+summary，按 heat 降序），对齐 MemoryCore 的 scene-navigation | 2026-08-08

## F. 混合召回（核心）

- [x] F1 BM25 实现 | 结论：SQLite FTS5 已验证可用（sqlite 3.45.3）；建 memories_fts 虚拟表（content 列），中文用字符 bigram 预分词（无 jieba 依赖）写入 content_fts 列 | 2026-08-08
- [x] F2 混合策略 | 结论：hybrid = BM25 top-N + 向量 top-N → RRF 融合（k=60，score=Σ1/(60+rank+1)）；N = maxResults*3 候选；默认 strategy=hybrid，可切 keyword/embedding | 2026-08-08
- [x] F3 预算控制 | 结论：maxResults=5、scoreThreshold=0.008（RRF 分数域，对应双榜命中基准）、timeoutMs=5000、maxCharsPerMemory=0(不限)、maxTotalChars=2000（可配）；超时/超限截断并标注 | 2026-08-08
- [x] F4 分层注入 chat | 结论：L1 召回结果→user message 前缀（<relevant-memories>，每轮变化）；L3 narrative+场景导航→system prompt（稳定）；对齐 MemoryCore 注入位置 | 2026-08-08
- [x] F5 recall 模块 | 结论：新模块 `personal_assistant/recall.py`：`hybrid_recall(query, k, strategy, budget) -> RecallResult`（含 items/truncated/elapsed_ms/strategy）；chat.py 与 api.py 改调它 | 2026-08-08
- [x] F6 FTS 同步 | 结论：add_memory/update/merge/delete 时同步维护 memories_fts；旧库首次启动全量重建 | 2026-08-08

## G. 配置与接口

- [x] G1 配置块 | 结论：config/default.json 新增 `memory` 块：dedup_enabled/l1_batch_max/priority_drop_thresholds/scene_max/scene_min_memories/distill_every_n/recall{strategy,max_results,score_threshold,timeout_ms,max_total_chars} | 2026-08-08
- [x] G2 CLI | 结论：新增 `cli memory`：status（各层计数/场景列表）/recall <query>（调试召回）/scenes（列表+heat） | 2026-08-08
- [x] G3 API | 结论：新增 GET /memories/recall?q=&k=&strategy=（带预算的混合召回）；/memories 列表端点不变 | 2026-08-08
- [x] G4 StubLLM 扩展 | 结论：新增 [TASK:DEDUP_MEMORIES]、[TASK:SCENE_INTEGRATE]、[TASK:NARRATIVE] 三个确定性分支，保证 stub 全链路可测 | 2026-08-08

## H. 测试与验收

- [x] H1 新增单测 | 结论：tests/test_recall.py（RRF/BM25/预算/超时）、tests/test_scenes.py（整合策略/heat/容量/溯源）、tests/test_l1_dedup.py（四种判决/merge 字段合并） | 2026-08-08
- [x] H2 回归 | 结论：现有 102 passed 全绿不破坏；test_e2e 扩展覆盖 L1 去重→L2 场景→L3 narrative→混合召回全链路 | 2026-08-08
- [x] H3 验收标准 | 结论：全量 pytest 零失败 + e2e stub 链路通过 + cli memory 三子命令可用 + /memories/recall 返回结构正确 | 2026-08-08
- [x] H4 修复循环 | 结论：红→修→绿循环直到零失败，每轮记录到 planning/test-log.md | 2026-08-08

## 待讨论项

（无——所有决策已基于调研与 PA 约束闭环）
