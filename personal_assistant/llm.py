"""llm.py — 可插拔 LLM 与 Embedder。stdlib + numpy，零三方 SDK。

后端：stub(智能桩,驱动管线) | anthropic_proxy(会话代理,实测) | ollama | openai_compat(GLM/兼容)。
Embedder：hashing(确定性,零网络) | openai_compat。
所有真实后端用 urllib 直发 HTTP，避免 anthropic/openai SDK 依赖（本机 pip 装不了）。
"""
from __future__ import annotations
import json
import re
import hashlib
import urllib.request
import urllib.error
from abc import ABC, abstractmethod

import numpy as np

from . import config

# ── JSON 提取（LLM 输出常带 ```json 或散文）──────────────────────────
def extract_json(text: str):
    if not text:
        return None
    fence = re.search(r"```(?:json)?\s*(.*?)```", text, re.S)
    cand = fence.group(1) if fence else text
    try:
        return json.loads(cand)
    except Exception:
        pass
    for m in re.finditer(r"[\[{]", cand):
        start = m.start()
        depth = 0
        for i in range(start, len(cand)):
            if cand[i] in "[{":
                depth += 1
            elif cand[i] in "]}":
                depth -= 1
                if depth == 0:
                    try:
                        return json.loads(cand[start:i + 1])
                    except Exception:
                        break
    return None


class LLMClient(ABC):
    @abstractmethod
    def chat(self, system: str, user: str, temperature: float = 0.3) -> str: ...

    def chat_json(self, system: str, user: str, temperature: float = 0.2):
        return extract_json(self.chat(system, user, temperature))


class Embedder(ABC):
    @abstractmethod
    def embed(self, texts: list[str]) -> list[np.ndarray]: ...
    def embed_one(self, text: str) -> np.ndarray:
        return self.embed([text])[0]


