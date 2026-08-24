"""xiaozhi_server.py — 实现 xiaozhi-esp32 WebSocket 服务端协议（设备↔电脑对话）。

协议见 https://github.com/78/xiaozhi-esp32/blob/main/docs/websocket.md
- hello 握手协商 audio_params（opus/pcm, 16kHz, frame_duration 60ms）
- 设备发 listen{state:start/stop/detect} 标记语音边界（设备端 ESP-SR 唤醒词+VAD 已做）
- 设备发二进制 OPUS/PCM 帧 → 服务端解码 → 累积 → listen stop 时整段 ASR
- 服务端发 stt{text}（转写）→ LLM → tts{state:start/sentence_start:text/stop}（逐句回答）
- 同时把 stt/tts 事件经 ws_manager 广播到手机 live.html（实时转录 + AI 回答两流）

OPUS 解码用 opuslib（lazy import；GPU 电脑 pip install opuslib + libopus）。
dev 盒无 opuslib → 用 format=pcm 的假客户端测协议；真 xiaozhi 固件发 opus 需 GPU 电脑。
"""
from __future__ import annotations
import asyncio
import hashlib
import json
import logging
import re
import time
import struct
import wave
import io
from datetime import datetime

from fastapi import WebSocket, WebSocketDisconnect

from . import auth, storage, ws_manager
from . import chat as _chat
from . import llm as _llm

log = logging.getLogger("pa.xiaozhi")

SAMPLE_RATE = 16000
SAMPLE_WIDTH = 2  # 16-bit
CHANNELS = 1


def _split_sentences(text: str) -> list[str]:
    """按中英文句末标点切成句（保留标点）。"""
    parts = re.findall(r'[^。！？!?…\n]*[。！？!?…\n]*', text)
    out = [p for p in (x.strip() for x in parts) if p]
    return out or [text]


# Whisper 在噪声/低音量/不清晰音频上的经典幻觉话术（YouTube 字幕腔、直播腔），
# 整段过滤，不再送给 LLM —— 否则助手会顺着幻觉文本聊"点赞打赏"。
_HALLUC_RE = re.compile(
    r'請不吝|请不吝|點贊|点赞|訂閱|订阅|打賞|打赏|轉發|转发|明鏡|明镜|'
    r'感謝收看|感谢收看|小鈴鐺|小铃铛|关注主播|刷礼物|訂閱我的|订阅我的'
)


class _ProtocolError(Exception):
    """hello 能力协商失败：参数不支持或服务端缺解码器，endpoint 关闭连接。"""


# 显式 turn 状态机：idle → listening → recognizing → thinking → speaking → idle。
# 状态只用于日志/可观测，收发判定仍走 _listening/_turn_id 守卫。
_STATE_IDLE = "idle"
_STATE_LISTENING = "listening"
_STATE_RECOGNIZING = "recognizing"
_STATE_THINKING = "thinking"
_STATE_SPEAKING = "speaking"

# TTS 下行背压：opus 帧 60ms；前 3 帧快速发送建立设备解码缓冲，
# 之后按帧时长 pacing，避免瞬间灌入数百包溢出设备约 2.4s 的 decode queue。
_TTS_FRAME_MS = 60
_TTS_FAST_START_FRAMES = 3


class _IncrementalSplitter:
    """增量句切分：LLM delta 到达时按句末标点切出完整句，剩余残留在缓冲。"""

    def __init__(self):
        self._buf = ""

    def feed(self, chunk: str) -> list[str]:
        """返回本次 chunk 切出的完整句（含标点）。"""
        if not chunk:
            return []
        self._buf += chunk
        out = []
        while True:
            m = re.search(r"[^。！？!?…\n]*[。！？!?…\n]", self._buf)
            if not m:
                break
            s = m.group(0).strip()
            if s:
                out.append(s)
            self._buf = self._buf[m.end():]
        return out

    def flush(self) -> str:
        """返回无句末标点的残余文本并清空缓冲。"""
        rest = self._buf.strip()
        self._buf = ""
        return rest


