# personal-assistant — 进度

> 直导式构建。v0.1 深核主干；v0.2 说话人/日历/提醒/反幻觉；v0.3 推荐联网搜索；v0.4 个人 wiki；v0.5 LLM 可配 + 前端设计文档；v0.6 安卓 App；v0.7 DeepSeek 后端；v0.8 ESP32-S3 双模式固件 + /ws/audio 管线；Web 面板 Next.js 化；真 ASR/声纹后端就绪；v0.10 TencentDB Agent Memory 架构融合。

## 当前状态（2026-08-11）
### v0.11 实时语音应答增强（进行中，实体设备已刷写并联通）
- ✅ 服务端 turn 状态机定型：`idle→listening→recognizing→thinking→speaking`，单调 `turn_id` + generation guard 可取消 turn；LLM 解包契约修复（`AssistantResponse` 对象解包，600-604 行）。
- ✅ 服务端 VAD 自适应：噪声基线（前 16 帧 sorted[2]×1.8，钳位 12k）+ 宽容积分（语音帧 -2 / 静音帧 +1，连续 8 帧≈480ms 切段）+ 满帧保险 8s（原 15s，防噪声环境拖满）。
- ✅ 固件自定义唤醒词「江江」：sdkconfig 重建启用 MultiNet6（`CONFIG_SR_MN_CN_MULTINET6_QUANT=y`）+ `CustomWakeWord::Initialize` 命令集补齐注入；boot 日志实测 `Command: jiang jiang`。已刷写 ota_0。
- ✅ 固件 Wi-Fi PSM 关停：音频服务运行期 `WIFI_PS_NONE`（Stop 恢复 `MIN_MODEM`），消除音频攒发；已刷写。
- ✅ 语音响应提速（08-09 ~ 08-11，服务端）：
  - LLM 限长：`get_llm(max_tokens=None)` 覆盖参数 + 音箱通道 `_voice_llm()` 限 160 tokens（此前实测一 turn llm_ms=35s，回复被拉满 4096）；
  - ASR：medium→small + beam/best_of 5→1 贪心解码（调用处接入配置）；small 模型 3.7s 预热。
- ✅ 服务 8004 已重启上线（PID 42332）：small 模型加载、设备 `/ws/audio` 重连、ASR 预热完成。
- ✅ 测试：`tests/test_xiaozhi_session.py` 12/12 通过（可取消 turn / 终态 / VAD 切段 / 协议边界）。
- ⏳ 待办：真机复测分段时延（asr_ms / llm_ms / tts_ms，目标 EOU→STT p95≤2s、STT→首Opus p95≤4s）；08-09 日志观测到一轮 15s 满帧空 ASR（环境噪声无 480ms 静音）→ 已用 8s 保险缓解，待复测确认；Type-C 耳机输出不可用（板无 DAC/codec），输出方案评估：外接 I2S DAC/功放（零代码）或固件新增 USB UAC device（新开发）。
- ✅ v0.10 Token 清理与环境变量化：跟踪文件硬编码清零，PA_API_TOKEN 轮换（旧值失效），固件 token 走 sdkconfig.local（gitignore）/ 云编译 secrets.PA_WS_TOKEN。
- ✅ v0.10 记忆架构融合（复刻 TencentDB-Agent-Memory L0-L3 + 混合召回，Python 栈落地）：
  - L1 两阶段去重：priority 分档 + 向量候选 top-5 + LLM 判决 store/update/merge/skip
  - L2 scenes 场景层：UPDATE>MERGE>CREATE + heat 强化 + 容量 15 + 溯源校验（反幻觉）
  - L3 narrative 叙事档案（≤2000 字符，与 9 维 JSON 并存）
  - 混合召回：FTS5 BM25（中文 bigram）+ 向量 + RRF(k=60) + 预算（5条/阈值/5s/2000字符）
  - chat 分层注入：L1→user 前缀 <relevant-memories>；profile+narrative+场景导航→system
  - FTS 自愈机制（虚拟表 DDL autocommit + 损坏表 writable_schema 清除重建）
