"""speaker.py — 说话人区分：远程 diarize + 自算 MFCC 声纹→角色库。

Diarizer 接口 + TextDiarizer（纯文字启发式，兜底）+ RemoteDiarizer（调 ASR 的
/v1/diarize，单文件内聚类 S1/S2…）。
SpeakerRegistry：跨文件的"声纹→角色"库，MFCC 向量存 speakers.embedding；
每个录音文件的簇声纹存 voiceprint_clusters，供 `speakers assign` 校准入库。

诚实局限：/v1/diarize 只做单文件聚类、不给音频嵌入，所以跨文件稳定对应靠本地
MFCC 余弦匹配；匹配不上的簇标 S? 等校准，不瞎猜角色。
"""
from __future__ import annotations

import json
import urllib.request
from collections import Counter

import numpy as np

from . import config, storage, voiceprint
from .transcript import Utterance


class Diarizer:
    def attribute(self, utterances: list[Utterance], audio_path: str | None = None) -> list[Utterance]:
        raise NotImplementedError


class TextDiarizer(Diarizer):
    """文字启发式：有标签→按标签聚类,最常用'我'者=user;无标签→全部=user。
    诚实局限：纯文字无法可靠区分多人音色,需音频才准（见 RemoteDiarizer）。"""

    def attribute(self, utterances, audio_path=None):
        labeled = [u for u in utterances if u.speaker]
        if not labeled:
            for u in utterances:
                u.speaker = "user"
            return utterances
        wo_count = Counter()
        total = Counter()
        for u in labeled:
            total[u.speaker] += 1
            wo_count[u.speaker] += u.text.count("我")
        user_label = max(total, key=lambda k: (wo_count[k], total[k]))
        for u in utterances:
            if u.speaker == user_label:
                u.speaker = "user"
            else:
                u.speaker = u.speaker or "他人"
        for lbl in total:
            if lbl != user_label:
                storage.upsert_speaker(f"speaker:{lbl}", label=lbl, note="text-inferred")
        storage.upsert_speaker("user", label=user_label, note="device owner")
        return utterances


class SpeakerRegistry:
    """声纹→角色库。identify 余弦匹配 speakers.embedding，阈值内才认。"""

    def __init__(self, threshold: float | None = None):
        self.threshold = (threshold if threshold is not None
                          else float(config.get("speaker.voiceprint_threshold", 0.92)))

    def best_match(self, vec: np.ndarray):
        best, best_sim = None, -1.0
        for row in storage.speakers_with_embedding():
            sim = voiceprint.cosine(vec, voiceprint.unpack(row["embedding"]))
            if sim > best_sim:
                best, best_sim = row["name"], sim
        return best, best_sim

    def identify(self, vec: np.ndarray):
        best, sim = self.best_match(vec)
        return best if sim >= self.threshold else None

    def enroll(self, role: str, vec: np.ndarray, seconds: float = 0.0):
        """入库/增量更新：与已有声纹做等权平均，计数记在 note 里。"""
        row = storage.get_speaker(role)
        n = 1
        if row and row.get("embedding"):
            old = voiceprint.unpack(row["embedding"])
            note = row.get("note") or ""
            if note.startswith("voiceprint n="):
                try:
                    n = int(note.split("n=")[1])
                except ValueError:
                    n = 1
            vec = (old * n + vec) / (n + 1)
            vec = vec / (np.linalg.norm(vec) or 1.0)
            n += 1
        storage.upsert_speaker(role, label=(row or {}).get("label") or role,
                               embedding=voiceprint.pack(vec.astype(np.float32)),
                               note=f"voiceprint n={n} +{seconds:.1f}s")


