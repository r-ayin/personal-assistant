"""web.py — 联网搜索（可插拔）。免 key 默认 Bing HTML；可切 ApiWebSearcher(Tavily/Generic 等用户自配搜索 API)。

config web.backend: bing(默认) | baidu | api | deepseek | stub
config web.api: {format: tavily|generic, api_key, base_url, query_param, ...}
deepseek 后端复用当前 LLM 上游凭据，走 Responses API 的托管 web_search 工具。
"""
from __future__ import annotations
import html as _html
import json
import re
import urllib.parse
import urllib.request
from datetime import datetime

from . import config


class WebSearcher:
    def search(self, query: str, n: int = 10) -> list[dict]:
        """返回 [{'title','url','snippet'}]。"""
        raise NotImplementedError


def _fetch(url: str, timeout: int = 15) -> str:
    req = urllib.request.Request(
        url, headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                                   "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0 Safari/537.36"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read().decode("utf-8", "replace")


def _post_json(url: str, body: dict, headers: dict | None = None, timeout: int = 20) -> dict:
    data = json.dumps(body, ensure_ascii=False).encode("utf-8")
    h = {"Content-Type": "application/json"}
    h.update(headers or {})
    req = urllib.request.Request(url, data=data, headers=h, method="POST")
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read().decode("utf-8", "replace"))


def _strip_tags(s: str) -> str:
    return _html.unescape(re.sub(r"<[^>]+>", "", s)).strip()


def _by_path(obj, path: str):
    cur = obj
    for p in path.split("."):
        if isinstance(cur, dict) and p in cur:
            cur = cur[p]
        elif isinstance(cur, list) and p.isdigit() and int(p) < len(cur):
            cur = cur[int(p)]
        else:
            return None
    return cur


class BingWebSearcher(WebSearcher):
    def search(self, query: str, n: int = 10) -> list[dict]:
        url = "https://www.bing.com/search?q=" + urllib.parse.quote(query) + "&setlang=zh-Hans"
        try:
            doc = _fetch(url)
        except Exception as e:
            print(f"[web] bing fetch fail: {e}")
            return []
        out = []
        for m in re.finditer(r'<li class="b_algo"[^>]*>(.*?)</li>', doc, re.S):
            block = m.group(1)
            tm = re.search(r'<h2[^>]*>\s*<a[^>]*href="([^"]+)"[^>]*>(.*?)</a>', block, re.S)
            if not tm:
                continue
            u, t = tm.group(1), _strip_tags(tm.group(2))
            sm = re.search(r'<p[^>]*>(.*?)</p>', block, re.S)
            s = _strip_tags(sm.group(1)) if sm else ""
            if t:
                out.append({"title": t, "url": u, "snippet": s})
            if len(out) >= n:
                break
        return out


class BaiduWebSearcher(WebSearcher):
    def search(self, query: str, n: int = 10) -> list[dict]:
        url = "https://www.baidu.com/s?wd=" + urllib.parse.quote(query)
        try:
            doc = _fetch(url)
        except Exception as e:
            print(f"[web] baidu fetch fail: {e}")
            return []
        out = []
        for m in re.finditer(r'<h3[^>]*>\s*<a[^>]*href="([^"]+)"[^>]*>(.*?)</a>', doc, re.S):
            u, t = m.group(1), _strip_tags(m.group(2))
            if t:
                out.append({"title": t, "url": u, "snippet": ""})
            if len(out) >= n:
                break
        return out


class ApiWebSearcher(WebSearcher):
    """用户自配搜索 API。支持 tavily / generic(JSON GET)。

    tavily: POST https://api.tavily.com/search {api_key,query,max_results} → {results:[{title,url,content}]}
    generic: GET {base_url}?{query_param}=q&{num_param}=n [&{key_param}=key] → {result_path:[{title_field,url_field,snippet_field}]}
    """

    def __init__(self):
        c = config.get("web.api", {})
        self.fmt = c.get("format", "tavily")
        self.api_key = c.get("api_key", "")
        self.base_url = c.get("base_url", "")
        self.query_param = c.get("query_param", "q")
        self.num_param = c.get("num_param", "num")
        self.key_param = c.get("key_param", "api_key")
        self.result_path = c.get("result_path", "results")
        self.title_field = c.get("title_field", "title")
        self.url_field = c.get("url_field", "url")
        self.snippet_field = c.get("snippet_field", "content")

    def search(self, query: str, n: int = 10) -> list[dict]:
        if not self.api_key and self.fmt == "tavily":
            print("[web] api backend 未配 api_key（设 TAVILY_API_KEY 或 web.api.api_key）")
            return []
        try:
            if self.fmt == "tavily":
                return self._tavily(query, n)
            return self._generic(query, n)
        except Exception as e:
            print(f"[web] api search fail: {e}")
            return []

    def _tavily(self, query: str, n: int) -> list[dict]:
        data = _post_json("https://api.tavily.com/search",
                          {"api_key": self.api_key, "query": query,
                           "max_results": n, "search_depth": "basic"})
        return [{"title": r.get("title", ""), "url": r.get("url", ""),
                 "snippet": r.get("content", "")} for r in data.get("results", [])]

    def _generic(self, query: str, n: int) -> list[dict]:
        if not self.base_url:
            return []
        params = {self.query_param: query, self.num_param: str(n)}
        if self.api_key and self.key_param:
            params[self.key_param] = self.api_key
        url = self.base_url + ("&" if "?" in self.base_url else "?") + urllib.parse.urlencode(params)
        req = urllib.request.Request(url, headers={"User-Agent": "personal-assistant/0.3"})
        with urllib.request.urlopen(req, timeout=20) as r:
            data = json.loads(r.read().decode("utf-8", "replace"))
        rows = _by_path(data, self.result_path) or []
        out = []
        for row in rows:
            if isinstance(row, dict):
                out.append({"title": str(row.get(self.title_field, "")),
                            "url": str(row.get(self.url_field, "")),
                            "snippet": str(row.get(self.snippet_field, ""))})
            if len(out) >= n:
                break
        return out


