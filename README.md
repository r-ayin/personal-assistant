# personal-assistant — 全自动个人助手

> 数据与编排由 PA 单一后端负责：记忆、课程、助手性格、用户画像、提醒、Web、设备和可选 MiniCPM-o Worker 都归 PA 所有。桌面端只保留透明置顶弹幕壳。

## 状态
- 阶段：完成（PA Web 主界面与桌面弹幕壳已通过回归、浏览器、真实 CUDA、安装器和跨应用协议验证）。
- PA Web 是主界面；页面主动聊天只在页面显示，不转为桌面弹幕。
- MiniCPM-o 由 PA 按 `manual`、`perception`、`chat-backend` consumer 共享一个 Worker；最后一个 consumer 释放后退出。
- 本地模型失败会明确报错，不静默回退云端。

## 快速开始
```bash
# 依赖（GPU 盒/常规机器用 venv）：
python3 -m venv .venv && .venv/bin/pip install -r requirements.txt
# 开发盒（无 python3-venv / pip 受限）：直接用系统 python3，依赖已预装
#   numpy duckdb fastapi uvicorn pydantic 已在；其余走 stdlib（无第三方 SDK）

# 配置 `.env`，至少设置生产环境的 PA_API_TOKEN
# 构建静态 Web；PA 只挂载 web/dist
cd web && npm install && npm run build && cd ..
# 启动唯一 PA API；默认 http://127.0.0.1:8004/web/
python3 -m personal_assistant.cli serve --host 127.0.0.1 --port 8004
# 隔离端到端验证（不启动真实模型）
PA_LLM_BACKEND=stub PA_ASR_BACKEND=stub PA_SPEAKER_BACKEND=text python3 -m personal_assistant.cli test
```

### 本地多模态感知控制
先启动 PA API，再通过 API 控制长期 Worker；CLI/包装器不会单独持有 Worker：

```bash
# Windows（从项目根目录运行）
pa-perception.bat start --token %PA_API_TOKEN%
pa-perception.bat stop --token %PA_API_TOKEN%

# 跨平台等价命令；PA_API_URL 默认 http://127.0.0.1:8004
python -m personal_assistant.cli perception start
python -m personal_assistant.cli perception stop
```

远端或非默认端口可使用 `PA_API_URL` 或 `--base-url`；资源控制 token 来自 `PA_API_TOKEN` 或 `--token`。

### 桌面弹幕壳
Electron 壳位于 `../pub-local-jarvis/desktop`，只连接 PA API/WS，不启动后端、模型或数据库：

```bash
cd ../pub-local-jarvis/desktop
npm install
npm start
```

PA 启动时会把版本化连接信息写入当前用户的 `PersonalAssistant/desktop-connection.json`。Windows 默认位于 `%LOCALAPPDATA%`；可用 `PA_DESKTOP_CONNECTION_FILE` 覆盖路径。Electron 只读该文件，`PA_BASE_URL` 与 `PA_API_TOKEN` 环境变量优先覆盖。Web Token 只使用部署注入的 `window.PA_TOKEN` 或当前标签页的 `sessionStorage`。

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
```text
PA Web / Android / ESP32
    -> PA FastAPI :8004
    -> PA SQLite / DuckDB / 性格版本 / 用户画像反馈
    -> OmniService -> 0 或 1 个 MiniCPM-o Worker

PA Desktop Overlay
    -> /ws/live?client=overlay&version=1
    -> 只接收 hello / barrage / barrage_settings
    -> 不启动后端、模型或数据库
```
助手性格与自动蒸馏的用户画像独立存储、独立版本化。统一弹幕由 PA 生成，壳只负责过期/优先级队列和显示。

## 许可
MIT
