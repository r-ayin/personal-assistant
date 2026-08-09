/*
 * background_audio.cpp — 背景音频收集实现（PCM 直推版）
 *
 * 不依赖 Opus 编译——直接发送 16kHz/16bit PCM 帧到 PC 后端。
 * PC 端 /ws/audio 做 RMS VAD 切段 → WAV → inbox → scan_inbox。
 *
 * 工作流：
 *   bg_feed_pcm() → 累积 PCM → 每 30ms 帧 WS 发送 → 静音超时发段结束标记
 */
#include "background_audio.h"

#include <string.h>
#include <math.h>
#include <freertos/FreeRTOS.h>
#include <freertos/task.h>
#include <freertos/semphr.h>
#include <esp_log.h>
#include <esp_system.h>
#include <esp_heap_caps.h>
#include <esp_websocket_client.h>
#include <esp_timer.h>

#define TAG "bg_audio"

/* ── 帧类型（与 PC 端 /ws/audio 约定）─── */
#define FRAME_PCM      0   /* PCM 音频数据 */
#define FRAME_SEGMENT  1   /* 段结束标记 */
#define FRAME_PING     2   /* 心跳 */

#define PING_INTERVAL_MS     30000
#define PONG_TIMEOUT_MS      60000   /* 2x ping interval, 超时强制重连 */
#define RECONNECT_BASE_MS    1000
#define RECONNECT_MAX_MS     30000

#define PCM_FRAME_SAMPLES   480    /* 30ms @ 16kHz */
#define VAD_CHUNK_SAMPLES   512    /* 32ms */
#define ONSET_CHUNKS        2
#define PCM_BUFFER_SECONDS  8      /* 8 秒环形缓冲 */

typedef struct {
    char ws_uri[160];
    char ws_headers[128];
    int sample_rate;
    int vad_threshold;
    int silence_timeout_ms;
    int min_segment_ms;

    esp_websocket_client_handle_t ws_client;
    bool ws_connected;

    /* VAD 状态机 */
    bool is_speaking;
    int silence_chunks;
    int onset_chunks;
    int speech_samples;

    /* PCM 缓冲（PSRAM 优先） */
    int16_t *pcm_buffer;
    size_t pcm_buffer_capacity;
    size_t pcm_buffer_count;

    bg_state_t state;
    int reconnect_attempt;
    int64_t reconnect_at;
    int64_t last_ping_ms;
    int64_t last_pong_ms;           /* WS 最后活跃时刻，心跳超时判断用 */

    SemaphoreHandle_t mutex;
    TaskHandle_t ws_task_handle;
} bg_ctx_t;

static bg_ctx_t g_ctx;

static void _append_pcm(const int16_t *data, size_t samples);
static void _flush_segment(void);
static void _send_pcm(const int16_t *data, size_t samples);
static void _send_control(uint8_t type);
static esp_err_t _connect_ws(void);
static void _disconnect_ws(void);
static void _ws_task(void *pv);

/* ── 公开 API ──────────────────────────────────────────────── */

int bg_init(const char *pc_ip, int pc_port, const char *token) {
    memset(&g_ctx, 0, sizeof(g_ctx));

    g_ctx.sample_rate = 16000;
    g_ctx.vad_threshold = 350;
    g_ctx.silence_timeout_ms = 500;
    g_ctx.min_segment_ms = 300;
    g_ctx.state = BG_STATE_STOPPED;

    snprintf(g_ctx.ws_uri, sizeof(g_ctx.ws_uri),
             "ws://%s:%d/ws/audio", pc_ip, pc_port);
    if (token && strlen(token) > 0) {
        // 头部 128 字节有界；token 过长时不得带截断后的凭据连接（会静默 401），
        // 直接放弃鉴权头并告警——服务端开启鉴权时该连接会被拒，但不会误导排查。
        int needed = snprintf(NULL, 0, "Authorization: Bearer %s\r\n", token);
        if (needed >= (int)sizeof(g_ctx.ws_headers)) {
            ESP_LOGW(TAG, "ws token too long (%d > %d), header disabled",
                     needed - 22, (int)sizeof(g_ctx.ws_headers));
            g_ctx.ws_headers[0] = '\0';
        } else {
            snprintf(g_ctx.ws_headers, sizeof(g_ctx.ws_headers),
                     "Authorization: Bearer %s\r\n", token);
        }
    }

    g_ctx.mutex = xSemaphoreCreateMutex();
    if (!g_ctx.mutex) {
        ESP_LOGE(TAG, "mutex 创建失败");
        return -1;
    }

    g_ctx.pcm_buffer_capacity = (size_t)g_ctx.sample_rate * PCM_BUFFER_SECONDS;
    g_ctx.pcm_buffer = (int16_t *)heap_caps_malloc(
        g_ctx.pcm_buffer_capacity * sizeof(int16_t),
        MALLOC_CAP_SPIRAM | MALLOC_CAP_8BIT);
    if (!g_ctx.pcm_buffer) {
        ESP_LOGW(TAG, "PSRAM 分配失败，用内部 RAM");
        g_ctx.pcm_buffer_capacity = (size_t)g_ctx.sample_rate * 4;
        g_ctx.pcm_buffer = (int16_t *)malloc(
            g_ctx.pcm_buffer_capacity * sizeof(int16_t));
        if (!g_ctx.pcm_buffer) {
            ESP_LOGE(TAG, "PCM 缓冲分配失败");
            vSemaphoreDelete(g_ctx.mutex);
            g_ctx.mutex = NULL;
            return -1;
        }
    }
    g_ctx.pcm_buffer_count = 0;

    ESP_LOGI(TAG, "初始化完成: ws://%s:%d/ws/audio 鉴权=%s 阈值=%d",
             pc_ip, pc_port, token && strlen(token) > 0 ? "已配置" : "未配置",
             g_ctx.vad_threshold);
    return 0;
}

