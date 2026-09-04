# 固件定位：只录音 + 上传（v0.12 纯文字化改造，2026-08-30）

本项目固件从「小智对话固件」裁剪为**纯录音采集上传设备**，配合个人助手的纯文字化架构。

## 保留（核心链路）

- **录音**：麦克风采集（audio_service + 各板级 codec：ES8311/ES8374/ES8388/ES8389/Box 等）
- **上传**：components/background_audio —— PCM 16kHz/16bit/mono 直推
  ws://<PC_IP>:<PORT>/ws/audio（Byte0=帧类型：0=PCM 帧 / 1=段结束 / 2=ping），
  鉴权走 Authorization: Bearer <token> 头（token 读取优先级：NVS > CONFIG_PA_SERVER_TOKEN，
  读取时回退，启动不做写时播种）
- **服务器侧**：api.py 的 /ws/audio 收流 → RMS VAD 切段 → WAV 落 inbox → scan_inbox 转写 → 进记忆系统
- **设备反馈**：display 子系统（LCD/OLED 状态栏）**有意保留**——所有板级基础设施深度依赖其做状态反馈
  （录音中/联网状态等），不参与任何对话功能（经确认的合理偏差）
- **其余保留**：OTA（本地 websocket 凭据保护）、settings（NVS）、LED、目标板（genjutech-s3-1.54tft）

## 已删除（实时对话相关）

- main/audio/wake_words/（本地唤醒词：MultiNet6/AFE/Custom）
- main/protocols/websocket_protocol.*（小智对话协议）
- main/protocols/mqtt_protocol.*（MQTT+UDP 对话协议）
- main/mcp_server.*（设备侧 MCP，供 LLM 反向控制设备）
- application.cc 中的对话状态机分支、TTS 下行处理；audio_service 的唤醒词注入/检测（playback 队列保留，供提示音播放）
- sdkconfig 唤醒词模型（CONFIG_SR_WN_WN9_NIHAOXIAOZHI_TTS=n）

## 数据流

~~~
[麦克风采集] → [background_audio PCM 直推] → ws://PC/ws/audio
  → [服务器 RMS VAD 切段] → [WAV 落 inbox] → [scan_inbox 转写(服务器侧)]
  → [文本片段入记忆系统（融合记忆：信息层+时刻层）]
~~~

转写不再发生在设备端；设备只负责「录」与「传」。
