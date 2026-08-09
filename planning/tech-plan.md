# 技术方案：PA 本地多模态 Jarvis 整合

## 架构
PA 保持 Python FastAPI 中枢；新增 `local_omni.py` 负责模型清单/校验和 Worker 生命周期，`native_omni.py` 负责复用 Jarvis v1 命名管道协议；`llm.py` 通过 `MiniCPMOClient` 实现现有 `LLMClient`。感知与全双工优先复用 PA 已有 `/ws/live`、事件广播、课程和记忆落盘边界。

## 文件变更
- 新增 `personal_assistant/local_omni.py`：固定模型文件、大小、SHA-256、路径解析、状态。
- 新增 `personal_assistant/native_omni.py`：Worker 进程/命名管道适配，支持 fake 与 real。
- 修改 `personal_assistant/llm.py`：本地 LLM 工厂与 JSON 聊天。
- 修改 `personal_assistant/config.py`、`config/default.json`：本地模型与 Worker 配置及环境覆盖。
- 修改 `personal_assistant/chat.py`：短期上下文、当前多模态事实、证据返回。
- 修改 `personal_assistant/api.py`：本地状态、启动停止、感知控制端点。
- 修改 `personal_assistant/ws_manager.py`：新增统一事件常量。
- 新增测试覆盖模型管理、协议、工厂、聊天上下文、API 错误和事件。

## 不复制内容
不复制 Jarvis Electron UI、Jarvis 文件 MemoryStore、CourseRepository、ImageGenerationClient、完整 upstream runtime；PA 继续使用自己的 SQLite/DuckDB、课程和 API。

## 实施顺序
1. 模型清单和协议契约测试。
2. fake Worker 与本地 LLM 工厂。
3. real Worker 命名管道/进程生命周期。
4. 聊天短期上下文与证据。
5. 感知/全双工事件映射与 API。
6. 真实环境构建和冒烟。

## 风险
- 官方 v0.1.2 CUDA Worker 已部署到 PA 私有忽略目录；模型固定 revision 和三文件 SHA-256 已验证。
- Windows 命名管道断开、并发启动、失败恢复和 API 资源鉴权已有契约测试。
- RTX 2080 Ti 实测加载显存约 8.4 GiB，停止后恢复约 0.95 GiB 基线；不做 CPU 或云端静默回退。