int bg_start(void) {
    if (!g_ctx.mutex) return -1;
    xSemaphoreTake(g_ctx.mutex, portMAX_DELAY);

    if (g_ctx.state != BG_STATE_STOPPED) {
        xSemaphoreGive(g_ctx.mutex);
        return 0;
    }

    g_ctx.is_speaking = false;
    g_ctx.silence_chunks = 0;
    g_ctx.onset_chunks = 0;
    g_ctx.speech_samples = 0;
    g_ctx.pcm_buffer_count = 0;
    g_ctx.reconnect_attempt = 0;
    g_ctx.last_ping_ms = 0;
    g_ctx.last_pong_ms = 0;
    g_ctx.state = BG_STATE_IDLE;

    xSemaphoreGive(g_ctx.mutex);

    esp_err_t err = _connect_ws();
    if (err != ESP_OK) {
        ESP_LOGE(TAG, "WS 连接失败");
        xSemaphoreTake(g_ctx.mutex, portMAX_DELAY);
        g_ctx.state = BG_STATE_STOPPED;
        xSemaphoreGive(g_ctx.mutex);
        return -1;
    }

    ESP_LOGI(TAG, "背景收集已启动");
    return 0;
}

int bg_stop(void) {
    if (!g_ctx.mutex) return -1;
    xSemaphoreTake(g_ctx.mutex, portMAX_DELAY);

    if (g_ctx.state == BG_STATE_STOPPED) {
        xSemaphoreGive(g_ctx.mutex);
        return 0;
    }

    _flush_segment();
    g_ctx.state = BG_STATE_STOPPED;

    xSemaphoreGive(g_ctx.mutex);
    _disconnect_ws();
    ESP_LOGI(TAG, "背景收集已停止");
    return 0;
}

int bg_feed_pcm(const int16_t *pcm, size_t samples) {
    if (!pcm || samples == 0 || !g_ctx.mutex) return -1;
    xSemaphoreTake(g_ctx.mutex, portMAX_DELAY);

    if (g_ctx.state == BG_STATE_STOPPED) {
        xSemaphoreGive(g_ctx.mutex);
        return 0;
    }

    /* 缓冲模式：仅 memcpy 到 PSRAM 环形缓冲，由 _ws_task 异步发送。
     * 不在音频输入任务里做 WS 发送，避免 malloc + send 阻塞导致 I2S DMA 溢出。 */
    _append_pcm(pcm, samples);

    xSemaphoreGive(g_ctx.mutex);
    return 0;
}

int bg_reset(void) {
    if (!g_ctx.mutex) return -1;
    xSemaphoreTake(g_ctx.mutex, portMAX_DELAY);
    g_ctx.is_speaking = false;
    g_ctx.onset_chunks = 0;
    g_ctx.silence_chunks = 0;
    g_ctx.speech_samples = 0;
    g_ctx.pcm_buffer_count = 0;
    g_ctx.last_pong_ms = 0;
    xSemaphoreGive(g_ctx.mutex);
    return 0;
}

bg_state_t bg_get_state(void) {
    bg_state_t s = BG_STATE_STOPPED;
    if (g_ctx.mutex) {
        xSemaphoreTake(g_ctx.mutex, portMAX_DELAY);
        s = g_ctx.state;
        xSemaphoreGive(g_ctx.mutex);
    }
    return s;
}

/* ── 内部函数 ──────────────────────────────────────────────── */