class RemoteDiarizer(Diarizer):
    """调 ASR 的 /v1/diarize（与转写同 token），拿单文件聚类 + 本地声纹归角色。"""

    def __init__(self):
        c = config.get("speaker.remote", {}) or {}
        self.base = (c.get("base_url") or config.get("asr.remote_whisper.base_url") or "").rstrip("/")
        self.key = c.get("api_key") or config.get("asr.remote_whisper.api_key") or ""
        self.registry = SpeakerRegistry()

    def available(self) -> bool:
        return bool(self.base)

    def diarize(self, audio_path: str, num_speakers: int | None = None):
        if not self.base:
            return None
        with open(audio_path, "rb") as f:
            payload = f.read()
        boundary = "----padiarize7f3a"
        parts = [f"--{boundary}\r\nContent-Disposition: form-data; name=\"file\"; "
                 f"filename=\"{audio_path.rsplit('/', 1)[-1]}\"\r\n"
                 "Content-Type: application/octet-stream\r\n\r\n".encode(),
                 payload,
                 f"\r\n--{boundary}\r\nContent-Disposition: form-data; name=\"response_format\"\r\n\r\njson\r\n".encode()]
        if num_speakers:
            parts.append(f"--{boundary}\r\nContent-Disposition: form-data; name=\"num_speakers\"\r\n\r\n{num_speakers}\r\n".encode())
        parts.append(f"--{boundary}--\r\n".encode())
        req = urllib.request.Request(self.base + "/diarize", data=b"".join(parts), method="POST")
        req.add_header("Content-Type", f"multipart/form-data; boundary={boundary}")
        if self.key:
            req.add_header("Authorization", f"Bearer {self.key}")
        try:
            with urllib.request.urlopen(req, timeout=300) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except Exception:
            return None

    @staticmethod
    def _overlap_label(segs, start, end):
        best, best_ov = None, 0.0
        for s in segs:
            ov = min(end, s.get("end", 0.0)) - max(start, s.get("start", 0.0))
            if ov > best_ov:
                best, best_ov = s.get("speaker"), ov
        return best

    def _cluster_vec(self, audio_path, ranges):
        try:
            x = voiceprint.read_pcm_mono_16k(audio_path)
        except Exception:
            return None
        chunks = []
        for b, e in ranges:
            a, b2 = int(b * voiceprint.SAMPLE_RATE), min(int(e * voiceprint.SAMPLE_RATE), len(x))
            if b2 - a >= voiceprint.FRAME:
                chunks.append(x[a:b2])
        if not chunks:
            return None
        return voiceprint.voiceprint(np.concatenate(chunks))

    def label_segments(self, segments, audio_path: str):
        """给带 start_sec/end_sec 的 segment 列表就地标角色。返回 {簇: 角色|None}。"""
        d = self.diarize(audio_path)
        if not d:
            return {}
        segs = d.get("segments") or []
        fname = audio_path.rsplit("/", 1)[-1]
        clusters: dict[str, list] = {}
        for s in segments:
            lab = self._overlap_label(segs, s.start_sec, s.end_sec) or "S?"
            s.speaker = lab
            clusters.setdefault(lab, []).append((s.start_sec, s.end_sec))
        info: dict[str, str | None] = {}
        for lab, ranges in sorted(clusters.items()):
            vec = self._cluster_vec(audio_path, ranges)
            if vec is None:
                info[lab] = None
                continue
            secs = sum(e - b for b, e in ranges)
            storage.upsert_cluster(fname, lab, voiceprint.pack(vec), secs)
            role = self.registry.identify(vec)
            info[lab] = role
            if role:
                for s in segments:
                    if s.speaker == lab:
                        s.speaker = role
        return info

    def attribute(self, utterances, audio_path=None):
        if not audio_path or not self.available():
            return TextDiarizer().attribute(utterances, audio_path)
        d = self.diarize(audio_path)
        if not d:
            return TextDiarizer().attribute(utterances, audio_path)
        segs = d.get("segments") or []
        fname = audio_path.rsplit("/", 1)[-1]
        clusters: dict[str, list] = {}
        for u in utterances:
            lab = self._overlap_label(segs, u.start, u.end) or "S?"
            u.speaker = lab
            clusters.setdefault(lab, []).append((u.start, u.end))
        for lab, ranges in sorted(clusters.items()):
            vec = self._cluster_vec(audio_path, ranges)
            if vec is None:
                continue
            storage.upsert_cluster(fname, lab, voiceprint.pack(vec), sum(e - b for b, e in ranges))
            role = self.registry.identify(vec)
            if role:
                for u in utterances:
                    if u.speaker == lab:
                        u.speaker = role
        return utterances


def get_diarizer() -> Diarizer:
    backend = config.get("speaker.backend", "text")
    if backend == "remote":
        d = RemoteDiarizer()
        if d.available():
            return d
    return TextDiarizer()
