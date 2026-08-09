# PRD — Token 清理 + TencentDB Agent Memory 架构融合（v0.10）

> 来源：planning/prd-decisions.md（40 条决策）+ planning/requirements.md
> 日期：2026-08-08 | 状态：待确认（Step 2a）

## §0 总纲

**目标**：①清除仓库硬编码 token、统一环境变量配置；②在 PA Python 栈内复刻 TencentDB Agent Memory 的 L0-L3 分层记忆架构 + BM25/向量/RRF 混合召回，保留 PA 反幻觉硬约束与可插拔设计。

**层级映射**（决策 B2）：

| 层 | MemoryCore | PA 落地 |
|----|-----------|---------|
| L0 | 对话 JSONL | segments + chat_log（已有，不动） |
| L1 | 原子记忆+去重 | memories 表 + priority/scene_name/version + 两阶段去重 |
| L2 | 场景块 Markdown+heat | scenes 表（SQLite）+ heat + 整合管线 |
| L3 | persona.md | persona_versions 9 维 JSON + narrative 叙事列 |
| 召回 | FTS5 BM25+vec+RRF | memories_fts + numpy 余弦 + RRF(k=60) + 预算 |

**不做**（决策 B3）：Memory Hub/Team/ACL/Skill 库/CodeGraph；不引入新 pip 依赖。

---

## §1 节点 1：Token 清理与环境变量化（P0，无依赖）

- **N1-01** 清理 sdkconfig.defaults.esp32s3：删除 CONFIG_PC_TOKEN / CONFIG_PA_SERVER_TOKEN 两行，替换为注释"Token 从本地 sdkconfig.local 覆盖（不入库）"；保留 IP/URL（非机密）。
- **N1-02** 新建 `scripts/xiaozhi-esp32/sdkconfig.local`（含当前真 token），加入 .gitignore；固件 README 补"本地 token 配置"说明。
- **N1-03** `git rm scripts/xiaozhi-esp32/sdkconfig.old`（历史快照含 token，无保留价值）。
- **N1-04** tests/test_ws.py：TOKEN 改读 PA_API_TOKEN 环境变量，缺省 pytest.skip。
- **N1-05** token 轮换：secrets.token_hex(32) 生成新值 → 更新 .env 的 PA_API_TOKEN 与 sdkconfig.local；后端重启生效（api_token() 已支持环境变量优先，config.py:144）。
- **N1-06** PA-TODO.md 追加 P3 项：git 历史 filter-repo 清理（可选，token 轮换后已失效）+ 历史固件 bin 备注。

**验收**：`git grep <旧token>` 跟踪文本零命中（bin 除外）；新 token Bearer 鉴权通过；test_ws.py 无 token 时 skip。

---

## §2 节点 2：L1 原子记忆增强（P0）

- **N2-01** memories 表迁移（storage.py，参照 chat_log.evidence 迁移模式）：新增 `priority INTEGER DEFAULT 50`、`scene_name TEXT DEFAULT ''`、`version INTEGER DEFAULT 0`、`updated_at TEXT DEFAULT ''` 四列，connect() 自动 ALTER。
- **N2-02** 抽取增强（memory.py）：SYSTEM_EXTRACT 增加 priority 输出（0-100 按类型分档）；坏值修复为 50；config `memory.priority_drop_thresholds` 过滤低分（默认 fact:50/event:60/emotion:40/preference:50/intention:50/skill:50）。
- **N2-03** 两阶段去重 `memory.dedup_and_store(new_mems, embedder, llm) -> dict`：
  - 阶段1：每条新记忆向量召回 top-5 候选（复用 search_memories）
  - 阶段2：llm.chat_json([TASK:DEDUP_MEMORIES]) 批量判决 store/update/merge/skip
  - 执行：update=改 target content+version+1；merge=content 合并+priority 取高+10(≤100)+evidence 并集；skip=丢弃
  - 返回 {"stored","updated","merged","skipped"} 计数
  - 非法 action 降级 store（宁可重复不漏存）；候选为空跳过判决全部 store
  - config `memory.dedup_enabled` 默认 true
- **N2-04** ingest._memory_step 改调 dedup_and_store，计数进 ingest 结果。
- **StubLLM** [TASK:DEDUP_MEMORIES] 分支：content 完全相同→skip；bigram 重叠>0.6 且同 kind→merge；否则 store（确定性）。

**验收**：重复灌同一转录两次 memories 不增；merge priority 正确；旧库自动迁移。

---

## §3 节点 3：L2 场景层（P1，依赖节点 2）

- **N3-01** scenes 表：`id/name/summary/body/heat/source_mem_ids(JSON)/created_at/updated_at`；配套 scenes_all/scene_get/scene_upsert/scene_delete/scene_add_heat。
- **N3-02** 新模块 `scenes.py`：`integrate(new_mem_ids, llm=None) -> dict`
  - 输入：现有场景(name/summary/heat) + 新记忆(kind/content/priority)
  - [TASK:SCENE_INTEGRATE] LLM 判决操作列表 [{action: UPDATE|MERGE|CREATE, ...}]
  - 策略：UPDATE 默认优先；容量 ≥scene_max(15) 强制 MERGE；heat 新建=1/更新+1/合并=sum+1
  - 溯源：source_mem_ids 必须全部存在 memories 表，否则丢弃该操作
  - body ≤1500 字符截断；返回 {"created","updated","merged","scenes_total"}
- **N3-03** 触发：ingest 新增 _scene_step（新增记忆 ≥scene_min_memories(10) 时，verify 前执行）；distill.run() 前自动 integrate 未处理记忆。
- **StubLLM** [TASK:SCENE_INTEGRATE] 分支：按 kind 聚合到"日常记录/偏好画像/事件追踪"三固定场景，内建容量 MERGE 逻辑保证确定性收敛。

