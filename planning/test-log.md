# 测试日志 — v0.10 Token 清理 + 记忆架构融合

> 红→修→绿循环记录（PRD N7-03）| 2026-08-08

## 最终结果

**全量 224 passed / 3 skipped / 0 failed**（30s）
- 原 200 回归全绿
- 新增：test_recall 9 · test_scenes 7 · test_l1_dedup 8
- test_e2e 扩展步骤 13a-13e（L1 去重/L2 场景溯源/L3 narrative/混合召回/chat 引用）

## 修复循环记录

### 轮 1：5 failed
- `test_e2e` memories 不足 + distill skip + `sqlite3.OperationalError: invalid fts5 file format`
- `test_minicpm_chat` x3：evidence 缺 m-1
- `test_pluggable` TextDiarizer x1

**根因 1（FTS 损坏）**：`CREATE VIRTUAL TABLE` 在 Python sqlite3 隐式事务中执行，
`%_config` 元数据不落盘 → 表损坏且 DROP 都失败。
**修复**：虚拟表 DDL 强制 autocommit（isolation_level=None）；新增 `_purge_fts`
（writable_schema 删影子表）自愈损坏表；connect() 检测损坏→清除→重开。

**根因 2（priority 过滤）**：StubLLM 抽取不带 priority（默认 50）被 event 阈值 60 过滤。
**修复**：StubLLM._extract 输出真实分档（event 70/preference 75/intention 65/emotion 55）。

### 轮 2：9 failed（新增 omni_api x3）
**根因 3（悬挂事务）**：`_ensure_fts` 的 integrity-check INSERT 遗留未提交事务 →
barrage.py `BEGIN IMMEDIATE` 报 "cannot start a transaction within a transaction"。
**修复**：健康检查改纯 SELECT（不写）。

**根因 4（测试契约）**：测试 monkeypatch `chat.memory.search`，新 respond() 走 recall 绕过了 fake。
**修复**：hybrid 无命中/异常时回落 `memory.search`（生产语义=优雅降级，测试契约保留）。

### 轮 3：1 failed
**根因 5（narrative 覆盖 profile）**：`_system_prompt` narrative 优先跳过了 profile JSON 注入，
测试断言 "安静"（来自 profile）落空。
**修复**：profile JSON 始终注入（含用户纠正），narrative 作补充块并存。

### 轮 4：0 failed ✅

## 新增测试覆盖（24 用例）

| 文件 | 用例 | 覆盖点 |
|------|------|--------|
| test_recall.py | 9 | RRF 数学性质/中文 bigram BM25/双榜加分/预算截断/超时/strategy 切换 |
| test_scenes.py | 7 | CREATE+heat/UPDATE 递增/溯源丢弃假 id/body 截断/容量 MERGE/导航排序/pending 游标 |
| test_l1_dedup.py | 8 | store/skip/merge 三判决/priority 合并规则/非法 action 降级/低分过滤/priority 容错/旧库迁移 |
| test_e2e.py +13a-e | 5 | 重复灌入去重/场景溯源/narrative 长度/召回结构/chat evidence |
