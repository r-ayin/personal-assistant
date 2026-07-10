/*
 * background_audio.h — 背景音频收集模块
 *
 * 独立组件，通过 FeedPCM() 接收音频数据 → VAD 分割 → Opus 编码 → WS 推流到 PC。
 * xiaozhi-esp32 在 idle 状态时持续运行，对话时自动暂停。
 */
#pragma once

#include <stdint.h>
#include <stddef.h>

#ifdef __cplusplus
extern "C" {
#endif

typedef enum {
    BG_STATE_STOPPED = 0,
    BG_STATE_IDLE,
    BG_STATE_COLLECTING,
} bg_state_t;

/**
 * 初始化背景收集模块
 * @param pc_ip  PC 端 IP 地址
 * @param pc_port PC 端端口（默认 8000）
 * @param token  Bearer token，无则留空
 * @return 0=成功，-1=失败
 */
int bg_init(const char *pc_ip, int pc_port, const char *token);

/**
 * 启动收集：连接 WS，开始语音处理
 */
int bg_start(void);

/**
 * 停止收集：发完当前段 → 断开 WS
 */
int bg_stop(void);

/**
 * 喂入 PCM 数据（16kHz, 16bit, mono）
 * 在 AudioService 的音频循环中调用
 * @param pcm     PCM 样本数据
 * @param samples 样本数
 */
int bg_feed_pcm(const int16_t *pcm, size_t samples);

/**
 * 重置 VAD 状态（唤醒词触发时调用）
 */
int bg_reset(void);

/**
 * 获取当前状态
 */
bg_state_t bg_get_state(void);

#ifdef __cplusplus
}
#endif