def _norm_hit(raw) -> dict:
    """把搜索后端返回的单条结果归一化成 {title,url,snippet}，容忍字段别名。"""
    if isinstance(raw, dict):
        return {"title": str(raw.get("title") or raw.get("name") or "")[:80],
                "url": str(raw.get("url") or raw.get("link") or "")[:120],
                "snippet": str(raw.get("snippet") or raw.get("content")
                               or raw.get("summary") or "")[:200]}
    return {"title": "", "url": "", "snippet": str(raw)[:200]}


class DeepSeekWebSearcher(WebSearcher):
    """DeepSeek Responses API 的托管 web_search 工具（服务端执行搜索）。

    凭据复用当前激活的 LLM 上游（llm.<backend> 的 base_url/api_key/model）——
    联网与对话同一个 key，不新增配置项。响应 output 里 web_search_call 项带
    query/results/sources，取结构化结果；取不到时把 output_text 整体作为单条
    snippet 兜底（它来自已联网的模型回答，仍是真实依据而非编造）。
    服务端搜索耗时数秒，故类上带 timeout 属性供 chat 侧放宽（默认 3s 不够）。
    """
    timeout = 45.0

    def _creds(self) -> tuple[str, str, str]:
        backend = config.get("llm.backend", "openai_compat")
        sec = config.get(f"llm.{backend}", {}) or {}
        return (str(sec.get("base_url", "")).rstrip("/"),
                str(sec.get("api_key", "")),
                str(sec.get("model", "")))

    def search(self, query: str, n: int = 10) -> list[dict]:
        base, key, model = self._creds()
        if not base or not key:
            print("[web] deepseek backend 缺 base_url/api_key（沿用当前 LLM 上游配置）")
            return []
        # 实测不给日期时模型会多轮搜索反复确认「今天」，耗时翻倍；直接喂服务器日期。
        now = datetime.now().astimezone()
        prompt = (f"服务器当前日期：{now:%Y-%m-%d}（星期{'一二三四五六日'[now.weekday()]}）。\n"
                  f"用户查询：{query}")
        try:
            data = _post_json(f"{base}/responses",
                              {"model": model, "input": prompt,
                               "tools": [{"type": "web_search"}]},
                              headers={"Authorization": f"Bearer {key}"},
                              timeout=int(self.timeout))
        except Exception as e:
            print(f"[web] deepseek responses fail: {e}")
            return []
        out = []
        queries: list[str] = []
        commentary: list[str] = []
        final = ""
        for item in data.get("output", []) or []:
            if not isinstance(item, dict):
                continue
            if item.get("type") == "web_search_call":
                action = item.get("action") or {}
                queries.extend(q for q in (action.get("queries") or [])
                               if isinstance(q, str) and not q.startswith("ws_call_id="))
            elif item.get("type") == "message":
                text = "\n".join(c.get("text", "") for c in (item.get("content") or [])
                                 if isinstance(c, dict) and c.get("text"))
                if not text:
                    continue
                if item.get("phase") == "final_answer":
                    final = text
                else:
                    commentary.append(text)
        # 实测：web_search_call 只回搜索词、不回结果文档；接地内容在 message 文本里，
        # 且 DeepSeek 顶层不给 output_text（与 OpenAI Responses 不同）。
        grounded = final or (commentary[-1] if commentary else "") or (data.get("output_text") or "")
        grounded = grounded.strip()
        if grounded:
            title = ("联网搜索 " + " / ".join(queries[:2]))[:80] if queries else query[:80]
            out.append({"title": title, "url": "", "snippet": grounded})
        return out[:n]


class StubWebSearcher(WebSearcher):
    def search(self, query: str, n: int = 10) -> list[dict]:
        return []


def get_searcher() -> WebSearcher:
    backend = config.get("web.backend", "bing")
    if backend == "baidu":
        return BaiduWebSearcher()
    if backend == "api":
        return ApiWebSearcher()
    if backend == "deepseek":
        return DeepSeekWebSearcher()
    if backend == "stub":
        return StubWebSearcher()
    return BingWebSearcher()
