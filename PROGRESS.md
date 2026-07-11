# personal-assistant — 进度

> 直导式构建。v0.6 双模式固件（ESP32 背景音频采集 + 唤醒词"江江"本地后端处理）
> Web 面板全量接后端 + 多 Agent 管理架构

## 当前状态（2026-07-12）

### 已完成 ✅

#### v0.1–v0.5 基础功能（全部端到端跑通）
- ✅ v0.1 深核 MVP：ASR→记忆→蒸馏→对话→主动
- ✅ v0.2 说话人区分/日历/提醒/反幻觉/真实时间戳
- ✅ v0.3 推荐引擎（联网动态搜索 Bing/可切 API）
- ✅ v0.4 个人 wiki（记忆→切片→分类→编译互链主题页）
- ✅ v0.5 LLM 可插拔（5 旋钮 + 思考程度档位 + 全局覆盖 + 3 新端点）

#### v0.6 ESP32 双模式固件（2026-07-10~12）
- ✅ **双模式固件**：xiaozhi-esp32 v2.2.6 + 背景音频收集（ESP-IDF v5.5.4, ESP32-S3-N16R8）
- ✅ **背景音频采集**：ESP32 I2S → RMS VAD → TCP 8004 → PC 后端 → WAV → ASR → 记忆抽取
- ✅ **TCP 替代 WebSocket**：解决 esp_websocket_client 兼容问题，连接稳定不断开
- ✅ **NAT 保活**：空闲每 5 秒发静音 PCM 帧防路由器超时
- ✅ **"江江"唤醒词**：后端 FasterWhisper ASR 识别 → DeepSeek 对话回复
- ✅ **唤醒对话本地化**：不依赖 xiaozhi 云，全部走本地后端
- ✅ **CI 自动构建流水线**：GitHub Actions 云编译 + 自动下载烧录（`AutoCIFlash` 定时任务每 15 分钟）

#### Web 面板（全量改造）
- ✅ **Agent 管理页**：设备注册/名称编辑/个性 JSON 配置
- ✅ **设置页**：deepseek 后端选项，全 6 后端切换
- ✅ 仪表盘/日历/对话/wiki 全部接后端真数据
- ✅ 所有 JSX 空安全修复（`tags` 兼容数组/字符串、`source_ids`/`link_ids` 兼容格式）
- ✅ 缓存破坏 `?v=2`

#### 后端新增
- ✅ **Multi-Agent 架构**：agents 表 + CRUD API + agent_id 段标记
- ✅ **统一 LLM**：DeepSeek deepseek-v4-flash，所有 agent 共享
- ✅ 新端点：`/agents`、`/interventions`、`/memories/search`、`/chat/clear`、`/wiki/build`

### 进行中/待完善 🔄
- [ ] **第3轮测试**：对着开发板实际说话 → ASR 识别 → "江江"触发对话（端到端验证未完成）
- [ ] **Web 面板继续完善**：VerifyPage items 明细、PersonaPage 版本切换后端支持
- [ ] **ESP32 端 "江江" 替换 xiaozhi 唤醒词**：当前唤醒词检测在 PC 后端 ASR 侧，非 ESP32 本地

### 待办
- [ ] 安卓 App 编译（缺 Android SDK 环境）
- [ ] ECS 外网隧道（PC tunnel_client → ECS relay_bridge 打通）
- [ ] pyannote 真声纹（GPU 盒）
- [ ] faster-whisper 小型模型优化

## 命令
```bash
python -m personal_assistant.cli serve                        # API
curl http://localhost:8000/status                              # 查看数据量
curl http://localhost:8000/agents                              # 设备列表
python -m personal_assistant.cli llm                           # 查 LLM 配置
python -m personal_assistant.cli test                          # stub 全链路
```

## 固件烧录
```bash
cd /e/x-tool/personal-assistant/xiaozhi-dual-mode-firmware-v28/xiaozhi-dual-mode-firmware
python -m esptool --chip esp32s3 --port COM4 write-flash 0x20000 xiaozhi.bin
```
