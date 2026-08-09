# PA-TODO — personal-assistant 待办清单

> 审计日期：2026-07-19 | 最后更新：2026-07-25

---

## P0 — 必须修复

- [x] `personal_assistant/chat.py`：respond() 中的 TODO — 从 memory.search 命中的记忆 id 收集 evidence，当前始终返回空列表。导致对话溯源链断裂。（已修复 07-25）

---

## P1 — 技术债 / 文档滞后

- [ ] **git 工作区未提交** — 46+ 文件有改动。建议分批 commit。
- [x] **`personal_assistant/reminders.py`** — `calendar_resolve_prompt()` 标记为 `[deprecated]`，确认无引用后已删除。（07-25）

---

## P2 — 质量增强

- [ ] **API 鉴权测试** — `/memories` `/profile` `/chat-log` 缺 401 单测
- [ ] **faster-whisper e2e** — 需真实音频
- [ ] **pyannote 真声纹 e2e** — 需 HF_TOKEN + 真实音频
- [ ] **Android 单测** — 仅 AppContextRobolectricTest，10 ViewModel 无覆盖
- [ ] **Web 前端测试** — 12 页面零 Jest/Cypress
- [ ] **DuckDB 习惯分析可读视图** — query_habits() 只输出 JSON

---

## P3 — 后续功能

- [ ] pyannote 真声纹启用（需 HF_TOKEN）
- [ ] faster-whisper 中式语音实测
- [ ] Web 前端鉴权 UI（用户输入 token）
- [ ] Android 通知真机测试
- [ ] Docker 部署
- [ ] **git 历史 token 清理（可选）** — 2026-08-08 PA_API_TOKEN 已轮换（旧值失效），历史提交中的旧 token 已无安全风险；如需彻底清除可跑 `git filter-repo --replace-text`（破坏性，需通知所有克隆方）
- [ ] **ECS relay token 同步** — PA_RELAY_TOKEN 仍为旧值；若 ECS 中继转发用同一 token 鉴权，需同步更新 ECS 侧配置（.env 已加注记）
- [ ] **历史固件包含已失效 token** — xiaozhi-dual-mode-firmware-v29~v37 的 .bin 内嵌旧 token（已失效）；新版固件走 sdkconfig.local/secrets 注入
- [ ] **GitHub 仓库 secret 配置** — 云编译工作流改用 `secrets.PA_WS_TOKEN`，需在仓库 Settings→Secrets 添加（值为当前 PA_API_TOKEN）

---

## 🔴 当前进行中：微信聊天记录导入

### 尝试记录（07-25 ~ 07-26，全部未成功）

**目标**：解密 PC 微信 4.1.12.24 本地数据库（SQLCipher 4），导出聊天记录注入 PA。

**已排除方案**：
| 方案 | 结果 | 原因 |
|------|------|------|
| cdb 断点 `bcrypt!BCryptDeriveKeyPBKDF2` | ❌ | WeChat 4.1.x Windows 版不走系统 CNG，用静态编译 OpenSSL |
| 旧版内存扫描 `x'<64hex_key>'` | ❌ | 4.1.x 不缓存 raw key |
| ZedeX `scan_keys.py` pymem 扫描 | ❌ | 4322 前缀，0 有效 key |
| 803MB 内存 dump 搜 passphrase | ❌ | 高熵块无法定位 |
| `afumu/wetrace` DLL 注入 | ❌ | GitHub DMCA 下架，外网不通 |
| 备份 RMFH 格式解密 | ❌ | 密钥在手机端生成，PC 上没有 |
| Android 模拟器 + Frida | ❌ | 国内镜像无系统镜像，Google 不通 |
| ECS Linux GDB 断点（wcdb-key-tool） | ❌ | ELF 分析偏移 0x67413f0 不是真正密钥函数，断点不触发 |
| ECS 内存 dump 搜 passphrase | ❌ | 登录后 passphrase 被清零 |
| strace 追踪文件打开 | ❌ | WeChat 不用 openat 打开 .db |

