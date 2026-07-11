/*
 * background_audio.cpp — 背景音频收集实现（原始 TCP 版）
 *
 * 通过原始 TCP socket 发送 16kHz/16bit PCM 帧到 PC 后端的 8004 端口。
 * 协议：1B type + 4B length LE + N bytes PCM data
 *   type=0 PCM | type=1 segment_end | type=2 ping
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
#include <esp_timer.h>
#include <lwip/sockets.h>
#include <lwip/netdb.h>

#define TAG "bg_audio"

#define FRAME_PCM      0
#define FRAME_SEGMENT  1
#define FRAME_PING     2

#define PING_INTERVAL_MS     30000
#define RECONNECT_BASE_MS    1000
#define RECONNECT_MAX_MS     30000

#define PCM_FRAME_SAMPLES   480
#define VAD_CHUNK_SAMPLES   512
#define ONSET_CHUNKS        2
#define PCM_BUFFER_SECONDS  8

typedef struct {
    char host[64];
    int port;
    int sample_rate;
    int vad_threshold;
    int silence_timeout_ms;
    int min_segment_ms;

    int sock;
    bool connected;

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

    SemaphoreHandle_t mutex;
    TaskHandle_t mgmt_task_handle;
} bg_ctx_t;

static bg_ctx_t g_ctx;

static void _append_pcm(const int16_t *data, size_t samples);
static void _flush_segment(void);
static void _tcp_send(uint8_t type, const uint8_t *payload, size_t len);
static int _tcp_connect(void);
static void _tcp_disconnect(void);
static void _mgmt_task(void *pv);

int bg_init(const char *pc_ip, int pc_port, const char *token) {
    memset(&g_ctx, 0, sizeof(g_ctx));
    strncpy(g_ctx.host, pc_ip, sizeof(g_ctx.host) - 1);
    g_ctx.port = pc_port;
    g_ctx.sample_rate = 16000;
    g_ctx.vad_threshold = 350;
    g_ctx.silence_timeout_ms = 500;
    g_ctx.min_segment_ms = 300;
    g_ctx.state = BG_STATE_STOPPED;
    g_ctx.sock = -1;

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

    ESP_LOGI(TAG, "初始化: %s:%d 阈值=%d", g_ctx.host, g_ctx.port, g_ctx.vad_threshold);
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
    g_ctx.state = BG_STATE_IDLE;
    xSemaphoreGive(g_ctx.mutex);

    if (_tcp_connect() != 0) {
        ESP_LOGE(TAG, "TCP 连接失败");
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
    _tcp_disconnect();
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

    size_t offset = 0;
    while (offset < samples) {
        size_t chunk = (samples - offset < (size_t)VAD_CHUNK_SAMPLES)
                       ? (samples - offset) : (size_t)VAD_CHUNK_SAMPLES;
        const int16_t *chunk_data = pcm + offset;

        int64_t sum = 0;
        for (size_t i = 0; i < chunk; i++) {
            sum += (int32_t)chunk_data[i] * (int32_t)chunk_data[i];
        }
        int rms = (chunk > 0) ? (int)sqrt((double)(sum / chunk)) : 0;
        bool voice = (rms >= g_ctx.vad_threshold);

        if (!g_ctx.is_speaking) {
            if (voice) {
                g_ctx.onset_chunks++;
                _append_pcm(chunk_data, chunk);
                if (g_ctx.onset_chunks >= ONSET_CHUNKS) {
                    g_ctx.is_speaking = true;
                    g_ctx.speech_samples = g_ctx.pcm_buffer_count;
                    g_ctx.silence_chunks = 0;
                }
            } else {
                g_ctx.onset_chunks = 0;
                if (g_ctx.pcm_buffer_count < (size_t)VAD_CHUNK_SAMPLES * ONSET_CHUNKS) {
                    g_ctx.pcm_buffer_count = 0;
                }
            }
        } else {
            _append_pcm(chunk_data, chunk);
            g_ctx.speech_samples += chunk;
            if (voice) {
                g_ctx.silence_chunks = 0;
            } else {
                g_ctx.silence_chunks++;
                int silence_ms = g_ctx.silence_chunks *
                    (VAD_CHUNK_SAMPLES * 1000 / g_ctx.sample_rate);
                if (silence_ms >= g_ctx.silence_timeout_ms) {
                    _flush_segment();
                    g_ctx.is_speaking = false;
                    g_ctx.onset_chunks = 0;
                    g_ctx.silence_chunks = 0;
                    g_ctx.speech_samples = 0;
                }
            }
        }
        offset += chunk;
    }
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

/* ── PCM 缓冲 ──────────────────────────────────────────────── */

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

    size_t offset = 0;
    while (offset + PCM_FRAME_SAMPLES <= g_ctx.pcm_buffer_count) {
        _tcp_send(FRAME_PCM, (uint8_t*)(g_ctx.pcm_buffer + offset), PCM_FRAME_SAMPLES * 2);
        offset += PCM_FRAME_SAMPLES;
    }
    if (offset < g_ctx.pcm_buffer_count) {
        _tcp_send(FRAME_PCM, (uint8_t*)(g_ctx.pcm_buffer + offset),
                  (g_ctx.pcm_buffer_count - offset) * 2);
    }
    _tcp_send(FRAME_SEGMENT, NULL, 0);
    ESP_LOGI(TAG, "背景段已发送: %dms", ms);
    g_ctx.pcm_buffer_count = 0;
}

