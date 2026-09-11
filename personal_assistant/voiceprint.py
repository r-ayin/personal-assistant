"""voiceprint.py — 自算 MFCC 声纹，维护"声纹→角色"对应库。

ASR 的 /v1/diarize 只做单文件内聚类（S1/S2…），不给音频嵌入、也没有服务端
注册接口，所以跨文件的稳定角色对应必须在本地建：对每段音频切片算 MFCC 均值+
标准差向量入库，新录音的每个簇跟库里角色做余弦匹配，阈值内归角色、阈值外标
未知等校准。只依赖 numpy + stdlib wave。

仅支持 16-bit PCM WAV；其它格式（mp3/m4a/flac）若机器上有 ffmpeg 则先转码，
否则该文件只做单文件 diarize、不入库声纹（降级但不报错）。
"""
from __future__ import annotations

import shutil
import subprocess
import tempfile
import wave
from pathlib import Path

import numpy as np

SAMPLE_RATE = 16000
N_FILT = 26
N_CEP = 13
FRAME = 400   # 25ms @16k
STEP = 160    # 10ms @16k


def _hz2mel(hz: float) -> float:
    return 2595.0 * np.log10(1.0 + hz / 700.0)


def _mel2hz(mel: float) -> float:
    return 700.0 * (10.0 ** (mel / 2595.0) - 1.0)


def read_pcm_mono_16k(path: str | Path) -> np.ndarray:
    """读成 16k 单声道 float32 [-1,1]。非 WAV 时尝试 ffmpeg 转码。"""
    p = Path(path)
    tmp = None
    if p.suffix.lower() != ".wav":
        ffmpeg = shutil.which("ffmpeg")
        if not ffmpeg:
            raise ValueError(f"非 WAV 且无 ffmpeg，无法解码: {p.name}")
        tmp = tempfile.NamedTemporaryFile(suffix=".wav", delete=False)
        tmp.close()
        subprocess.run(
            [ffmpeg, "-y", "-i", str(p), "-ar", str(SAMPLE_RATE), "-ac", "1", tmp.name],
            check=True, capture_output=True,
        )
        p = Path(tmp.name)
    try:
        with wave.open(str(p), "rb") as w:
            ch, sw, rate = w.getnchannels(), w.getsampwidth(), w.getframerate()
            if sw != 2:
                raise ValueError(f"仅支持 16-bit PCM, 实际 sampwidth={sw}")
            raw = w.readframes(w.getnframes())
        x = np.frombuffer(raw, dtype="<i2").astype(np.float32) / 32768.0
        if ch > 1:
            x = x.reshape(-1, ch).mean(axis=1)
        if rate != SAMPLE_RATE:
            n2 = max(1, int(len(x) * SAMPLE_RATE / rate))
            x = np.interp(np.linspace(0, max(0, len(x) - 1), n2),
                          np.arange(len(x)), x).astype(np.float32)
        return x
    finally:
        if tmp:
            try:
                os_unlink(tmp.name)
            except OSError:
                pass


def os_unlink(p: str) -> None:
    import os
    os.unlink(p)


def _frames(x: np.ndarray) -> np.ndarray:
    if len(x) < FRAME:
        x = np.pad(x, (0, FRAME - len(x)))
    n = 1 + (len(x) - FRAME) // STEP
    idx = (np.arange(n)[:, None] * STEP + np.arange(FRAME)[None, :])
    return x[idx] * np.hamming(FRAME)


def _mel_filterbank(n_filt: int, n_fft: int, rate: int) -> np.ndarray:
    lo, hi = _hz2mel(0.0), _hz2mel(rate / 2.0)
    edges = _mel2hz(np.linspace(lo, hi, n_filt + 2))
    bins = np.floor((n_fft + 1) * edges / rate).astype(int)
    fb = np.zeros((n_filt, n_fft // 2 + 1))
    for i in range(n_filt):
        for j in range(bins[i], bins[i + 1]):
            fb[i, j] = (j - bins[i]) / max(1, bins[i + 1] - bins[i])
        for j in range(bins[i + 1], bins[i + 2]):
            fb[i, j] = (bins[i + 2] - j) / max(1, bins[i + 2] - bins[i + 1])
    return fb


def _dct_mat(k: int, n: int) -> np.ndarray:
    return np.cos(np.pi * np.arange(1, k + 1)[:, None] * (2 * np.arange(n)[None, :] + 1) / (2 * n))


def voiceprint(x: np.ndarray) -> np.ndarray:
    """MFCC 均值+标准差拼接向量（26 维），L2 归一化。"""
    fr = _frames(x)
    spec = np.abs(np.fft.rfft(fr, axis=1)) ** 2 / FRAME
    fb = _mel_filterbank(N_FILT, FRAME, SAMPLE_RATE)
    logmel = np.log(spec @ fb.T + 1e-9)
    cep = logmel @ _dct_mat(N_CEP, N_FILT).T
    vec = np.concatenate([cep.mean(axis=0), cep.std(axis=0)])
    n = np.linalg.norm(vec)
    return (vec / n if n > 0 else vec).astype(np.float32)


def voiceprint_of_slice(path: str | Path, start: float, end: float) -> np.ndarray:
    x = read_pcm_mono_16k(path)
    a, b = int(start * SAMPLE_RATE), int(end * SAMPLE_RATE)
    b = min(b, len(x))
    if b - a < FRAME:
        raise ValueError("切片太短，不足以算声纹")
    return voiceprint(x[a:b])


def cosine(a: np.ndarray, b: np.ndarray) -> float:
    na, nb = np.linalg.norm(a), np.linalg.norm(b)
    if na == 0 or nb == 0:
        return 0.0
    return float(np.dot(a, b) / (na * nb))


def pack(vec: np.ndarray) -> bytes:
    return vec.astype("<f4").tobytes()


def unpack(blob: bytes) -> np.ndarray:
    return np.frombuffer(blob, dtype="<f4")