**根因**：WeChat 4.1.x 全平台（Windows/Linux）都不在内存中常驻 passphrase，登录时派生完密钥即清零。唯一捕获窗口是登录瞬间的函数调用，但 ELF 静态分析给出的断点地址不对。

**当前状态**：
- PC 微信数据：`C:\Users\admin\Documents\xwechat_files\wxid_ts58chree3kx22_eac4\db_storage\`（SQLCipher 4 加密）
- 3.1GB 备份：`C:\Users\admin\Documents\xwechat_files\Backup\wxid_ts58chree3kx22\`（RMFH 加密）
- ECS Linux 微信已登录：`/root/xwechat_files/wxid_ts58chree3kx22_eac4/db_storage/`（16 个 .db）
- 工具链：`E:\x-tool\wcdb-key-tool\`、`E:\x-tool\weixin-decrypte\`、`E:\x-tool\wechat-decrypt-328\`

**可行路径**：
1. **Mac/Linux 设备**（已验证）：同号登录跑 `wcdb_key_tool.py extract`，5 分钟出 passphrase
2. **手动导出**：手机微信 → 聊天 → 长按 → 多选 → 转发到文件传输助手 → 导出文本 → 格式化导入 PA
3. **PC 进程直接读**：用 UI Automation 从 PC 微信窗口抓取消息文本（不需要解密 DB）

---

## ✅ 本轮修复（07-25 语音链路修复 + ASR 反幻觉 + 提速）

### 根因定位
- **「点赞打赏」内容根因**：不是 prompt/设置问题，是 Whisper 在噪声/低音量音频上的经典幻觉（`請不吝點贊訂閱轉發打賞支持明鏡與點點欄目`，YouTube 字幕腔），LLM 顺着幻觉文本回复所致。
- **TTS 无声根因**：`_tts_to_opus_frames` 里 `input_ctx.decode(audio=True)` —— `True==1`，PyAV 按索引取第 2 路流越界（tuple index out of range），每句 0 opus packets。另 FFmpeg 原生 opus 编码器只支持 48kHz。
- **后端掉线根因**：进程不知何时被终止，端口 8004 无人监听。

### xiaozhi_server.py
- ✅ TTS 修复：`decode(audio=0)` + 编码器优先 libopus@16kHz（回退原生 opus@48kHz）+ bit_rate 24k。实测 146 packets 全可解码。
- ✅ ASR 反幻觉：`condition_on_previous_text=False` + `initial_prompt` 引导简体 + 幻觉话术黑名单（点赞/打赏/订阅/转发/明镜等繁简）+ 低置信段过滤（cr>2.4 且 lp<-1.0）。
- ✅ 提速：serve 启动后台预热 ASR 模型（api.py lifespan，省首句 ~8s 模型加载）；VAD 静音尾 12→8 帧（720→480ms）；`chat.respond(voice=True)` 语音模式（≤60 字、口语化、禁 emoji）；纯 emoji 句跳过 TTS。
- 全量测试 102 passed 不回归。

### chat.py
- ✅ `_system_prompt(user_msg, voice=False)` 新增 voice 参数
- ✅ `respond(user_msg, voice=False)` 向后兼容

### api.py
- ✅ lifespan 中 `asyncio.to_thread(xiaozhi_server.warmup_asr)` 后台预热

### 数据清理
- ✅ 删除所有 stub 测试生成的假数据（db/persona/inbox），空库重启
- ✅ 25 条 Hermes Agent 记忆注入 PA 记忆系统 + 人格蒸馏完成
- ✅ 个人知识库文件：`data/knowledge/personal-profile.md`

### 待验证
- ⚠️ TTS 设备端实际发声（packets 已验证可解码，待真机确认）
- ⚠️ 反幻觉过滤实战表现（黑名单命中率见 backend.log「ASR 幻觉话术过滤」行）
