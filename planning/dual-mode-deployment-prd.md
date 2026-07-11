# 双模式固件部署 PRD

## 1. 概述
在 ESP32-S3-N16R8（COM4）上部署双模式固件（xiaozhi-esp32 + 背景音频收集），启动 PC 后端服务，配置手机端接入。

## 2. 配置项
- **ESP32 WiFi**：连接到本地局域网（xiaozhi-esp32 通过 menuconfig/CLI 配置）
- **PC IP/Port**：`192.168.1.100:8000`（COFIG_PC_IP/CONFIG_PC_PORT，已在 sdkconfig.defaults 设置）
- **ESP32 音频**：INMP441 I2S 麦克风（默认），16kHz/16bit PCM

## 3. 烧录流程
- esptool 擦除全部 flash → 按偏移写入 4 个 bin
- 写入后串口监视验证启动日志
- 验证 `[bg_audio] WS 已连接` 和 `[Application] Wake word detected`

## 4. PC 后端
- `personal_assistant.cli serve` 启动 FastAPI 服务
- 端点：`/ws/audio`（ESP32 背景音频接入）/ `/ws/xiaozhi`（唤醒对话 WS 中继）/ `/ws/live`（手机直播）/ `web/`（控制面板）
- 自动 VAD 切段 → WAV → inbox → ingest pipeline

## 5. 手机端接入
- **同 WiFi**：浏览器 `http://PC_IP:8000/web/` 直连
- **外网**：ECS `relay_bridge` + PC `tunnel_client` 隧道
- **Android App**：需 Android Studio 环境编译，当前通过 Web 面板替代

## 6. 架构依赖
```
ESP32 (COM4) ──USB──→ PC:8000 ──→ /ws/audio 背景PCM
                        │       ──→ /ws/xiaozhi 唤醒对话
                        │       ──→ web/ 控制面板
                        │
                   同 WiFi ──→ 手机浏览器直连
                   ECS ──→ 外网隧道中继
```

## 7. 验证标准
- [ ] esptool flash 成功，日志无 panic
- [ ] ESP32 连接 WiFi 成功
- [ ] PC `/health` 返回 ok
- [ ] ESP32 日志出现 `WS 已连接`
- [ ] 手机浏览器打开控制面板
- [ ] 唤醒词触发对话
