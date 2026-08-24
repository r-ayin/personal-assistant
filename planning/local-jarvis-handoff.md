# PA 本地 Jarvis 整合开发交接记录

## 模式
- 模式：serial run
- 控制器：主会话
- Worker：按功能块串行执行，先读本文件，不回退其他改动

## 源文档
- `planning/requirements.md`
- `planning/prd.md`
- `planning/test-cases.md`
- `planning/tech-plan.md`
- `../pub-local-jarvis/PROJECT_OVERVIEW.md`
- `../pub-local-jarvis/third_party/runtime/INTEGRATION.md`
- `CLAUDE.md`、`GATES.md`

## 不可违反约束
- PA 是唯一个人助手中枢；不引入第二套 memory/course/API。
- 本地模型不可用时不静默切云端。
- 模型权重不进 Git；上游 runtime 版本必须按 Jarvis VENDOR.json 固定。
- 不安装或恢复已禁用的 Studio Hook、SessionStart Hook、定时心跳和 decision log。
- 不回退用户已有未提交改动。

## Worker 顺序
1. ModelContract：模型清单、哈希校验、配置、契约测试。
2. NativeAdapter：fake/real Worker 协议、生命周期、错误映射。
3. ChatIntegration：本地 LLM 工厂、人格/记忆/evidence/短上下文。
4. PerceptionAPI：事件映射、感知控制、API/WS、回归测试。
5. Verification：主会话运行全量测试、真实冒烟或记录阻塞。

## 执行日志
| 日期 | Worker | 改动 | 验证 | 风险/下一步 |
|---|---|---|---|---|
| 2026-07-30 | Controller | 完成能力对比与设计批准；发现本机 RTX 2080 Ti 22.5 GiB，但无 Worker/模型产物 | 已读取 Jarvis 模型清单、VENDOR、协议和 PA 基线 | 先实现契约层，再构建真实 Worker |
| 2026-07-30 | ModelContract / Controller | 新增 `local_omni.py`、本地模型配置和 `test_local_omni.py`；Worker 通道证书失败后由控制器按同一 TDD 契约接管 | RED: ImportError；GREEN: `python -m pytest tests/test_local_omni.py -q` → 4 passed | 下一步实现 protocol v1 和 Worker 生命周期；模型/二进制仍未下载 |
| 2026-07-30 | NativeAdapter / Controller | 新增 protocol v1、显式 fake client、Windows named-pipe client 与 Worker Manager；Agent 上游 HTTP 400 后控制器接管已有 RED 测试 | RED: ModuleNotFoundError；GREEN: `python -m pytest tests/test_native_omni.py -q` → 11 passed | 下一步实现后台 runtime service、本地 LLM 工厂和聊天上下文 |
| 2026-07-30 | ChatIntegration / Controller | 新增 `MiniCPMOLLM`、最多 4 轮进程内短期上下文、PA 人格/记忆/evidence 合并与模型控制标记清洗 | `test_minicpm_chat.py` 5 passed | 长期事实仍只由 PA memory/evidence 管理 |
| 2026-07-30 | PerceptionAPI / Controller | 新增场景证据校验、稳定/去重、课程 inbox、PA memory 写入、API/WS 事件桥和受 Bearer 保护的资源控制端点 | Omni 专项最终 46 passed | 不迁 Electron UI；事件供现有 Web/Android/ESP32 消费 |
| 2026-07-30 | Runtime / Controller | 部署官方 v0.1.2 私有 CUDA runtime；下载固定 revision 三份权重并逐个验证 SHA-256；CLI 支持状态、缓存命中和 HTTP Range 断点下载 | runtime self-test 通过；模型总计 6,781,995,488 bytes | runtime/模型均在 `.gitignore`，不进 Git |
| 2026-07-30 | Verification / Controller | 真实 API 热切换到 `minicpm_o`，完成文本推理、屏幕/系统音频感知启停、鉴权和 Worker 释放 | 回复“PA API 本地模型正常。”；显存约 956 → 8428 → 949 MiB；最终回归 146 passed, 5 skipped | `test_real_backends.py` 的云 ASR 下载由 `PA_SKIP_REAL_BACKENDS=1` 显式跳过；MiniCPM-o 已单独真实验证 |
| 2026-07-30 | Review / Controller | 修复并发双 Worker、断管 pending 悬挂、fatal 状态不诚实、失败隐式重启、感知 stop 反向启动、匿名 GPU 资源控制、CLI 孤儿进程与下载分片残留 | 对应 RED/GREEN 契约均通过；最终无 Worker 进程残留 | 独立 reviewer 通道因 `401 invalid x-api-key` 未产出结论，已完成内联审查与实物复验 |
| 2026-07-30 | PerceptionCLI / Controller | 保留最近 5 分钟感知注入并返回 `perception:*` evidence；新增 `perception start/stop` HTTP CLI 和 CMD 包装器 | 聚焦 23 passed；全量 154 passed, 5 skipped；Windows 包装器真实 stop 返回模型仍 stopped | CLI 只控制已运行 PA API，不创建或持有 Worker；`PA_API_URL`/`PA_API_TOKEN` 可覆盖 |
| 2026-07-31 | PA Web / Overlay / Controller | PA Web 切为 Today 主界面；新增独立助手性格、画像纠正、统一弹幕、WS role；Electron 删除桌宠与独立后端，只读 PA 发布的连接契约 | PA 200 passed/3 skipped；Web 21 passed + typecheck/build；Desktop 27 passed；浏览器 1440×900/390×844 各 6 页通过 | overlay 传输层只允许 barrage/settings；Web token 只在 window 注入或 sessionStorage |
| 2026-07-31 | Final Verification / Controller | 完成真实 Electron、WS、CUDA Worker 所有权、安装器和认证边界验收 | page 收到 chat_reply 而 overlay 未收到；quiet/pause 409；version 2 为 1008；显存 3222→10710→3165 MiB；安装器 SHA-256 b7fc95fb3f9a9583c5a306bc998646f153e2beb8d825fec4b3639059d4b6fa36 | 最终只保留 PA API 常驻，Worker/overlay 均停止；外部 reviewer 403 未产出结果，主会话完成内联复审 |

## Codebase Patterns
- PA LLM 通过 `LLMClient.chat(system,user)` 抽象，所有后端由 `get_llm()` 路由。
- PA WS 事件统一使用 `{type,data,ts}`，由 `ws_manager.manager.broadcast` 推送。
- PA 的时间、记忆 evidence 和课程落盘必须由确定性代码负责。
- Jarvis 模型三文件固定 revision `502eec5b03eaee9d0d2ce17a176e3490103c9a63`；Worker upstream revision `b9d15b83ee353b2eaeee4d9318c98a35a1347486`。
