# personal-assistant — 全自动个人助手

> 数据完全本地、24h 被动听你说的一切、自动蒸馏成"数字分身"（人格/习惯/思维/技能/知识），并主动给建议/安抚/推荐的个人 AI 助手。安卓 App + Web 控制端；大脑跑在本地电脑或云服务器。

## 状态
- 阶段：development（用户直导式构建，2026-06-28 启动）
- MVP：深核主干 ASR→记忆→蒸馏→对话→主动；App/Web/推荐 后补。
- 4 项锁定决策见 `planning/status.json` 与 `planning/prd.md`。

## 快速开始
```bash
# 依赖（GPU 盒/常规机器用 venv）：
python3 -m venv .venv && .venv/bin/pip install -r requirements.txt
# 开发盒（无 python3-venv / pip 受限）：直接用系统 python3，依赖已预装
#   numpy duckdb fastapi uvicorn pydantic 已在；其余走 stdlib（无第三方 SDK）

cp config/default.json config/default.json  # 已就绪；按环境改 .env
# 端到端跑一遍（stub 后端，零网络零模型）
python3 -m personal_assistant.cli test
# 真 GLM-5.2（会话代理，本机实测可用）
PA_LLM_BACKEND=anthropic_proxy python3 -m personal_assistant.cli test
python3 -m personal_assistant.cli status      # 看计数 + 人格档案
python3 -m personal_assistant.cli serve       # 起 API (localhost:8000/docs)
```

### 往 inbox 灌入内容
- 把录音转写稿 `.txt`（每行一段）丢进 `data/inbox/`，`cli pipeline --once` 即转片段入库。
- 真音频 `.wav/.mp3`：设 `PA_ASR_BACKEND=faster_whisper`（需 GPU 盒 + HuggingFace 可达）。

## 后端切换（config/default.yaml）
| 组件 | dev（本盒） | prod（GPU 盒） |
|---|---|---|
| ASR | `stub` | `faster_whisper` (large-v3, cuda) |
| LLM | `stub` 或 `anthropic_proxy`（会话代理，实测可用则切） | `ollama` 或 `openai_compat`（真 GLM key） |
| Embedder | `hashing` | `openai_compat`（GLM embedding-3） |

## 架构
```
录音→inbox/ ①watch ②VAD ③ASR ④声纹→ ⑤片段库(SQLite+DuckDB+向量)
→⑥记忆抽取(LLM)→ ⑦蒸馏引擎(反思循环→persona/profile.json 版本化)
→⑧主动触发(关键信息→建议/安抚/推荐→推送) ⑨被动对话(人格+检索)
```
详见 `CLAUDE.md`。

## 许可
MIT