async def _tts_to_opus_frames(text: str, voice: str = "zh-CN-XiaoxiaoNeural") -> list[bytes]:
    """文本 → opus 帧列表（60ms @ 16kHz mono）。

    流程：edge-tts 生成 mp3 → PyAV 解码 → resample 到 16kHz mono fltp → PyAV 编码 opus。
    返回每个 opus packet 的 bytes 列表，可直接 send_bytes 给设备。
    """
    import edge_tts
    import av
    import io as _io

    # 1. edge-tts 生成 mp3
    communicate = edge_tts.Communicate(text, voice=voice)
    mp3_data = bytearray()
    try:
        async for chunk in communicate.stream():
            if chunk["type"] == "audio":
                mp3_data.extend(chunk["data"])
    except Exception as e:
        log.warning("edge-tts 失败: %s", e)
        return []
    if not mp3_data:
        return []

    # 2. PyAV 解码 mp3 → resample 16kHz mono fltp → 编码 opus
    try:
        input_ctx = av.open(_io.BytesIO(bytes(mp3_data)))
    except Exception as e:
        log.warning("PyAV 打开 mp3 失败: %s", e)
        return []

    # libopus 支持 16kHz 输入；FFmpeg 原生 opus 编码器只接受 48kHz
    # （16k 会报 "tuple index out of range"，导致 0 packets 设备无声）
    try:
        encoder = av.CodecContext.create('libopus', 'w')
        enc_rate = SAMPLE_RATE
    except Exception:
        encoder = av.CodecContext.create('opus', 'w')
        enc_rate = 48000
    encoder.sample_rate = enc_rate
    encoder.layout = 'mono'
    encoder.format = av.AudioFormat('fltp')
    encoder.bit_rate = 24000

    resampler = av.AudioResampler(format='fltp', layout='mono', rate=enc_rate)

    opus_packets: list[bytes] = []
    try:
        # audio=0 取第 0 路音频流（不能写 audio=True：True==1 会越界取第 2 路流）
        for frame in input_ctx.decode(audio=0):
            resampled = resampler.resample(frame)
            for rf in resampled:
                try:
                    packets = encoder.encode(rf)
                except Exception as e:
                    log.debug("opus encode err: %s", e)
                    continue
                for pkt in packets:
                    opus_packets.append(bytes(pkt))
        # flush encoder
        try:
            packets = encoder.encode(None)
            for pkt in packets:
                opus_packets.append(bytes(pkt))
        except Exception:
            pass
    except Exception as e:
        log.warning("PyAV opus 编码失败: %s", e)
    finally:
        try:
            input_ctx.close()
        except Exception:
            pass
    log.info("TTS: text=%r voice=%s → %d opus packets",
             text[:50], voice, len(opus_packets))
    return opus_packets


def _voice_llm():
    """音箱通道 LLM：max_tokens 限长（xiaozhi.llm_max_tokens），避免超长回复拖长 TTS。

    每次构造新实例成本极低（仅持有配置值）；测试可注入替身 assistant 绕过。
    """
    from . import config
    return _llm.get_llm(max_tokens=config.get("xiaozhi.llm_max_tokens", 160))