# ── 智能桩 LLM：按 [TASK:...] 标记产出结构化结果，真实驱动管线 ────
class StubLLM(LLMClient):
    """不联网的确定性桩。解析 prompt 里的 JSON 输入块，产出合法结构化输出。"""

    def chat(self, system: str, user: str, temperature: float = 0.3) -> str:
        prompt = system + "\n" + user
        task = ""
        m = re.search(r"\[TASK:([A-Z_]+)\]", prompt)
        if m:
            task = m.group(1)
        if task == "EXTRACT_MEMORIES":
            return json.dumps(self._extract(prompt), ensure_ascii=False)
        if task == "DISTILL":
            return json.dumps(self._distill(prompt), ensure_ascii=False)
        if task == "EXTRACT_EVENTS":
            return json.dumps(self._extract_events(prompt), ensure_ascii=False)
        if task == "EXTRACT_REMINDERS":
            return json.dumps(self._extract_reminders(prompt), ensure_ascii=False)
        if task == "RESOLVE_TIME":
            return json.dumps(self._resolve_time_stub(prompt), ensure_ascii=False)
        if task == "RESOLVE_RANGE":
            return json.dumps(self._resolve_range_stub(prompt), ensure_ascii=False)
        if task == "RECOMMEND":
            return json.dumps(self._recommend(prompt), ensure_ascii=False)
        if task == "BUILD_WIKI":
            return json.dumps(self._build_wiki(prompt), ensure_ascii=False)
        if task == "INTERVENTION":
            return self._intervention(prompt)
        # CHAT / 默认
        return self._chat(prompt)

    def _block_json(self, prompt: str, after_marker: str):
        idx = prompt.find(after_marker)
        if idx < 0:
            return None
        rest = prompt[idx + len(after_marker):]
        return extract_json(rest)

    def _extract(self, prompt: str) -> list[dict]:
        segs = self._block_json(prompt, "Segments (JSON):")
        if not isinstance(segs, list):
            segs = [{"id": "s1", "text": "（样例）今天和朋友去爬山了，很开心。"}]
        out = []
        pref_kw = ["喜欢", "爱", "讨厌", "不想", "偏好", "最爱的"]
        int_kw = ["打算", "准备", "要去", "想去做", "应该", "计划", "明天要", "下周"]
        emo_kw = [("累", "tired"), ("烦", "annoyed"), ("开心", "happy"),
                  ("难过", "sad"), ("焦虑", "anxious"), ("兴奋", "excited")]
        for s in segs:
            sid = s.get("id", "?")
            text = s.get("text", "")
            out.append({"kind": "event", "content": text[:200],
                         "segment_id": sid, "evidence": f"segment:{sid}"})
            for kw in pref_kw:
                if kw in text:
                    out.append({"kind": "preference", "content": text[:200],
                                 "segment_id": sid, "evidence": f"segment:{sid} (kw:{kw})"})
                    break
            for kw in int_kw:
                if kw in text:
                    out.append({"kind": "intention", "content": text[:200],
                                 "segment_id": sid, "evidence": f"segment:{sid} (kw:{kw})"})
                    break
            for kw, lab in emo_kw:
                if kw in text:
                    out.append({"kind": "emotion", "content": lab,
                                 "segment_id": sid, "evidence": f"segment:{sid} (kw:{kw})"})
                    break
        return out

    def _distill(self, prompt: str) -> dict:
        mems = self._block_json(prompt, "Recent memories (JSON):")
        if not isinstance(mems, list):
            mems = []
        contents = [m.get("content", "") for m in mems if isinstance(m, dict)]
        blob = " ".join(contents)[:600]
        prefs = [m["content"] for m in mems if isinstance(m, dict) and m.get("kind") == "preference"][:5]
        intents = [m["content"] for m in mems if isinstance(m, dict) and m.get("kind") == "intention"][:5]
        profile = {
            "personality": f"根据 {len(mems)} 条记忆归纳：活跃、善表达。" + (f" 关键内容：{blob[:200]}" if blob else ""),
            "values": "重视关系与体验。",
            "goals": "；".join(intents) if intents else "（暂无明显长期目标）",
            "habits": {"social": "频繁提及他人", "topics": list({c[:12] for c in contents})[:5]},
            "skills": [],
            "knowledge": [{"topic": "日常生活", "level": "rich", "evidence": f"{len(contents)} 条相关记忆"}],
            "thinking_patterns": "偏感性叙述，少结构化推理。",
            "preferences": prefs if prefs else ["（待积累）"],
            "affective_baseline": "情绪随事件波动，整体偏积极。",
        }
        return {"profile": profile,
                "change_summary": f"从 {len(mems)} 条记忆蒸馏人格档案 v1（stub 归纳）。"}

    def _intervention(self, prompt: str) -> str:
        mems = self._block_json(prompt, "Triggering memories (JSON):")
        n = len(mems) if isinstance(mems, list) else 0
        return (f"（stub 建议）注意到你近期 {n} 条相关记录。"
                "也许可以安排一段安静时间整理一下这些事，需要我帮你梳理个清单吗？")

    def _time_expr(self, text: str):
        pats = [r"(大前天|前天|昨天|今天|明天|后天|大后天)",
                r"((?:上|这|本|下)周[一二三四五六日天])",
                r"(\d{1,2}月\d{1,2}[日号])",
                r"((?:上午|下午|晚上|早上|凌晨)?\s*\d{1,2}\s*[点时](?:\d{1,2}分|半)?)"]
        for p in pats:
            m = re.search(p, text)
            if m:
                return m.group(1)
        return None

    def _extract_events(self, prompt: str) -> list[dict]:
        segs = self._block_json(prompt, "Utterances (JSON):")
        if not isinstance(segs, list):
            return []
        out = []
        for s in segs:
            text = s.get("text", "")
            t = self._time_expr(text)
            if t:
                out.append({"title": text[:20], "when_raw": t, "who": s.get("speaker", ""),
                            "where": "", "id": s.get("id", "")})
        return out

    def _extract_reminders(self, prompt: str) -> list[dict]:
        segs = self._block_json(prompt, "Utterances (JSON):")
        if not isinstance(segs, list):
            return []
        out = []
        rec_kw = [("每天", "daily"), ("每周", "weekly"), ("每月", "monthly")]
        intent_kw = ["提醒", "要", "得", "该", "准备", "打算", "别忘", "需要", "开会", "交"]
        for s in segs:
            text = s.get("text", "")
            t = self._time_expr(text)
            if not t:
                continue
            if not any(k in text for k in intent_kw) and not any(k in text for k, _ in rec_kw):
                continue
            rec = ""
            for k, v in rec_kw:
                if k in text:
                    rec = v
                    break
            out.append({"what": text[:30], "when_raw": t, "recurring": rec, "id": s.get("id", "")})
        return out

    def _resolve_time_stub(self, prompt: str) -> dict:
        from .temporal import resolve
        from datetime import datetime
        expr, ref = "", datetime.now()
        m = re.search(r"Raw expr:\s*(.*)", prompt)
        if m:
            expr = m.group(1).strip().split("\n")[0]
        m2 = re.search(r"Reference\(ISO\):\s*([^\s]+)", prompt)
        if m2:
            try:
                ref = datetime.fromisoformat(m2.group(1))
            except Exception:
                pass
        r = resolve(expr, ref)
        return {"dt": r[0].isoformat(timespec="minutes"), "precision": r[1]} if r else {"dt": None}

    def _resolve_range_stub(self, prompt: str) -> dict:
        from .temporal import resolve_range
        from datetime import datetime
        q, ref = "", datetime.now()
        m = re.search(r"Query:\s*(.*)", prompt)
        if m:
            q = m.group(1).strip().split("\n")[0]
        m2 = re.search(r"Reference\(ISO\):\s*([^\s]+)", prompt)
        if m2:
            try:
                ref = datetime.fromisoformat(m2.group(1))
            except Exception:
                pass
        s, e = resolve_range(q, ref)
        return {"start": s, "end": e}

    def _recommend(self, prompt: str) -> list[dict]:
        """从【真实联网搜索结果】里挑，不写死。无结果→空。"""
        prof = self._block_json(prompt, "Persona (JSON):")
        prof = prof if isinstance(prof, dict) else {}
        results = self._block_json(prompt, "Web search results (real, JSON):")
        dims = [d for d in ("preferences", "personality", "goals", "habits",
                            "knowledge", "skills", "values", "affective_baseline")
                if prof.get(d)]
        base = dims[0] if dims else "personality"
        if not isinstance(results, list) or not results:
            return []
        out = []
        for r in results[:3]:
            title = (r.get("title") or r.get("snippet") or "").strip()[:60]
            if title:
                out.append({"item": title, "reason": f"来自联网搜索，结合你的{base}特质", "based_on": base})
        return out

    def _build_wiki(self, prompt: str) -> list[dict]:
        """增量：新记忆按 kind 分组；已有页匹配该 kind→扩展(union source_ids+body 覆盖旧+新)；否则建新页。"""
        new_mems = self._block_json(prompt, "New memories (JSON):")
        existing = self._block_json(prompt, "Existing wiki pages (JSON):")
        if not isinstance(new_mems, list):
            new_mems = []
        if not isinstance(existing, list):
            existing = []
        by_kind = {}
        for m in new_mems:
            if not isinstance(m, dict):
                continue
            by_kind.setdefault(m.get("kind", "event"), []).append(m)
        out = []
        for k, ms in by_kind.items():
            ex = None
            for p in existing:
                tags = p.get("tags", []) if isinstance(p.get("tags"), list) else []
                if k in tags or k in (p.get("title") or ""):
                    ex = p
                    break
            new_ids = [m.get("id") for m in ms if m.get("id")]
            if ex:
                old_c = ex.get("source_contents", []) or []
                body = "\n".join(f"- {c[:60]}" for c in old_c) + "\n" + \
                       "\n".join(f"- {m.get('content', '')[:60]}" for m in ms)
                src = (ex.get("source_ids", []) or []) + new_ids
                out.append({"title": ex["title"], "body": body,
                            "tags": ex.get("tags", []) or [k],
                            "source_ids": src, "links": []})
            else:
                body = "\n".join(f"- {m.get('content', '')[:60]}" for m in ms)
                out.append({"title": f"{k}主题", "body": body, "tags": [k],
                            "source_ids": new_ids, "links": []})
        return out

    def _chat(self, prompt: str) -> str:
        m = re.search(r"User says:\s*(.*)", prompt, re.S)
        msg = m.group(1).strip()[:200] if m else ""
        return (f"（stub 回复）我听到了。你说的是：{msg}。"
                "我记下了，会结合你过往的习惯慢慢懂你。")


