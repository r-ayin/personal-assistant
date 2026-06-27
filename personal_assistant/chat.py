"""chat.py — 被动对话：人格档案(system prompt) + 记忆检索 → LLM 回复。

respond(user_msg): 取当前人格档案 + 检索 top-5 相关记忆，拼 system prompt，LLM 回复。
"""
from __future__ import annotations
import json

from . import distill, memory, storage
from .llm import get_llm, get_embedder


class Assistant:
    def __init__(self, llm=None, embedder=None):
        self.llm = llm or get_llm()
        self.embedder = embedder or get_embedder()

    def _system_prompt(self, user_msg: str) -> str:
        profile = distill.current_profile()
        hits = memory.search(user_msg, k=5, embedder=self.embedder)
        mem_snip = [{"kind": h["memory"].get("kind"), "content": h["memory"].get("content")}
                    for h in hits]
        return (
            "[TASK:CHAT]\n"
            "你是用户的个人助手，是他的'数字分身'。用他的风格、懂他的过往来回应。\n"
            "当前你对其人格的理解（人格档案）：\n"
            + json.dumps(profile, ensure_ascii=False)
            + "\n\n相关记忆：\n"
            + json.dumps(mem_snip, ensure_ascii=False)
            + "\n\n用第一人称、温暖、简短地回应。必要时引用他的经历。"
        )

    def respond(self, user_msg: str) -> str:
        user = f"User says: {user_msg}"
        return self.llm.chat(self._system_prompt(user_msg), user)
