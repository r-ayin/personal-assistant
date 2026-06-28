# PRD — LLM 可插拔配置增强（v0.5）

> 2026-06-28。把 LLM 后端做成可自定义配置：model / 上下文窗口 / 输出 max_tokens / 思考程度(off·低·中·高) / API(base_url) / key，全局覆盖当前激活后端，对齐 `cli llm`，并为前端设置面板提供回接端点。

## 背景
- 现状：`llm.py` 的 model/base_url/api_key 三后端已可配，但 `max_tokens` 硬编码 4096，**思考程度完全没有**。前端设置面板（v1.1+ 设计文档）依赖后端 5 旋钮 + 3 个尚不存在的端点。
- 调研：已查 4 家 provider 官方文档（workflow w5pz1agsk），思考字段映射依实测，不捏造。

## 用户价值
- 一处改 LLM 全旋钮（前端表单或 `cli llm`），即时作用于当前激活后端。
- 思考程度档位 off/低/中/高，按 provider 原生字段翻译；前端只发档位，不编造 budget。
- 前端可查看/设置生效配置 + 上传转录，回接即用。

## 锁定设计
1. **5 旋钮**：model、context_window（输入窗口，信息性+供前端展示）、max_tokens（输出上限）、thinking_effort(off/低/中/高)、base_url、api_key。
2. **全局覆盖层**：`config.set_override` 运行态覆盖；`get()` 先查覆盖再查 CONFIG；`get_llm()` 每后端字段回落到 `llm.*` 全局默认。
3. **思考程度→原生字段**（已查官方文档）：
   - **GLM openai_compat**：`thinking:{type:"enabled"|"disabled"}`，仅开/关，低/中/高塌缩为"开"（默认思考开，off 须显式 disable）。
   - **GLM anthropic 端点**(`open.bigmodel.cn/api/anthropic`)：`thinking:{type:"enabled",budget_tokens:N}`，可分低/中/高（budget min 1024, < max_tokens）。
   - **OpenAI o 系**：`reasoning_effort:"low"|"medium"|"high"`；推理模型改发 `max_completion_tokens`（非 max_tokens），温度置 1。
   - **Qwen3**：`enable_thinking:true|false` + `thinking_budget:N`（urllib 顶层字段）。
   - **Anthropic Claude**：`thinking:{type:"enabled",budget_tokens:N}`（min 1024, < max_tokens）；Opus4.7+ 仅 adaptive（按 model 名注释标注）。
   - budget 映射：低4096/中12288/高24576，均 `min(budget, max_tokens-1024)` 且 ≥1024。
4. **新增 `glm_anthropic` 后端**：AnthropicProxyLLM 指向 GLM anthropic 端点，使 GLM 也能分低/中/高。
5. **env 覆盖**：`PA_LLM_MAX_TOKENS`/`PA_LLM_THINKING`/`PA_LLM_THINKING_FORMAT` 注入激活后端（同 `PA_LLM_BACKEND` 模式）。

## 范围
- 改：`llm.py`、`config.py`、`config/default.json`、`cli.py`、`api.py`。
- 新增：`tests/test_llm_config.py`、`planning/frontend-design.md`、本 PRD。
- 更新：`PROGRESS.md`、`planning/status.json`。

## 新端点（前端依赖）
- `GET /settings/llm`：生效配置（key 掩码）+ native thinking 字段预览。
- `POST /settings/llm`：写运行态覆盖（body 含 5 旋钮 + backend）。
- `POST /inbox/upload`：multipart 转录文件→`data/inbox/`。

## 反幻觉与诚实
- 思考字段映射严格按官方文档；budget 具体上限随型号变动，代码注释标注"以官方文档为准"。
- `cli llm` / `GET /settings/llm` 永不明文回显 key（掩码前4…后4）。

## 非目标
- 真 ASR/embedding/本地 LLM 验证（留 GPU 盒）。
- 前端代码实现（用户去别处建）。
- 人格 LoRA、多说话人关系建模。

## 验收
- `cli test` stub 全链路 PASS + 反幻觉断言通过（无回归）。
- `cli llm` 输出含 5 旋钮 + key 掩码。
- `tests/test_llm_config.py` 全绿：openai/glm/qwen/anthropic/off 各档位字段与调研一致；`set_override` 后 `get_llm()` 生效。
- `planning/frontend-design.md` §6.11 与后端实现对齐。

## 流程
pipeline-gate：本 PRD（prd 步）→ dev（编码）→ verify（cli test + 单测）→ done（更新 PROGRESS/status）。