# ── 真实 HTTP 后端（urllib 直发）─────────────────────────────────
def _post_json(url: str, headers: dict, body: dict, timeout: float = 60.0) -> dict:
    data = json.dumps(body, ensure_ascii=False).encode("utf-8")
    req = urllib.request.Request(url, data=data, headers=headers, method="POST")
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode("utf-8"))


# ── 思考程度档位 → provider 原生字段（按官方文档实测，不捏造）─────
# 档位归一：off/低/中/高 ↔ off/low/medium/high
_EFFORT_NORM = {"off": "off", "low": "low", "medium": "medium", "high": "high",
                "低": "low", "中": "medium", "高": "high"}
_EFFORT_BUDGET = {"low": 4096, "medium": 12288, "high": 24576}


def _norm_effort(effort) -> str:
    e = str(effort or "off").strip()
    return _EFFORT_NORM.get(e) or _EFFORT_NORM.get(e.lower(), "off")


def _budget_for(effort_norm: str, max_tokens: int) -> int:
    """budget 映射 低4096/中12288/高24576，clamp 到 [1024, max_tokens-1024]。
    Anthropic/GLM-anthropic 约束：budget ≥1024 且 < max_tokens。"""
    n = _EFFORT_BUDGET.get(effort_norm, 4096)
    cap = max(1024, (int(max_tokens or 4096)) - 1024)
    return min(n, cap)