static void _append_pcm(const int16_t *data, size_t samples) {
    if (g_ctx.pcm_buffer_count + samples > g_ctx.pcm_buffer_capacity) {
        size_t keep = g_ctx.pcm_buffer_capacity / 2;
        memmove(g_ctx.pcm_buffer,
                g_ctx.pcm_buffer + (g_ctx.pcm_buffer_count - keep),
                keep * sizeof(int16_t));
        g_ctx.pcm_buffer_count = keep;
    }
    memcpy(g_ctx.pcm_buffer + g_ctx.pcm_buffer_count, data,
           samples * sizeof(int16_t));
    g_ctx.pcm_buffer_count += samples;
}

static void _flush_segment(void) {
    int ms = (int)(g_ctx.speech_samples * 1000 / g_ctx.sample_rate);
    if (ms < g_ctx.min_segment_ms) {
        ESP_LOGD(TAG, "段太短 %dms，丢弃", ms);
        g_ctx.pcm_buffer_count = 0;
        return;
    }

    /* 逐帧发送 PCM（每帧 30ms，与 PC 端约定） */
    size_t offset = 0;
    while (offset + PCM_FRAME_SAMPLES <= g_ctx.pcm_buffer_count) {
        _send_pcm(g_ctx.pcm_buffer + offset, PCM_FRAME_SAMPLES);
        offset += PCM_FRAME_SAMPLES;
    }
    /* 剩余不足一帧的零头也发掉 */
    if (offset < g_ctx.pcm_buffer_count) {
        _send_pcm(g_ctx.pcm_buffer + offset, g_ctx.pcm_buffer_count - offset);
    }

    _send_control(FRAME_SEGMENT);
    ESP_LOGI(TAG, "背景段已发送: %dms", ms);
    g_ctx.pcm_buffer_count = 0;
}

/* ── WS 连接管理 ───────────────────────────────────────────── */

static void _ws_event_handler(void *h, esp_event_base_t b,
                              int32_t id, void *d) {
    xSemaphoreTake(g_ctx.mutex, portMAX_DELAY);
    g_ctx.last_pong_ms = (esp_timer_get_time() / 1000);  /* 任何事件=连接活跃 */
    switch (id) {
        case WEBSOCKET_EVENT_CONNECTED:
            ESP_LOGI(TAG, "WS 已连接");
            g_ctx.ws_connected = true;
            g_ctx.reconnect_attempt = 0;
            break;
        case WEBSOCKET_EVENT_DISCONNECTED: {
            ESP_LOGW(TAG, "WS 断开");
            g_ctx.ws_connected = false;
            g_ctx.reconnect_attempt++;
            int delay = RECONNECT_BASE_MS * (1 << (g_ctx.reconnect_attempt > 5 ? 5
                                                 : g_ctx.reconnect_attempt));
            if (delay > RECONNECT_MAX_MS) delay = RECONNECT_MAX_MS;
            g_ctx.reconnect_at = (esp_timer_get_time() / 1000) + delay;
            break;
        }
        case WEBSOCKET_EVENT_ERROR:
            ESP_LOGE(TAG, "WS 错误");
            break;
        default:
            break;
    }
    xSemaphoreGive(g_ctx.mutex);
}

static esp_err_t _connect_ws(void) {
    if (g_ctx.ws_client) _disconnect_ws();

    esp_websocket_client_config_t cfg = {};
    cfg.uri = g_ctx.ws_uri;
    cfg.headers = g_ctx.ws_headers[0] != '\0' ? g_ctx.ws_headers : NULL;
    cfg.task_stack = 4096;
    cfg.buffer_size = 4096;
    cfg.network_timeout_ms = 200;      /* > WiFi MAX_MODEM 信标间隔 102ms */
    cfg.reconnect_timeout_ms = 5000;
    g_ctx.ws_client = esp_websocket_client_init(&cfg);
    if (!g_ctx.ws_client) return ESP_FAIL;

    esp_websocket_register_events(g_ctx.ws_client, WEBSOCKET_EVENT_ANY,
                                  _ws_event_handler, NULL);

    esp_err_t err = esp_websocket_client_start(g_ctx.ws_client);
    if (err != ESP_OK) {
        esp_websocket_client_destroy(g_ctx.ws_client);
        g_ctx.ws_client = NULL;
    }

    if (err == ESP_OK && g_ctx.ws_task_handle == NULL) {
        xTaskCreate(_ws_task, "bg_ws", 4096, NULL, 2, &g_ctx.ws_task_handle);
    }
    return err;
}

static void _disconnect_ws(void) {
    if (g_ctx.ws_task_handle) {
        TaskHandle_t h = g_ctx.ws_task_handle;
        g_ctx.ws_task_handle = NULL;
        vTaskDelete(h);
    }
    if (g_ctx.ws_client) {
        esp_websocket_client_stop(g_ctx.ws_client);
        esp_websocket_client_destroy(g_ctx.ws_client);
        g_ctx.ws_client = NULL;
    }
    g_ctx.ws_connected = false;
}