- ✅ v0.10 全量验证：224 passed / 3 skipped / 0 failed（原 200 回归 + 新增 24）；4 轮红绿循环修复记录见 planning/test-log.md。
- ✅ v0.9 积压改动已全部归档入库（9 提交，含后端核心/语音/Web/安卓/固件/文档/build untrack）。
- ✅ PA Web 已成为默认主界面：Today 对话、性格工作室、我的画像、模型与感知、桌面弹幕、隐私与连接。
- ✅ 助手性格与用户画像独立版本化；用户画像纠正追加审计，停用不删除历史。
- ✅ 页面聊天只在 Web 显示；overlay 传输层只允许 `barrage` 与 `barrage_settings`。
- ✅ Electron 已删除桌宠、独立后端、模型管理和业务存储，仅保留透明置顶弹幕与托盘。
- ✅ MiniCPM-o 使用 `manual`、`perception`、`chat-backend` consumer 共享单 Worker。
- ✅ 最终全量：PA 200 passed / 3 skipped；Web 21 passed + typecheck/build；Desktop 27 passed + installer/ASAR 验证。
- ✅ v0.3 推荐引擎（联网动态搜索）：
  - Bing Web Search API + 可切 `ApiWebSearcher` 后端；写死推荐池已删
  - 推荐流程：蒸馏人格/兴趣 → LLM 生成搜索词 → 联网搜索 → LLM 筛选+排序 → 存储
  - 反幻觉：推荐内容溯源到搜索结果 URL+snippet，无源不推
- ✅ v0.4 个人 wiki：
  - 记忆→切片+分类→编译互链主题页+源引用；主题动态增长（增量 build）
  - 反幻觉：wiki 内容溯源到记忆条目，记忆溯源到源转录
- ✅ v0.5 LLM 可插拔配置增强：
  - 6 项基础旋钮可配：model / context_window / max_tokens / thinking_effort(off·低·中·高) / base_url / api_key（外加 `thinking_format` 用于 provider 原生字段风格选择）
  - 全局覆盖层：`config.set_override` 运行态覆盖 + env(PA_LLM_MODEL/BASE_URL/API_KEY/MAX_TOKENS/THINKING/THINKING_FORMAT) + `llm.*` 全局默认回落
  - 思考程度档位→provider 原生字段（按官方文档实测，不捏造）：GLM(openai_compat 仅开/关) / GLM-anthropic(budget) / OpenAI(reasoning_effort+max_completion_tokens) / Qwen(enable_thinking+thinking_budget) / Anthropic(thinking.budget_tokens)
  - 新增 `glm_anthropic` 后端（走 `open.bigmodel.cn/api/anthropic`）使 GLM 也能分低/中/高
  - `cli llm` 查生效配置（key 掩码）+ native 字段预览
  - 新端点：`GET/POST /settings/llm`、`POST /inbox/upload`（原始 body+filename，免 multipart）
- ✅ 测试体系：
  - `tests/test_llm_config.py` 10/10 绿（可插拔旋钮+覆盖层+思考档位）
  - `tests/test_pluggable.py` 41 用例（工厂路由/stub 合约/接口不变量/ABC 继承）
  - `tests/test_e2e.py` 端到端冒烟（stub 全链路，由 `cli test` 调用）
  - `tests/test_real_backends.py` 3 用例（faster-whisper/pyannote 可加载性 + speaker env 覆盖）
  - `tests/test_temporal.py` 47 用例（时间解析确定性）
  - **全量：102 passed**（在干净配置下通过，`.env` 覆盖时需显式设 stub 后端）