def _thinking_body(effort, fmt: str, max_tokens: int):
    """off/低/中/高 → provider 原生思考字段。
    返回 (extra_fields, use_max_completion_tokens)。extra 合并入请求体。

    - glm(openai_compat 端点)：仅 thinking.type enabled/disabled，无 budget（低/中/高塌缩为开）
    - openai：reasoning_effort low/medium/high；推理模型须用 max_completion_tokens 非 max_tokens
    - qwen：enable_thinking + thinking_budget（urllib 顶层字段）
    - anthropic：thinking.{type:budget_tokens}（min 1024, < max_tokens）
    具体上限随型号变动，以官方文档为准。
    """
    e = _norm_effort(effort)
    if e == "off":
        if fmt == "glm":
            return {"thinking": {"type": "disabled"}}, False   # GLM 默认思考开，off 须显式 disable
        if fmt == "qwen":
            return {"enable_thinking": False}, False
        return {}, False                                        # anthropic/openai：省略
    if fmt == "glm":
        return {"thinking": {"type": "enabled"}}, False        # 无 budget 旋钮
    if fmt == "openai":
        return {"reasoning_effort": e}, True                   # e=low/medium/high；改发 max_completion_tokens
    if fmt == "qwen":
        return {"enable_thinking": True, "thinking_budget": _budget_for(e, max_tokens)}, False
    if fmt == "anthropic":
        return {"thinking": {"type": "enabled", "budget_tokens": _budget_for(e, max_tokens)}}, False
    return {}, False


def mask_key(k: str) -> str:
    if not k:
        return ""
    if len(k) <= 8:
        return "*" * len(k)
    return f"{k[:4]}…{k[-4:]}"


