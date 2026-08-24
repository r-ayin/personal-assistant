# 需求分析：Token 清理 + TencentDB Agent Memory 架构融合

> 日期：2026-08-08 | 来源：用户目标（/goal）| Studio 管线阶段：需求

## 一、用户原始需求

1. **清理 token 并配置环境变量**：清除仓库中硬编码的 API token，统一走环境变量配置。
2. **全面融合 TencentDB-Agent-Memory 记忆架构**：将腾讯开源的 L0-L3 分层记忆架构融入 PA。
3. **使用 studio 模式**：走完整管线（需求→PRD→开发→验证→评审→归档）。
4. **融入后测试，修复-测试循环直到完全无问题**。

## 二、调研结论

### 2.1 目标架构（TencentDB Agent Memory / MemoryCore）

已克隆至 /tmp/tencentdb-agent-memory（75M，通过本地 Clash 代理 7897）。核心设计：

| 层 | 内容 | 关键机制 |
|----|------|---------|
| L0 Conversation | 原始对话，按日 JSONL 分片 | append-only，增量捕获（位置切片+时间戳游标） |
| L1 Atom | 原子记忆（persona/episodic/instruction 等类型） | LLM 抽取+两阶段去重（向量/FTS 候选召回→LLM 判决 store/update/merge/skip），priority 0-100 |
| L2 Scenario | 场景块 Markdown（META+heat） | LLM agent 整合，UPDATE>MERGE>CREATE，容量上限 15，heat 强化信号 |
| L3 Persona | 长期画像（≤2000 字符） | 四层深度扫描，增量/全量重写，L2 带外信号触发 |
| 召回 | BM25 + 向量 + RRF(k=60) 混合 | 分层注入：L3+场景导航进 system，L1 结果进 user 前缀；预算：5 条/阈值 0.3/超时 5s |

生命周期：无遗忘曲线；遗忘=TTL 清理（默认关）；整合=L1 merge + L2 MERGE/heat + L3 重写。

### 2.2 PA 现状基线

| PA 现有 | 对应层级 | 差距 |
|---------|---------|------|
| segments 表 | ≈L0 | 无按日分片，无增量游标 |
| memories 表（6 类） | ≈L1 | 无 priority/scene_name/version；无去重整合 |
| wiki_pages | ≈L2（主题维度） | 无场景概念、无 heat |
| persona_versions（9 维 JSON） | ≈L3 | 结构不同（JSON vs 叙事档案），无触发链 |
| search_memories 全量余弦 | 召回 | 无 BM25/RRF 混合，无预算控制，无分层注入 |

### 2.3 环境约束（CLAUDE.md）

- 无 GPU/torch；pip 装不了新包 → 只能用 stdlib + numpy/duckdb/fastapi/uvicorn/pydantic
- 无法使用 SQLite FTS5 扩展不确定（需验证 Python sqlite3 是否带 FTS5）；无 jieba（用字符 ngram 替代）
- 反幻觉是硬约束：新记忆层须通过 bigram 溯源 grounding
- 会话代理 127.0.0.1:58597 可作真 LLM

### 2.4 Token 现状

- 跟踪文件 4 处文本 token：sdkconfig.defaults.esp32s3(2)、sdkconfig.old(1)、tests/test_ws.py(1)
- 9 个固件 .bin 二进制含 token（v29-v37）
- git 历史多处（含已提交）
- 后端已有环境变量机制：`api_token()` 读 PA_API_TOKEN → config api.token → 空串；.env 已有 PA_API_TOKEN

## 三、需求拆分

### R1: Token 清理与环境变量化（独立、低风险）
- R1.1 跟踪文件 token 替换为占位符/环境变量引用
- R1.2 固件构建走本地未跟踪 sdkconfig（含真 token），defaults 模板不含 token
- R1.3 测试改读环境变量（缺省跳过或用测试 token）
- R1.4 轮换 token（.env 重新生成）
- R1.5 评估 git 历史清理（filter-repo）——仓库无远程则低风险
- R1.6 固件二进制归档评估（含旧 token 的 .bin 是否保留）

### R2: 记忆架构融合（复杂、核心）
- R2.1 **L0 增强**：对话历史持久化（chat_log 已有，补 L0 增量捕获语义）
- R2.2 **L1 增强**：memories 表加 priority/scene_name/version 列；两阶段去重（向量候选+LLM 判决）；类型映射（现有 6 类保留，增加 priority 打分）
- R2.3 **L2 场景层**：新增 scene_blocks（Markdown+META+heat），场景整合管线（UPDATE>MERGE>CREATE），容量控制
- R2.4 **L3 融合**：persona 增加叙事档案输出（与现有 9 维 JSON 并存），触发条件链
- R2.5 **混合召回**：BM25（Python 纯实现或 sqlite FTS5 若可用）+ 向量 + RRF(k=60)；预算控制（条数/字符/超时）；分层注入 chat prompt
- R2.6 **反幻觉适配**：新层（scene/persona 叙事）溯源到 L1→segments
- R2.7 **配置项**：memory.* 配置块（触发阈值/召回参数/场景容量）
- R2.8 **CLI/API**：cli memory 子命令（status/recall/scenes）；API /memories/recall

### R3: 测试与质量门
- R3.1 新模块单测（L1 去重/L2 整合/RRF 召回/预算）
- R3.2 全量回归 102 passed 不破坏
- R3.3 e2e 扩展：分层管线 stub 全链路
- R3.4 修复-测试循环直到零失败

## 四、非目标（明确不做）

- 不部署 MemoryCore Node 服务（技术栈不符、依赖不可装）
- 不实现 Memory Hub/Team/ACL/CodeGraph/Skill 库（团队功能，超出个人助手范围）
- 不实现 Wiki ingest/CodeGraph sync（PA 已有 wiki）
- 不引入新 pip 依赖

## 五、风险

| 风险 | 缓解 |
|------|------|
| Python sqlite3 无 FTS5 | 先验证；无则纯 Python BM25（numpy 实现） |
| stub LLM 无法模拟复杂去重判决 | StubLLM 增加 [TASK:DEDUP_MEMORIES] 分支 |
| 现有 102 测试回归 | 每步改动后跑全量 |
| embedding 后端切换维度不兼容 | memories 表加 embed_dim 元数据标记 |