- ✅ 前端设计文档 `planning/frontend-design.md`（14 节 + 附录 A 四家真实参数，供外部实现回接）
- ✅ Web 控制面板（Next.js App Router + TypeScript + Tailwind）：
  - 从 `web/` 静态 React 原型迁移为完整 Next.js 工程（12 路由：dashboard/inbox/memories/persona/calendar/reminders/chat/recommend/wiki/verify/settings）
  - 共享 API 客户端 `@/lib/api` + 类型 `@/lib/types` + UI 组件 `@/components/ui`
  - 所有页面接后端真实端点（非 mock），`npm run build` 静态导出成功
- ✅ 安卓 App 全量源码落地（06-29）：Gradle 工程 + 10 屏 + 数据层/主题/反幻觉组件；后调整为纯前端定位（移除录音/上传/Inbox/前台服务），并换皮为「动森 Pocket Camp」风格
- ✅ LLM 后端新增 DeepSeek（06-30）：`deepseek` / `deepseek_anthropic` 双后端，key 走 `${DEEPSEEK_API_KEY}`，`config/default.json` 已配
- ✅ ESP32-S3 双模式固件端到端打通（07-10 ~ 07-18）：
  - 新增 `scripts/xiaozhi-esp32/` 完整固件工程 + `components/background_audio/` 背景音频组件
  - 唤醒词模式 + 背景音频收集双模式；VAD 切段 → PCM 直推 → WebSocket 推流
  - 后端 `/ws/audio` PCM 接收 → RMS VAD 切段 → WAV → inbox → ingest 全管线
  - GitHub Actions 云编译工作流落地，迭代 v34 → v38 固件
  - 07-18 修复 I2S 24-bit→16-bit 位偏移（`>>8`）保留完整动态范围
- ✅ 真 ASR / 真声纹后端就绪（代码 + 配置）：
  - `FasterWhisperTranscriber` 已支持 `medium` 模型、`float16`、`vad_filter`，配置项在 `config/default.json`
  - `PyannoteDiarizer` 已支持从 `config/default.json` 读取 `hf_token_env`，使用 `pyannote/speaker-diarization-3.1`
  - 切换命令：`PA_ASR_BACKEND=faster_whisper` / `PA_SPEAKER_BACKEND=pyannote`（需 CUDA + HF token）

## v0.9 PA Web 与桌面弹幕壳
- Today 为默认入口，桌面/移动 6 页矩阵无横向溢出、裁切或 console/page error。
- 统一弹幕策略覆盖提醒、主动建议、环境感知、游戏/课程事件；聊天回复不派生弹幕。
- WS role 协议为 `page|overlay|device` version 1；不兼容 overlay 在真实 Chromium 中干净关闭 1008。
- 真实 CUDA 生命周期：感知独占时 `stopped → ready → stopped`；显存 3222 → 10710 → 3165 MiB。
- 共享租约：`chat-backend + perception` 只产生一个 Worker；停止感知保留聊天 PID，切回 deepseek 后退出。
- 安装器：`PA-Desktop-Overlay-Setup-0.2.0-x64.exe`，SHA-256 `b7fc95fb3f9a9583c5a306bc998646f153e2beb8d825fec4b3639059d4b6fa36`。

## 阶段
- [x] Phase 0 脚手架+ASR 接口+后端骨架
- [x] Phase 1 接入(转录解析)→说话人归属→片段库
- [x] Phase 2 记忆抽取+检索
- [x] Phase 3 蒸馏引擎+人格档案
- [x] Phase 4 被动对话
- [x] Phase 5 主动触发引擎
- [x] v0.2 说话人区分(音频+文字) + 日历 + 提醒 + 反幻觉 verify + 真实时间戳
- [x] v0.3 推荐引擎(联网动态搜索 Bing/可切API + 反幻觉)
- [x] v0.4 个人 wiki(记忆→切片+分类+编译互链主题页+源引用 + 反幻觉)
- [x] v0.5 LLM 可配(5旋钮+思考程度档位+全局覆盖+cli llm+3新端点) + 前端设计文档
- [x] v0.6 安卓 App 全量源码 + 视觉换皮 + Robolectric/JVM 单测
- [x] v0.7 DeepSeek 后端接入
- [x] v0.8 ESP32-S3 双模式固件(背景音频+唤醒词) + /ws/audio 管线 + GitHub Actions 云编译
- [x] 后补：Web 面板实现 / pyannote 真声纹(GPU盒) / faster-whisper 真模型