class OpenAICompatLLM(LLMClient):
    """OpenAI 兼容 /chat/completions。GLM(openai 兼容端点) / Ollama / OpenAI / Qwen 共用。
    thinking_format：glm(开/关) | openai(reasoning_effort) | qwen(enable_thinking+thinking_budget)。"""

    def __init__(self, base_url: str, api_key: str, model: str,
                 max_tokens: int = 4096, thinking_effort: str = "off",
                 thinking_format: str = "glm"):
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.model = model
        self.max_tokens = int(max_tokens or 4096)
        self.thinking_effort = thinking_effort
        self.thinking_format = thinking_format

    def chat(self, system: str, user: str, temperature: float = 0.3) -> str:
        extra, use_mct = _thinking_body(self.thinking_effort, self.thinking_format, self.max_tokens)
        body = {"model": self.model,
                "messages": [{"role": "system", "content": system},
                             {"role": "user", "content": user}]}
        if use_mct:
            # OpenAI 推理模型：max_completion_tokens（非 max_tokens），温度须 1
            body["max_completion_tokens"] = self.max_tokens
            body["temperature"] = 1
        else:
            body["max_tokens"] = self.max_tokens
            body["temperature"] = temperature
        body.update(extra)
        headers = {"Content-Type": "application/json",
                   "Authorization": f"Bearer {self.api_key}"}
        data = _post_json(f"{self.base_url}/chat/completions", headers, body)
        return data["choices"][0]["message"]["content"]


class OllamaLLM(OpenAICompatLLM):
    pass


class AnthropicProxyLLM(LLMClient):
    """Anthropic 协议（会话本地代理 / Claude / GLM-anthropic 端点）。路径不确定，依次尝试。
    thinking_format=anthropic：thinking.{type:budget_tokens}（min 1024, < max_tokens）。"""

    def __init__(self, base_url: str, api_key: str, model: str,
                 max_tokens: int = 4096, thinking_effort: str = "off",
                 thinking_format: str = "anthropic"):
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.model = model
        self.max_tokens = int(max_tokens or 4096)
        self.thinking_effort = thinking_effort
        self.thinking_format = thinking_format or "anthropic"

    def chat(self, system: str, user: str, temperature: float = 0.3) -> str:
        extra, _ = _thinking_body(self.thinking_effort, self.thinking_format, self.max_tokens)
        body = {"model": self.model, "max_tokens": self.max_tokens, "system": system,
                "messages": [{"role": "user", "content": user}]}
        body.update(extra)
        headers = {"Content-Type": "application/json",
                   "x-api-key": self.api_key, "anthropic-version": "2023-06-01"}
        last_err = None
        for path in ("/v1/messages", "/messages"):
            try:
                data = _post_json(f"{self.base_url}{path}", headers, body, timeout=90)
                if "content" in data:
                    blocks = data["content"]
                    return "".join(b.get("text", "") for b in blocks if b.get("type") == "text")
                last_err = json.dumps(data)[:200]
            except urllib.error.HTTPError as e:
                last_err = f"HTTP {e.code}: {e.read()[:200]!r}"
            except Exception as e:
                last_err = f"{type(e).__name__}: {e}"
        raise RuntimeError(f"anthropic_proxy 调用失败: {last_err}")


class GLMAnthropicLLM(AnthropicProxyLLM):
    """GLM 走 Anthropic 兼容端点(open.bigmodel.cn/api/anthropic)，支持 budget_tokens 分低/中/高。"""
    pass


# ── Embedder ────────────────────────────────────────────────────
class HashingEmbedder(Embedder):
    """确定性哈希向量：词 + 字符 bigram 投影到固定维，L2 归一。零网络。"""

    def __init__(self, dim: int = 256):
        self.dim = dim

    def embed(self, texts: list[str]) -> list[np.ndarray]:
        out = []
        for text in texts:
            vec = np.zeros(self.dim, dtype=np.float32)
            toks = re.findall(r"[\w]+", text)
            for tok in toks:
                h = int(hashlib.sha256(tok.encode()).hexdigest(), 16)
                vec[h % self.dim] += 1.0
            for i in range(len(text) - 1):
                bg = text[i:i + 2]
                h = int(hashlib.sha256(bg.encode()).hexdigest(), 16)
                vec[h % self.dim] += 0.5
            n = float(np.linalg.norm(vec))
            if n > 0:
                vec /= n
            out.append(vec)
        return out