def warmup_asr():
    """预热 xiaozhi 路径的 faster_whisper 模型（serve 启动时后台调用）。

    首次加载模型 + CUDA kernel 初始化约 8s，预热避免首句语音干等。
    未装 faster_whisper 时静默跳过（stub 环境）。
    """
    try:
        import faster_whisper  # noqa
    except ImportError:
        return
    try:
        import numpy as np
        model = XiaozhiSession._load_asr_model()
        segs, _ = model.transcribe(
            np.zeros(SAMPLE_RATE // 2, dtype=np.float32),
            vad_filter=False, language="zh",
        )
        list(segs)
        log.info("ASR 预热完成")
    except Exception as e:
        log.warning("ASR 预热失败: %s", e)


class _PyavOpusDecoder:
    """PyAV 实现的 OPUS 解码器，API 兼容 opuslib.Decoder.decode(data, frame_size)。

    opuslib 需要 native libopus.dll，Windows 上常缺；PyAV 自带 FFmpeg 含 opus 解码器，
    可作回退。返回 s16 interleaved PCM bytes。
    """
    def __init__(self, sample_rate: int, channels: int):
        import av  # noqa
        self._av = av
        self._ctx = av.CodecContext.create('opus', 'r')
        layout = 'mono' if channels == 1 else 'stereo'
        self._resampler = av.AudioResampler(
            format='s16', layout=layout, rate=sample_rate
        )
        self._decode_count = 0
        self._frame_count = 0
        self._sample_rate = sample_rate
        self._channels = channels

    def decode(self, data: bytes, frame_size: int = 0) -> bytes:
        self._decode_count += 1
        packet = self._av.Packet(data)
        out = bytearray()
        try:
            frames = self._ctx.decode(packet)
        except Exception as e:
            if self._decode_count <= 3:
                log.warning("PyAV opus decode err #%d: %s", self._decode_count, e)
            return b''
        # 前 3 帧和每 50 帧打一次诊断
        if self._decode_count <= 3 or self._decode_count % 50 == 0:
            log.info("PyAV decode #%d: frames=%d", self._decode_count, len(frames))
        # 逐帧 resample（PyAV resample 接受单 frame 最稳）
        for frame in frames:
            self._frame_count += 1
            try:
                resampled = self._resampler.resample(frame)
            except Exception as e:
                if self._frame_count <= 3:
                    log.warning("PyAV resample err #%d: %s", self._frame_count, e)
                continue
            for rf in resampled:
                try:
                    arr = rf.to_ndarray()
                    out.extend(arr.tobytes())
                except Exception as e:
                    if self._frame_count <= 3:
                        log.warning("PyAV to_ndarray err #%d: %s", self._frame_count, e)
                    continue
            if self._frame_count <= 3 or self._frame_count % 50 == 0:
                log.info("PyAV frame #%d: resampled=%d out=%dB",
                         self._frame_count, len(resampled) if resampled else 0, len(out))
        return bytes(out)


class _OpusDecoder:
    """lazy OPUS 解码器：优先 opuslib（需 libopus.dll），回退 PyAV。返回有 decode() 的对象。"""
    _tried = False
    _backend = None   # "opuslib" | "pyav" | None
    _lib = None

    @classmethod
    def _probe(cls):
        if cls._tried:
            return
        cls._tried = True
        # 1) opuslib（需要 native libopus.dll）
        # 注意：opuslib.api 在 import 阶段就 find_library('opus')，
        # 找不到时抛 Exception（不是 ImportError）。用宽 except 兜住。
        try:
            import opuslib  # noqa
            try:
                opuslib.Decoder(SAMPLE_RATE, CHANNELS)
                cls._backend = "opuslib"
                cls._lib = opuslib
                log.info("OPUS 解码后端: opuslib")
                return
            except Exception as e:
                log.warning("opuslib 已装但 Decoder 初始化失败: %s", e)
        except Exception as e:
            log.info("opuslib 不可用（%s），尝试 PyAV 回退", e)
        # 2) PyAV 回退（自带 FFmpeg 含 opus 解码器）
        try:
            import av  # noqa
            av.CodecContext.create('opus', 'r')  # 验证可用
            cls._backend = "pyav"
            cls._lib = av
            log.info("OPUS 解码后端: PyAV (opuslib 不可用时的回退)")
            return
        except Exception as e:
            log.warning("PyAV 也不可用，OPUS 解码完全失败: %s", e)
        cls._backend = None
        cls._lib = None

    @classmethod
    def get(cls, sample_rate: int, channels: int):
        cls._probe()
        if cls._backend is None:
            return None
        if cls._backend == "opuslib":
            try:
                return cls._lib.Decoder(sample_rate, channels)
            except Exception as e:
                log.warning("opuslib 初始化失败: %s", e)
                return None
        # PyAV
        try:
            return _PyavOpusDecoder(sample_rate, channels)
        except Exception as e:
            log.warning("PyAV OPUS 初始化失败: %s", e)
            return None


class XiaozhiSession:
    """单个设备连接的会话状态机。"""

    # 服务端 VAD 参数（设备 VAD 不可靠时的兜底）
    _VAD_THRESHOLD = 1500      # 最低 RMS 阈值下限；有效阈值 = 噪声基线 *1.8，见 _vad_threshold
    _VAD_NOISE_FRAMES = 16     # 前 N 帧（16*60ms≈1s）评估噪声基底
    _VAD_MIN_THRESHOLD = 2500  # 自适应阈值下限（环境太静时不再多等尾巴）
    _VAD_MAX_NOISE = 12000     # 噪声基底钳制上限（避免持续高音被误当背景噪声）
    _VAD_SILENCE_LIMIT = 8     # 连续静音帧数上限（8 * 60ms = 480ms → finalize，缩短响应尾巴）
    _VAD_MAX_FRAMES = 133      # 最大聆听帧数（133 * 60ms ≈ 8s 保险 → 强制 finalize，防噪声拖满 15s）

    def __init__(self, ws, device_key: str | None = None,
                 asr=None, assistant=None, tts=None):
        self.ws = ws
        self.session_id = f"s-{datetime.now().strftime('%H%M%S%f')[:12]}"
        self.audio_format = "pcm"      # 设备 hello 声明
        self.sample_rate = SAMPLE_RATE
        self.channels = CHANNELS
        self.frame_duration = 60
        self._opus = None              # opuslib.Decoder 或 _PyavOpusDecoder（lazy）
        self._pcm_buf = bytearray()    # 当前 listen 段累积的 PCM
        self._listening = False
        self._aborted = False
        # 可取消 turn：_turn_id 单调递增；在途 turn 只有 id 匹配且未关闭才允许发送。
        self._turn_id = 0
        self._turn_task: asyncio.Task | None = None
        self._tts_task: asyncio.Task | None = None   # 流式 TTS 消费者（随 turn 取消）
        self._closed = False
        self._state = _STATE_IDLE
        # 服务端 VAD 状态
        self._listen_frames = 0
        self._silence_frames = 0
        self._pcm_buf_log_at = 0       # 下次打印累积长度的帧序号
        self._vad_noise_rms: list[int] = []   # 前 _VAD_NOISE_FRAMES 帧 RMS，评估噪声基底
        self._vad_threshold = self._VAD_MIN_THRESHOLD  # 自适应阈值（随噪声基线更新）
        self._seen_voice = False       # 本轮是否出现过有效语音（未出声前不因静音切段）
        # 测试替身可注入；默认走真实 faster-whisper / Assistant / Edge TTS
        self._asr_func = asr or self._asr
        self._assistant = assistant or _chat.assistant_for(
            "xiaozhi:" + (device_key or self.session_id),
            llm=_voice_llm())
        self._tts_func = tts or _tts_to_opus_frames

    def _set_state(self, state: str) -> None:
        if state != self._state:
            log.info("session=%s state: %s -> %s", self.session_id, self._state, state)
            self._state = state

    def _turn_active(self, turn_id: int) -> bool:
        """当前 turn 是否仍有效：未被 abort/新 turn 覆盖，连接未关闭。"""
        return (not self._closed
                and turn_id == self._turn_id
                and self._turn_task is not None
                and not self._turn_task.done())

    async def _send_json(self, obj: dict) -> None:
        obj.setdefault("session_id", self.session_id)
        try:
            await self.ws.send_text(json.dumps(obj, ensure_ascii=False))
        except Exception as e:
            log.debug("send_json drop: %s", e)

    async def _on_hello(self, msg: dict) -> None:
        """校验设备音频能力并回 hello；参数不支持或缺解码器时抛 _ProtocolError。"""
        ap = msg.get("audio_params", {}) or {}
        fmt = str(ap.get("format", "pcm"))
        try:
            rate = int(ap.get("sample_rate", SAMPLE_RATE))
            channels = int(ap.get("channels", CHANNELS))
            duration = int(ap.get("frame_duration", 60))
        except (TypeError, ValueError):
            raise _ProtocolError("audio_params must be integers")
        if fmt not in ("opus", "pcm"):
            raise _ProtocolError(f"unsupported audio format: {fmt!r}")
        if rate != SAMPLE_RATE or channels != CHANNELS or duration != 60:
            raise _ProtocolError(
                f"unsupported audio_params: {rate}Hz/{channels}ch/{duration}ms")
        self.audio_format = fmt
        self.sample_rate = rate
        self.channels = channels
        self.frame_duration = duration
        if fmt == "opus":
            self._opus = _OpusDecoder.get(self.sample_rate, self.channels)
            if self._opus is None:
                # 无 Opus 解码器时明确拒绝：固件不读取服务端协商出的 format，
                # 伪协商为 pcm 只会让设备继续发 opus 而被误当 pcm 解析。
                raise _ProtocolError("no opus decoder available on server")
        await self._send_json({
            "type": "hello", "transport": "websocket",
            "session_id": self.session_id,
            "audio_params": {
                "format": self.audio_format, "sample_rate": self.sample_rate,
                "channels": self.channels, "frame_duration": self.frame_duration,
            },
        })
        log.info("xiaozhi hello: session=%s format=%s", self.session_id, self.audio_format)

    async def _on_listen(self, msg: dict) -> None:
        state = msg.get("state")
        if state in ("start", "detect"):
            self._listening = True
            self._pcm_buf = bytearray()
            self._aborted = False
            self._listen_frames = 0
            self._silence_frames = 0
            self._pcm_buf_log_at = 0
            self._vad_noise_rms = []
            self._vad_threshold = self._VAD_MIN_THRESHOLD
            self._seen_voice = False
            self._set_state(_STATE_LISTENING)
        elif state == "stop":
            self._listening = False
            await self._finalize_utterance()

    async def _on_audio(self, data: bytes) -> None:
        if not self._listening:
            return  # 非 listen 段的帧丢弃
        # 解码
        pcm: bytes = b''
        if self.audio_format == "opus":
            if self._opus is None:
                return
            try:
                pcm = self._opus.decode(data, frame_size=int(self.sample_rate * self.frame_duration / 1000))
            except Exception as e:
                log.warning("opus decode 失败: %s", e)
                return
        else:
            pcm = data
        if not pcm:
            return  # 解码空，丢弃
        self._pcm_buf.extend(pcm)
        self._listen_frames += 1

        # 服务端 VAD：算 RMS；有效阈值自适应噪声基线（前 N 帧第 3 小值 *1.8）
        rms = self._rms(pcm)
        if len(self._vad_noise_rms) < self._VAD_NOISE_FRAMES:
            self._vad_noise_rms.append(rms)
            if len(self._vad_noise_rms) == self._VAD_NOISE_FRAMES:
                base = min(sorted(self._vad_noise_rms)[2], self._VAD_MAX_NOISE)
                self._vad_threshold = max(int(base * 1.8), self._VAD_MIN_THRESHOLD)
                log.info("VAD 噪声基线: rms=%d 有效阈值=%d", base, self._vad_threshold)
        if rms >= self._vad_threshold:
            self._seen_voice = True
            # 宽容积分：语音帧归还 2 个静音帧（容忍偶发尖峰噪声），不为 0 而清零
            self._silence_frames = max(0, self._silence_frames - 2)
        else:
            self._silence_frames += 1

        # 周期性日志（前 3 帧 + 每 50 帧），含 RMS/阈值用于调参
        if self._listen_frames <= 3 or self._listen_frames % 50 == 0:
            log.info("listen frame=%d pcm=%dB rms=%d thr=%d silence=%d",
                     self._listen_frames, len(self._pcm_buf),
                     rms, self._vad_threshold, self._silence_frames)

        # 触发 finalize 条件：静音 8 帧（480ms）即切段，不再等满 15s；
        # 阈值已自适应噪声基线，无需再校验"是否出现过语音"
        need_finalize = False
        if self._silence_frames >= self._VAD_SILENCE_LIMIT \
                and len(self._pcm_buf) >= SAMPLE_RATE * SAMPLE_WIDTH // 2:
            log.info("server VAD: 静音 %d 帧 → finalize", self._silence_frames)
            need_finalize = True
        elif self._listen_frames >= self._VAD_MAX_FRAMES:
            log.info("server VAD: 达到最大帧数 %d → 强制 finalize", self._listen_frames)
            need_finalize = True

        if need_finalize:
            self._listening = False
            await self._finalize_utterance()

    @staticmethod
    def _rms(pcm: bytes) -> int:
        """16-bit LE PCM 的 RMS（int16 单位）。空数据返回 0。"""
        if not pcm or len(pcm) < 2:
            return 0
        n = len(pcm) // 2
        total = 0
        # 步长 2 取每个 int16 样本（避免 numpy 依赖）
        for i in range(0, n * 2, 2):
            # signed 16-bit little-endian
            s = pcm[i] | (pcm[i+1] << 8)
            if s >= 32768:
                s -= 65536
            total += s * s
        return int((total / n) ** 0.5)

    async def _finalize_utterance(self) -> None:
        """快照 PCM 并启动独立 turn 任务；不阻塞 receiver，abort 可被及时消费。"""
        if self._aborted:
            log.info("finalize skipped: aborted")
            return
        pcm = bytes(self._pcm_buf)
        self._pcm_buf = bytearray()
        pcm_ms = len(pcm) * 1000 // (SAMPLE_RATE * SAMPLE_WIDTH)
        log.info("finalize: pcm=%d bytes (%dms), frames=%d",
                 len(pcm), pcm_ms, self._listen_frames)
        if len(pcm) < SAMPLE_RATE * SAMPLE_WIDTH // 2:  # < 0.5s 丢弃
            log.info("finalize: pcm < 0.5s, discard")
            self._set_state(_STATE_IDLE)
            return
        self._turn_id += 1
        turn_id = self._turn_id
        self._cancel_turn_tasks()
        self._turn_task = asyncio.create_task(self._run_turn(turn_id, pcm))
        self._set_state(_STATE_RECOGNIZING)

    def _cancel_turn_tasks(self) -> None:
        """取消在途 turn 及其 TTS 消费者；abort/新 turn/断连共用。"""
        prev = self._turn_task
        if prev is not None and not prev.done():
            prev.cancel()
        self._turn_task = None
        tts = self._tts_task
        if tts is not None and not tts.done():
            tts.cancel()
        self._tts_task = None

    async def _run_turn(self, turn_id: int, pcm: bytes) -> None:
        """独立 turn：ASR → stt → LLM → 逐句 TTS。所有退出路径收敛到终态。

        每步发送前检查 _turn_active(turn_id)：abort 或新 turn 会递增 _turn_id，
        在途任务的结果一律丢弃，绝不向设备/手机发送旧 generation 的内容。
        """
        started = time.perf_counter()
        metrics: dict = {"turn_id": turn_id}
        try:
            # ASR
            wav_bytes = self._to_wav(pcm)
            text = await asyncio.to_thread(self._asr_func, wav_bytes)
            metrics["asr_ms"] = int((time.perf_counter() - started) * 1000)
            if not self._turn_active(turn_id):
                return
            if not text:
                # 空 ASR：明确空转写事件，让设备/前端感知"本轮无内容"，
                # 而不是设备仍 listening、服务端已停止接收的卡死状态。
                log.info("turn=%d ASR empty -> terminal", turn_id)
                await self._send_json({"type": "stt", "text": ""})
                return
            log.info("turn=%d sending stt", turn_id)
            await self._send_json({"type": "stt", "text": text})
            try:
                await ws_manager.manager.broadcast(
                    ws_manager.EV_TRANSCRIPTION,
                    {"text": text, "speaker": "user", "is_partial": False})
            except Exception as e:
                log.warning("turn=%d broadcast stt failed: %s", turn_id, e)
            # LLM 流式：增量文本按句切分，完整句立即交给 TTS 消费者，
            # 首句无需等待 LLM 全部生成（句级流式）。
            log.info("turn=%d calling LLM respond (stream)", turn_id)
            self._set_state(_STATE_THINKING)
            sentences_q: asyncio.Queue = asyncio.Queue()
            splitter = _IncrementalSplitter()
            loop = asyncio.get_running_loop()
            out_packets = 0
            llm_error = False

            def on_delta(piece: str) -> None:
                """LLM 子线程回调：线程安全地把完整句投递到 asyncio 队列。"""
                for s in splitter.feed(piece):
                    if re.search(r"\w", s):
                        loop.call_soon_threadsafe(sentences_q.put_nowait, s)

            async def _speak_consumer() -> None:
                """TTS 消费者：取句 → sentence_start → TTS → pacing 发送 → sentence_end。"""
                nonlocal out_packets
                while True:
                    s = await sentences_q.get()
                    if s is None:
                        return
                    if not self._turn_active(turn_id):
                        return
                    await self._send_json(
                        {"type": "tts", "state": "sentence_start", "text": s})
                    try:
                        await ws_manager.manager.broadcast(
                            ws_manager.EV_CHAT_REPLY,
                            {"text": s, "evidence": evidence or [], "is_partial": False})
                    except Exception:
                        pass
                    if self.audio_format == "opus":
                        frames = self._tts_func(s)
                        if asyncio.iscoroutine(frames):
                            frames = await frames
                        if not self._turn_active(turn_id):
                            return
                        for idx, opus_pkt in enumerate(frames):
                            if not self._turn_active(turn_id):
                                return
                            try:
                                await self.ws.send_bytes(opus_pkt)
                                out_packets += 1
                            except Exception as e:
                                log.warning("turn=%d send opus failed: %s", turn_id, e)
                                break
                            if idx >= _TTS_FAST_START_FRAMES - 1:
                                await asyncio.sleep(_TTS_FRAME_MS / 1000.0)
                        await self._send_json(
                            {"type": "tts", "state": "sentence_end", "text": s})

            consumer = asyncio.create_task(_speak_consumer())
            self._tts_task = consumer
            self._set_state(_STATE_SPEAKING)
            try:
                await asyncio.to_thread(storage.add_chat_log, "user", text)
                if not self._turn_active(turn_id):
                    return
                await self._send_json({"type": "tts", "state": "start"})
                result = await asyncio.to_thread(
                    self._assistant.respond_stream, text, True, on_delta=on_delta)
                reply, evidence = result.reply, result.evidence
                if not self._turn_active(turn_id):
                    return
                # 无句末标点的残余尾巴也要播报
                tail = splitter.flush()
                if tail and re.search(r"\w", tail):
                    sentences_q.put_nowait(tail)
                await asyncio.to_thread(
                    storage.add_chat_log, "assistant", reply, evidence=evidence)
            except Exception as e:
                log.warning("turn=%d LLM/storage failed: %s", turn_id, e)
                llm_error = True
            finally:
                await sentences_q.put(None)
            try:
                await consumer
            except asyncio.CancelledError:
                raise
            except Exception as e:
                log.warning("turn=%d tts consumer error: %s", turn_id, e)
            finally:
                # 兜底：turn 取消/退出时确保消费者不再挂起在队列上
                if consumer is not None and not consumer.done():
                    consumer.cancel()
                if self._tts_task is consumer:
                    self._tts_task = None
            if llm_error or not self._turn_active(turn_id):
                return
            metrics["llm_ms"] = int((time.perf_counter() - started) * 1000)
            metrics["out_packets"] = out_packets
            await self._send_json({"type": "tts", "state": "stop"})
            metrics["turn_total_ms"] = int((time.perf_counter() - started) * 1000)
            log.info("turn metrics: %s", json.dumps(metrics, ensure_ascii=False))
        except asyncio.CancelledError:
            log.info("turn=%d cancelled", turn_id)
            raise
        except Exception as e:
            log.warning("turn=%d error: %s", turn_id, e)
            try:
                await self._send_json({"type": "tts", "state": "stop"})
            except Exception:
                pass
        finally:
            if self._turn_active(turn_id):
                self._set_state(_STATE_IDLE)

    # xiaozhi 路径专用 ASR 模型缓存（避免每次连接重新加载）
    _asr_model = None

    @classmethod
    def _load_asr_model(cls):
        """lazy 加载 faster_whisper 模型（类级缓存，跨连接复用）。"""
        if cls._asr_model is None:
            from faster_whisper import WhisperModel
            from . import config
            c = config.get("asr.faster_whisper", {})
            log.info("加载 faster_whisper 模型: size=%s device=%s compute=%s",
                     c.get("model_size", "small"),
                     c.get("device", "cpu"),
                     c.get("compute_type", "int8"))
            cls._asr_model = WhisperModel(
                c.get("model_size", "small"),
                device=c.get("device", "cpu"),
                compute_type=c.get("compute_type", "int8"),
            )
        return cls._asr_model

    def _asr(self, wav_bytes: bytes) -> str:
        """直接调 faster_whisper，关闭 vad_filter（xiaozhi 路径已服务端 VAD 切段）。

        faster_whisper 的 silero VAD 对 opus 解码后的 PCM 容易误判整段为静音，
        xiaozhi 路径已在 _on_audio 里做了 RMS VAD 切段，这里关掉 VAD filter。
        condition_on_previous_text=False 防幻觉逐段传播；initial_prompt 引导简体；
        段级过滤幻觉话术黑名单 + 低置信段（高压缩率+低 logprob）。
        """
        from . import config
        archive = config.ROOT / "data" / "inbox" / "archive"
        archive.mkdir(parents=True, exist_ok=True)  # 先建目录再 mkstemp
        # 用 session_id 命名，保留最近一次音频供人工调试
        debug_path = archive / f"xiaozhi_{self.session_id}.wav"
        try:
            with open(debug_path, "wb") as f:
                f.write(wav_bytes)
            model = self._load_asr_model()
            cfg = config.get("asr.faster_whisper", {})
            segments, info = model.transcribe(
                str(debug_path), vad_filter=False,
                language=config.get("asr.language", "zh"),
                condition_on_previous_text=False,
                beam_size=cfg.get("beam_size", 1),
                best_of=cfg.get("best_of", 1),
                initial_prompt="以下是简体中文普通话日常对话。",
            )
            # 收集 segments（faster_whisper 是 generator，需遍历）并过滤幻觉/低置信段
            kept: list[str] = []
            total = 0
            for s in segments:
                total += 1
                cr = getattr(s, "compression_ratio", 0) or 0
                lp = getattr(s, "avg_logprob", 0) or 0
                if _HALLUC_RE.search(s.text):
                    log.info("ASR 幻觉话术过滤: %r", s.text)
                    continue
                if cr > 2.4 and lp < -1.0:
                    log.info("ASR 低置信过滤: %r (cr=%.2f lp=%.2f)", s.text, cr, lp)
                    continue
                kept.append(s.text)
            text = "".join(kept).strip()
            log.info("ASR: lang=%s prob=%.2f duration=%.2fs segs=%d kept=%d text=%r",
                     getattr(info, "language", "?"),
                     getattr(info, "language_probability", 0),
                     getattr(info, "duration", 0),
                     total, len(kept), text)
            for i, s in enumerate(kept):
                log.info("  seg[%d]: %r", i, s)
            return text
        except Exception as e:
            log.warning("ASR 失败: %s", e)
            return ""

    @staticmethod
    def _to_wav(pcm: bytes) -> bytes:
        buf = io.BytesIO()
        with wave.open(buf, "wb") as wf:
            wf.setnchannels(CHANNELS)
            wf.setsampwidth(SAMPLE_WIDTH)
            wf.setframerate(SAMPLE_RATE)
            wf.writeframes(pcm)
        return buf.getvalue()

    async def _on_abort(self, msg: dict) -> None:
        """打断：作废在途 turn、取消生成任务，并让设备回到可再听状态。"""
        self._aborted = True
        self._turn_id += 1
        self._pcm_buf = bytearray()
        self._cancel_turn_tasks()
        self._set_state(_STATE_IDLE)
        try:
            await self._send_json({"type": "tts", "state": "stop"})
        except Exception as e:
            log.debug("abort tts.stop drop: %s", e)

    async def close(self) -> None:
        """连接结束：取消在途 turn，回收任务。"""
        self._closed = True
        prev = self._turn_task
        tts = self._tts_task
        self._cancel_turn_tasks()
        for t in (prev, tts):
            if t is not None and not t.done():
                try:
                    await t
                except (asyncio.CancelledError, Exception):
                    pass


def _stable_device_key(ws) -> str:
    """由 Device-Id/Client-Id 的 SHA-256 前缀生成会话 key（不暴露原始标识）。"""
    raw = ws.headers.get("device-id") or ws.headers.get("client-id") or ""
    if not raw:
        return ""
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16]