static void _ws_task(void *pv) {
    int16_t local_pcm[PCM_FRAME_SAMPLES * 2];  /* 最多 2 帧的本地拷贝 */
    while (g_ctx.ws_task_handle) {
        vTaskDelay(pdMS_TO_TICKS(30));

        xSemaphoreTake(g_ctx.mutex, portMAX_DELAY);
        int64_t now = esp_timer_get_time() / 1000;

        /* 从环形缓冲拷贝最多 2 帧到本地（持锁，但只做 memcpy/memmove，微秒级） */
        size_t frames_to_send = 0;
        if (g_ctx.ws_connected && g_ctx.pcm_buffer_count >= PCM_FRAME_SAMPLES) {
            /* 缓冲超过 1 秒 → 丢弃旧数据 */
            if (g_ctx.pcm_buffer_count > 16000) {
                size_t discard = g_ctx.pcm_buffer_count - 16000;
                memmove(g_ctx.pcm_buffer, g_ctx.pcm_buffer + discard,
                        16000 * sizeof(int16_t));
                g_ctx.pcm_buffer_count = 16000;
            }
            /* 最多取 2 帧 */
            frames_to_send = 2;
            if (frames_to_send * PCM_FRAME_SAMPLES > g_ctx.pcm_buffer_count) {
                frames_to_send = g_ctx.pcm_buffer_count / PCM_FRAME_SAMPLES;
            }
            if (frames_to_send > 0) {
                size_t copy_samples = frames_to_send * PCM_FRAME_SAMPLES;
                memcpy(local_pcm, g_ctx.pcm_buffer, copy_samples * sizeof(int16_t));
                /* 移出已拷贝部分 */
                size_t remaining = g_ctx.pcm_buffer_count - copy_samples;
                if (remaining > 0) {
                    memmove(g_ctx.pcm_buffer, g_ctx.pcm_buffer + copy_samples,
                            remaining * sizeof(int16_t));
                }
                g_ctx.pcm_buffer_count = remaining;
            }
        }

        /* 心跳 */
        if (g_ctx.ws_connected && now - g_ctx.last_ping_ms > PING_INTERVAL_MS) {
            g_ctx.last_ping_ms = now;
            _send_control(FRAME_PING);
        }

        /* 心跳超时 */
        if (g_ctx.ws_connected
            && g_ctx.last_pong_ms > 0
            && now - g_ctx.last_pong_ms > PONG_TIMEOUT_MS) {
            ESP_LOGW(TAG, "心跳超时 %lldms，强制重连", (long long)(now - g_ctx.last_pong_ms));
            if (g_ctx.ws_client) {
                esp_websocket_client_stop(g_ctx.ws_client);
                esp_websocket_client_destroy(g_ctx.ws_client);
                g_ctx.ws_client = NULL;
            }
            g_ctx.ws_connected = false;
            g_ctx.reconnect_attempt++;
            g_ctx.reconnect_at = now + RECONNECT_BASE_MS;
        }

        /* 重连 */
        bool need_reconnect = false;
        if (!g_ctx.ws_connected && g_ctx.state != BG_STATE_STOPPED
            && g_ctx.reconnect_at > 0 && now >= g_ctx.reconnect_at) {
            need_reconnect = true;
            g_ctx.reconnect_at = 0;
        }

        xSemaphoreGive(g_ctx.mutex);

        /* WS 发送在锁外执行：不阻塞音频输入任务 */
        for (size_t i = 0; i < frames_to_send; i++) {
            _send_pcm(local_pcm + i * PCM_FRAME_SAMPLES, PCM_FRAME_SAMPLES);
        }

        /* 重连也在锁外执行（_connect_ws 内部会自己管理锁） */
        if (need_reconnect) {
            ESP_LOGI(TAG, "尝试重连...");
            _connect_ws();
        }
    }
    vTaskDelete(NULL);
}

/* ── 帧发送 ──────────────────────────────────────────────────── */

static void _send_pcm(const int16_t *data, size_t samples) {
    if (!g_ctx.ws_connected || !g_ctx.ws_client || samples == 0) return;

    /* 帧格式: type(1B) + pcm_data(2B * samples) */
    size_t total = 1 + samples * sizeof(int16_t);
    uint8_t *frame = (uint8_t *)malloc(total);
    if (!frame) return;

    frame[0] = FRAME_PCM;
    memcpy(frame + 1, data, samples * sizeof(int16_t));

    esp_websocket_client_send_bin(g_ctx.ws_client, (char *)frame, total,
                                  pdMS_TO_TICKS(100));
    free(frame);
}

static void _send_control(uint8_t type) {
    if (!g_ctx.ws_connected || !g_ctx.ws_client) return;
    uint8_t ctrl[1] = { type };
    esp_websocket_client_send_bin(g_ctx.ws_client, (char *)ctrl, 1,
                                  pdMS_TO_TICKS(500));
}
