"""speaker.py — 说话人区分：文字(内容)启发式归属。

Diarizer 接口 + TextDiarizer(文字+标签启发式)。
SpeakerRegistry：enroll/identify，embedding 存 SQLite。
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


def get_diarizer() -> Diarizer:
    return TextDiarizer()