async def xiaozhi_endpoint(ws: WebSocket):
    """/ws/xiaozhi — xiaozhi-esp32 设备接入点。"""
    # 鉴权：Authorization header（xiaozhi 固件用 Bearer header）或 ?token=
    token = ws.query_params.get("token", "")
    if not token:
        authz = ws.headers.get("authorization") or ws.headers.get("Authorization") or ""
        if authz.lower().startswith("bearer "):
            token = authz[7:].strip()
    if auth.is_auth_enabled() and not auth._check(token):
        await ws.close(code=1008)
        return
    await ws.accept()
    sess = XiaozhiSession(ws, device_key=_stable_device_key(ws))
    log.info("xiaozhi device connected: %s", ws.client)
    binary_count = 0
    text_count = 0
    try:
        while True:
            msg = await ws.receive()
            if msg["type"] == "websocket.disconnect":
                break
            if "bytes" in msg and msg["bytes"] is not None:
                binary_count += 1
                if binary_count <= 3 or binary_count % 50 == 0:
                    log.info("recv binary #%d size=%d listening=%s",
                             binary_count, len(msg["bytes"]), sess._listening)
                await sess._on_audio(msg["bytes"])
            elif "text" in msg and msg["text"] is not None:
                text_count += 1
                try:
                    obj = json.loads(msg["text"])
                except json.JSONDecodeError:
                    log.warning("recv text #%d not json: %s", text_count, msg["text"][:200])
                    continue
                t = obj.get("type")
                log.info("recv text #%d type=%s", text_count, t)
                if t == "hello":
                    try:
                        await sess._on_hello(obj)
                    except _ProtocolError as e:
                        log.info("xiaozhi hello rejected: %s", e)
                        try:
                            await ws.close(code=1003)
                        except Exception:
                            pass
                        break
                elif t == "listen":
                    await sess._on_listen(obj)
                elif t == "abort":
                    await sess._on_abort(obj)
                # mcp/system 暂不处理
    except WebSocketDisconnect:
        pass
    except Exception as e:
        log.warning("xiaozhi endpoint error: %s", e)
    finally:
        await sess.close()
        log.info("xiaozhi device disconnected: session=%s binary=%d text=%d",
                 sess.session_id, binary_count, text_count)
