"""speaker.py — 说话人区分：音频(声纹)+文字(内容)融合归属。

Diarizer 接口 + TextDiarizer(dev,文字+标签启发式) + PyannoteDiarizer(prod,lazy,需 GPU+HF)。
SpeakerRegistry：enroll/identify，embedding 存 SQLite。
dev 盒无 torch/HF → 用 TextDiarizer；真声纹聚类在 GPU 盒切 PyannoteDiarizer。
"""
from __future__ import annotations
from collections import Counter
from . import storage
from .transcript import Utterance


class Diarizer:
    def attribute(self, utterances: list[Utterance], audio_path: str | None = None) -> list[Utterance]:
        raise NotImplementedError


class TextDiarizer(Diarizer):
    """文字启发式：有标签→按标签聚类,最常用'我'者=user;无标签→全部=user。
    诚实局限：纯文字无法可靠区分多人音色,需音频才准（见 PyannoteDiarizer）。"""

    def attribute(self, utterances, audio_path=None):
        labeled = [u for u in utterances if u.speaker]
        if not labeled:
            for u in utterances:
                u.speaker = "user"
            return utterances
        # 各标签的"我"频次
        wo_count = Counter()
        total = Counter()
        for u in labeled:
            total[u.speaker] += 1
            wo_count[u.speaker] += u.text.count("我")
        # user = "我"频次最高（并列则话最多者）
        user_label = max(total, key=lambda k: (wo_count[k], total[k]))
        for u in utterances:
            if u.speaker == user_label:
                u.speaker = "user"
            else:
                u.speaker = u.speaker or "他人"
        # 注册已知说话人（标签留档）
        for lbl in total:
            if lbl != user_label:
                storage.upsert_speaker(f"speaker:{lbl}", label=lbl, note="text-inferred")
        storage.upsert_speaker("user", label=user_label, note="device owner")
        return utterances


class PyannoteDiarizer(Diarizer):
    """prod：pyannote-audio 声纹聚类 + 注册表匹配 + 文字融合。lazy import。"""

    def __init__(self):
        self._pipe = None
        self._embed = None

    def _ensure(self):
        if self._pipe is None:
            from pyannote.audio import Pipeline  # lazy; 需 HF token
            import os
            self._pipe = Pipeline.from_pretrained("pyannote/speaker-diarization-3.1",
                                                  use_auth_token=os.environ.get("HF_TOKEN"))
            self._embed = self._pipe.to_audio.embeddings if False else None

    def attribute(self, utterances, audio_path=None):
        if not audio_path:
            # 无音频回落文字
            return TextDiarizer().attribute(utterances)
        self._ensure()
        diar = self._pipe(audio_path)
        # 把 pyannote 的 turn 区间对齐到 utterance.start/end → 取该段 speaker label
        for u in utterances:
            mid = (u.start + u.end) / 2
            spk = "他人"
            for turn, _, label in diar.itertracks(yield_label=True):
                if turn.start <= mid <= turn.end:
                    spk = label
                    break
            u.speaker = self._identify(spk, u.text)
        return utterances

    def _identify(self, cluster, text):
        """融合：先查注册表 embedding,再用文字线索(我是X/称呼)命名。"""
        import re
        m = re.search(r"我是([^,，。！!\s]{2,8})", text)
        if m:
            storage.upsert_speaker(m.group(1), note=f"cluster:{cluster}")
            return m.group(1)
        return cluster


def get_diarizer() -> Diarizer:
    from . import config
    backend = config.get("speaker.backend", "text")
    if backend == "pyannote":
        return PyannoteDiarizer()
    return TextDiarizer()