class OpenAICompatEmbedder(Embedder):
    """/v1/embeddings。GLM embedding-3 等。"""

    def __init__(self, base_url: str, api_key: str, model: str):
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.model = model

    def embed(self, texts: list[str]) -> list[np.ndarray]:
        body = {"model": self.model, "input": texts}
        headers = {"Content-Type": "application/json",
                   "Authorization": f"Bearer {self.api_key}"}
        data = _post_json(f"{self.base_url}/embeddings", headers, body)
        return [np.array(d["embedding"], dtype=np.float32) for d in data["data"]]


# ── 工厂 ────────────────────────────────────────────────────────
def _llm_fields(sec: str) -> dict:
    """读后端字段，回落到 llm.* 全局默认（供 get_llm / effective_llm_config）。"""
    def g(f, d=None):
        return config.get(f"llm.{sec}.{f}", config.get(f"llm.{f}", d))
    return {"base_url": g("base_url", ""), "api_key": g("api_key", ""),
            "model": g("model", ""), "max_tokens": g("max_tokens", 4096),
            "thinking_effort": g("thinking_effort", "off"),
            "thinking_format": g("thinking_format", "glm")}


def get_llm() -> LLMClient:
    backend = config.get("llm.backend", "stub")
    if backend == "stub":
        return StubLLM()
    f = _llm_fields(backend)
    if backend == "anthropic_proxy":
        return AnthropicProxyLLM(f["base_url"], f["api_key"], f["model"],
                                 f["max_tokens"], f["thinking_effort"],
                                 f["thinking_format"] or "anthropic")
    if backend == "glm_anthropic":
        return GLMAnthropicLLM(f["base_url"], f["api_key"], f["model"],
                               f["max_tokens"], f["thinking_effort"], "anthropic")
    if backend == "ollama":
        return OllamaLLM(f["base_url"], f["api_key"] or "ollama", f["model"],
                         f["max_tokens"], f["thinking_effort"],
                         f["thinking_format"] or "glm")
    if backend == "openai_compat":
        return OpenAICompatLLM(f["base_url"], f["api_key"], f["model"],
                               f["max_tokens"], f["thinking_effort"],
                               f["thinking_format"] or "glm")
    if backend == "deepseek":
        # DeepSeek is OpenAI-compatible, use same client with mapped config
        return OpenAICompatLLM(f["base_url"], f["api_key"], f["model"],
                               f["max_tokens"], f["thinking_effort"],
                               f["thinking_format"] or "glm")
    raise ValueError(f"unknown llm backend: {backend}")


def effective_llm_config() -> dict:
    """供 cli llm / GET /settings/llm：生效配置（key 掩码）+ native thinking 字段预览。"""
    backend = config.get("llm.backend", "stub")
    out = {"backend": backend}
    if backend == "stub":
        return out
    f = _llm_fields(backend)
    extra, use_mct = _thinking_body(f["thinking_effort"], f["thinking_format"], f["max_tokens"])
    out.update({"model": f["model"], "base_url": f["base_url"],
                "api_key_masked": mask_key(f["api_key"]),
                "max_tokens": f["max_tokens"], "thinking_effort": f["thinking_effort"],
                "thinking_format": f["thinking_format"],
                "native_preview": extra,
                "uses_max_completion_tokens": use_mct})
    return out


def get_embedder() -> Embedder:
    backend = config.get("embedder.backend", "hashing")
    if backend == "hashing":
        return HashingEmbedder(dim=config.get("embedder.dim", 256))
    if backend == "openai_compat":
        c = config.get("embedder.openai_compat", {})
        return OpenAICompatEmbedder(c.get("base_url", ""), c.get("api_key", ""), c.get("model", ""))
    raise ValueError(f"unknown embedder backend: {backend}")