**验收**：灌 ≥10 条记忆后 scenes 非空；容量超限 MERGE；溯源全部有效；heat 递增正确。

---

## §4 节点 4：L3 Persona 融合（P1，依赖节点 3）

- **N4-01** persona_versions 增加 `narrative TEXT DEFAULT ''` 列；save_persona_version(profile, change, narrative="") 向后兼容。
- **N4-02** distill 完成后生成 narrative：[TASK:NARRATIVE] 输入=9 维档案+场景导航，输出 ≤2000 字符叙事体；增量模式（有旧 narrative 时输入旧版保留稳定信息）；超长截断。
- **N4-03** config `memory.distill_every_n`(50)；`cli distill --auto` 未处理记忆数 ≥ 阈值才执行。
- **N4-04** chat._system_prompt 注入场景导航（heat 降序，`🔥 场景名 — summary`，heat≥50 加火焰分级），置于用户画像后。
- **StubLLM** [TASK:NARRATIVE] 分支：从档案确定性拼装。

**验收**：distill 后 narrative 非空 ≤2000 字符；chat system 含场景导航；--auto 阈值正确。

---

## §5 节点 5：混合召回（P0 核心，依赖节点 2）

- **N5-01** FTS 索引（storage.py）：`memories_fts` FTS5 虚拟表（content/content_original UNINDEXED/mem_id UNINDEXED）；`_tokenize_zh(text)` 字符 bigram 空格连接（中文）+ 拉丁词保留；add/update/delete 同步维护；connect() 检测空表全量重建。
- **N5-02** 新模块 `recall.py`：
  - `bm25_search(query, k)` — FTS5 MATCH + bm25() 排序（查询同样 bigram 分词）
  - `vector_search(query, k, embedder)` — 复用 storage.search_memories
  - `rrf_fuse(lists, k=60)` — score=Σ1/(60+rank+1)，双榜命中相加
  - `hybrid_recall(query, k=5, strategy="hybrid", embedder=None, budget=None) -> RecallResult`
  - RecallResult: items[{memory,score,sources}] / truncated / elapsed_ms / strategy
  - 候选 k*3 → 双路 → RRF → 阈值过滤 → 预算截断（条数/总字符/超时 monotonic 检查）
  - embedding 维度不匹配时回落纯 BM25 + 日志告警
- **N5-03** chat.respond() 改调 hybrid_recall；L1 结果注入 user message 前缀 `<relevant-memories>`；system 保持 narrative+画像+场景导航（稳定层）；evidence 收集适配新结构。
- **N5-04** API `GET /memories/recall?q=&k=5&strategy=hybrid`（Bearer 鉴权）→ RecallResult JSON。

**预算默认**：score_threshold=0.008（RRF 域）、timeout_ms=5000、max_total_chars=2000；截断标注 `…(已截断)`。

**验收**：双榜命中分 > 单榜；预算截断生效；超时返回结构化结果；chat evidence 非空。

---

## §6 节点 6：配置与 CLI（P1，随各节点落地）

- **N6-01** config/default.json 新增 `memory` 块：dedup_enabled/l1_batch_max/priority_drop_thresholds/scene_max/scene_min_memories/distill_every_n/recall{strategy,max_results,score_threshold,timeout_ms,max_total_chars}。
- **N6-02** `cli memory` 子命令：status（各层计数+最近更新）/ recall <query> [--k --strategy]（调试）/ scenes（列表+heat）。
- **N6-03** StubLLM 三分支（[TASK:DEDUP_MEMORIES]/[TASK:SCENE_INTEGRATE]/[TASK:NARRATIVE]）随节点 2/3/4 落地。

---

## §7 节点 7：测试与验收（P0，贯穿）

- **N7-01** 新增测试：
  - tests/test_recall.py — RRF 数学性质、BM25 中文命中、预算截断、超时路径、strategy 切换
  - tests/test_scenes.py — UPDATE/MERGE/CREATE 策略、heat、容量强制 MERGE、溯源丢弃
  - tests/test_l1_dedup.py — 四判决、priority 合并、旧库迁移
- **N7-02** 现有 102 passed 全绿；test_e2e.py 扩展全链路（灌转录→去重→场景→distill+narrative→hybrid_recall→chat 引用）。
- **N7-03** 红→修→绿循环直到 `pytest tests/ --tb=short` 零失败，每轮记录 planning/test-log.md。

**最终验收**：全量零失败 + e2e 通过 + cli memory 三子命令可用 + /memories/recall 正确 + token 零硬编码。

---

## 异常与边界

| # | 场景 | 处理 |
|---|------|------|
| E1 | 旧库无新列（priority/narrative） | connect() 自动 ALTER 迁移，默认值填充 |
| E2 | LLM 去重判决返回非法 action | 降级为 store（宁可重复不漏存） |
| E3 | 场景 body >1500 字符 | 截断 + 尾部标注 |
| E4 | narrative >2000 字符 | 截断 |
| E5 | FTS 表损坏/缺失 | connect() 检测重建 |
| E6 | 召回超时 | 返回已得结果 + truncated=True + elapsed_ms |
| E7 | embedding 维度变更（换后端） | 向量检索回落纯 BM25，日志告警 |
| E8 | 无 PA_API_TOKEN 时 test_ws.py | pytest.skip 不 fail |
| E9 | dedup 候选召回为空 | 跳过 LLM 判决全部 store |
| E10 | stub 下场景数超容量 | StubLLM 分支内建 MERGE 逻辑确定性收敛 |
