"""web.py — 联网搜索（可插拔）。免 key 默认 Bing HTML；可切 ApiWebSearcher(Tavily/Generic 等用户自配搜索 API)。

config web.backend: bing(默认) | baidu | api | stub
config web.api: {format: tavily|generic, api_key, base_url, query_param, ...}
"""
from __future__ import annotations
import html as _html
import json
import re
import urllib.parse
import urllib.request

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


class StubWebSearcher(WebSearcher):
    def search(self, query: str, n: int = 10) -> list[dict]:
        return []


def get_searcher() -> WebSearcher:
    backend = config.get("web.backend", "bing")
    if backend == "baidu":
        return BaiduWebSearcher()
    if backend == "api":
        return ApiWebSearcher()
    if backend == "stub":
        return StubWebSearcher()
    return BingWebSearcher()