/* ── TCP 连接管理 ───────────────────────────────────────────── */

static int _tcp_connect(void) {
    _tcp_disconnect();

    struct addrinfo hints = {0}, *res;
    hints.ai_family = AF_INET;
    hints.ai_socktype = SOCK_STREAM;
    char port_str[8];
    snprintf(port_str, sizeof(port_str), "%d", g_ctx.port);

    if (getaddrinfo(g_ctx.host, port_str, &hints, &res) != 0 || !res) {
        ESP_LOGE(TAG, "DNS 解析失败: %s", g_ctx.host);
        return -1;
    }

    int sock = socket(res->ai_family, res->ai_socktype, 0);
    if (sock < 0) {
        freeaddrinfo(res);
        return -1;
    }

    struct timeval timeout = {.tv_sec = 5, .tv_usec = 0};
    setsockopt(sock, SOL_SOCKET, SO_RCVTIMEO, &timeout, sizeof(timeout));
    setsockopt(sock, SOL_SOCKET, SO_SNDTIMEO, &timeout, sizeof(timeout));

    if (connect(sock, res->ai_addr, res->ai_addrlen) != 0) {
        close(sock);
        freeaddrinfo(res);
        ESP_LOGE(TAG, "TCP 连接失败: %s:%d", g_ctx.host, g_ctx.port);
        return -1;
    }
    freeaddrinfo(res);

    g_ctx.sock = sock;
    g_ctx.connected = true;
    g_ctx.reconnect_attempt = 0;

    if (g_ctx.mgmt_task_handle == NULL) {
        xTaskCreate(_mgmt_task, "bg_tcp_mgmt", 2048, NULL, 2, &g_ctx.mgmt_task_handle);
    }

    ESP_LOGI(TAG, "TCP 已连接: %s:%d", g_ctx.host, g_ctx.port);
    return 0;
}

static void _tcp_disconnect(void) {
    if (g_ctx.mgmt_task_handle) {
        TaskHandle_t h = g_ctx.mgmt_task_handle;
        g_ctx.mgmt_task_handle = NULL;
        vTaskDelete(h);
    }
    if (g_ctx.sock >= 0) {
        close(g_ctx.sock);
        g_ctx.sock = -1;
    }
    g_ctx.connected = false;
}

static void _tcp_send(uint8_t type, const uint8_t *payload, size_t len) {
    if (!g_ctx.connected || g_ctx.sock < 0) return;

    uint8_t header[5];
    header[0] = type;
    header[1] = len & 0xFF;
    header[2] = (len >> 8) & 0xFF;
    header[3] = (len >> 16) & 0xFF;
    header[4] = (len >> 24) & 0xFF;

    if (send(g_ctx.sock, header, 5, 0) < 0) {
        ESP_LOGW(TAG, "TCP 发送失败（header）");
        _tcp_disconnect();
        return;
    }
    if (len > 0 && payload) {
        if (send(g_ctx.sock, payload, len, 0) < 0) {
            ESP_LOGW(TAG, "TCP 发送失败（payload）");
            _tcp_disconnect();
        }
    }
}

static void _mgmt_task(void *pv) {
    int idle_pcm_count = 0;
    while (g_ctx.mgmt_task_handle) {
        vTaskDelay(pdMS_TO_TICKS(1000));

        xSemaphoreTake(g_ctx.mutex, portMAX_DELAY);
        int64_t now = esp_timer_get_time() / 1000;

        /* 心跳 */
        if (g_ctx.connected && now - g_ctx.last_ping_ms > PING_INTERVAL_MS) {
            g_ctx.last_ping_ms = now;
            _tcp_send(FRAME_PING, NULL, 0);
        }

        /* NAT 保活：空闲时每 5 秒发一段静音 PCM，防止路由器超时断开 TCP */
        if (g_ctx.connected && !g_ctx.is_speaking) {
            idle_pcm_count++;
            if (idle_pcm_count >= 5) {  // 5 秒
                idle_pcm_count = 0;
                int16_t silence[PCM_FRAME_SAMPLES] = {0};
                _tcp_send(FRAME_PCM, (uint8_t*)silence, PCM_FRAME_SAMPLES * 2);
            }
        } else {
            idle_pcm_count = 0;
        }

        /* 重连 */
        if (!g_ctx.connected && g_ctx.state != BG_STATE_STOPPED
            && g_ctx.reconnect_at > 0 && now >= g_ctx.reconnect_at) {
            ESP_LOGI(TAG, "尝试重连...");
            _tcp_connect();
            g_ctx.reconnect_at = 0;
        }

        xSemaphoreGive(g_ctx.mutex);
    }
    vTaskDelete(NULL);
}