## 命令
```bash
python3 -m personal_assistant.cli test                                       # stub 全链路
PA_LLM_BACKEND=anthropic_proxy python3 -m personal_assistant.cli test        # 真 GLM-5.2
python3 -m personal_assistant.cli llm                                        # 查生效 LLM 配置
PA_LLM_BACKEND=openai_compat PA_LLM_THINKING=高 python3 -m personal_assistant.cli llm  # 改思考程度
python3 -m personal_assistant.cli pipeline --once                            # 灌 inbox 转录
python3 -m personal_assistant.cli calendar 明天                              # 日历检索
python3 -m personal_assistant.cli reminders                                  # 提醒列表
python3 -m personal_assistant.cli verify                                     # 反幻觉复查
python3 -m personal_assistant.cli serve                                      # API（默认端口已改为 8004，见未提交改动）
```

> 上次自动审计: 2026-08-08 01:56 | 工作区 7 文件有改动 (5M/2A/0D)

## 未提交改动备注（2026-08-08）
工作区/暂存区有大量改动尚未提交，仅记录状态、不替用户提交：

**第二次审计修复（07-19）**
- `personal_assistant/chat.py`：`respond()` 改为返回 `(reply, evidence)` 元组
- `personal_assistant/storage.py`：新增 6 个 API 用查询函数 + `add_chat_log` 支持 `evidence` 参数 + 旧库列迁移
- `personal_assistant/distill.py`：新增 `run()`/`load_persona()`/`current_version()`
- `personal_assistant/reminders.py`：新增 `list_all()` 别名
- `personal_assistant/calendar.py`：新增 `get_events()` 别名
- `personal_assistant/wiki.py`：新增 `search()`/`list_topics()` 别名
- `personal_assistant/api.py`：补全 `/reminders/check` `/wiki/build` `/triggers` 三个缺失端点；修复调用签名
- `personal_assistant/config.py`：新增 `PA_SPEAKER_BACKEND` 环境覆盖
- `personal_assistant/speaker.py`：`PyannoteDiarizer` 从 config 读 token 配置，无 token 时回落
- `personal_assistant/auth.py`：`verify_ws_token` 从放行改为实际校验
- `config/default.json`：faster_whisper 改用 `medium` 模型；speaker 增加 model 配置
- `tests/test_e2e.py`：适配新签名 + Windows 兼容 + 离线不 fail

**前端迁移（07-19）**
- `web/` 完整迁移为 Next.js（12 路由、共享 API 客户端/类型/UI 组件、`window.PA_TOKEN` 鉴权）
- `.github/workflows/build-dual-mode-firmware.yml` 默认端口 8000 → 8004

**第一次审计修复 + 之前改动（07-18）**
- `personal_assistant/cli.py`：`serve` 默认端口 8004
- `personal_assistant/proactive.py`、`reminders.py`：ASCII-safe 输出、`check_due` 返回列表
- 新增 `start-pa.bat`、OTA 固件包与元数据

> 如需把这些改动归档到 git，建议用户自行 review 后 `git add` / `git commit`。

## 已知风险与待收尾项
详见 [PA-TODO.md](PA-TODO.md) — 22 项待办（1 P0 / 5 P1 / 9 P2 / 7 P3）。

## 部署
```bash
# 后端
python3 -m personal_assistant.cli serve                                    # 端口 8004

# 前端开发
cd web && npm run dev                                                     # 端口 3015

# 前端静态构建（输出 web/dist/，后端自动挂载 /web/）
cd web && npm run build

# 测试
PA_LLM_BACKEND=stub PA_ASR_BACKEND=stub PA_SPEAKER_BACKEND=text \
  python3 -m pytest tests/ --tb=short
# 102 passed
```
