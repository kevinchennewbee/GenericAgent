# -*- coding: utf-8 -*-
"""蓬莱插件：求证型多源搜索（情报矩阵 M5 — 多源不为省钱，为求真）。

无 key 基线（国内可用）：Bing + 搜狗 两个独立引擎并查。
可选增强：mykey.py 配 tavily_key / firecrawl_key 时自动并入为第三源。
做法：并查 → 按域名去重 → 标注每条来源 → 多源都出现的结果标 ★（高置信）。
交叉验证由 agent 完成（schema 描述里指示），工具只负责把多源证据清晰摆出来。

挂载：类注入 do_web_search + agent_before 注入 schema。GA 内核零改动。
GA 自带的 web_scan/web_execute_js（真浏览器）保留不动，本工具是其无浏览器补充。
"""
import os, re, json, html
from urllib.parse import urlparse, parse_qs, unquote

from plugins.hooks import register
from agent_loop import StepOutcome
from ga import GenericAgentHandler

_UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
       "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8"}

def _clean(t):
    return re.sub(r"\s+", " ", html.unescape(t or "")).strip()

def _domain(u):
    try: return urlparse(u).netloc.replace("www.", "")
    except Exception: return ""

def _bing(query, n=8):
    import requests
    from bs4 import BeautifulSoup
    r = requests.get("https://cn.bing.com/search", params={"q": query}, headers=_UA, timeout=10)
    soup = BeautifulSoup(r.text, "html.parser")
    out = []
    for li in soup.select("li.b_algo")[:n]:
        h = li.find("h2"); a = h.find("a") if h else None
        if not a or not a.get("href"): continue
        cap = li.select_one(".b_caption p, p")
        out.append({"title": _clean(a.get_text()), "url": a["href"],
                    "snippet": _clean(cap.get_text() if cap else ""), "source": "Bing"})
    return out

def _sogou(query, n=8):
    import requests
    from bs4 import BeautifulSoup
    r = requests.get("https://www.sogou.com/web", params={"query": query}, headers=_UA, timeout=10)
    soup = BeautifulSoup(r.text, "html.parser")
    out = []
    for d in soup.select("div.vrwrap")[:n]:
        a = d.select_one("h3 a, a.title-hover-show, a")
        if not a or not a.get("href"): continue
        url = a["href"]
        if url.startswith("/link?"):  # 搜狗跳转链接
            url = "https://www.sogou.com" + url
        sn = d.select_one(".star-wiki, .fz-mid, .text-layout, p")
        title = _clean(a.get_text())
        if not title: continue
        out.append({"title": title, "url": url, "snippet": _clean(sn.get_text() if sn else ""), "source": "搜狗"})
    return out

def _tavily(query, n=8):
    import requests
    key = _mykey_get("tavily_key")
    if not key: return []
    r = requests.post("https://api.tavily.com/search",
                      json={"api_key": key, "query": query, "max_results": n}, timeout=15)
    return [{"title": _clean(x.get("title")), "url": x.get("url"),
             "snippet": _clean(x.get("content")), "source": "Tavily"} for x in r.json().get("results", [])]

def _mykey_get(name):
    try:
        import mykey
        return getattr(mykey, name, "") or ""
    except Exception:
        return ""

def search(query, n=8):
    """并查多源 → 去重 → 标注收敛度。返回结构化 dict。"""
    sources, errors = [], []
    for fn in (_bing, _sogou, _tavily):
        try:
            res = fn(query, n)
            if res: sources.append(res)
        except Exception as e:
            errors.append(f"{fn.__name__}: {type(e).__name__}")
    if not sources:
        return {"error": "所有搜索源均不可用: " + "; ".join(errors)}
    # 按域名归并：同域名出现在多个源 → 收敛证据
    merged = {}
    for res in sources:
        for item in res:
            d = _domain(item["url"])
            key = d or item["url"]
            if key not in merged:
                merged[key] = {**item, "seen_in": {item["source"]}}
            else:
                merged[key]["seen_in"].add(item["source"])
                if len(item["snippet"]) > len(merged[key]["snippet"]):
                    merged[key]["snippet"] = item["snippet"]
    items = sorted(merged.values(), key=lambda x: (-len(x["seen_in"]), len(x["title"])))
    return {"query": query, "sources_used": len(sources), "errors": errors,
            "results": [{"title": x["title"], "url": x["url"], "snippet": x["snippet"][:300],
                         "from": "+".join(sorted(x["seen_in"])),
                         "convergent": len(x["seen_in"]) > 1} for x in items[:10]]}

def _format(r):
    if "error" in r: return r["error"]
    lines = [f"多源搜索「{r['query']}」（{r['sources_used']} 个源" +
             (f"，{','.join(r['errors'])}不可用" if r["errors"] else "") + "）："]
    for i, x in enumerate(r["results"], 1):
        mark = "★" if x["convergent"] else " "
        lines.append(f"{mark}{i}. [{x['from']}] {x['title']}\n   {x['url']}\n   {x['snippet']}")
    lines.append("\n[★=多源收敛，可信度较高]。求证型问题：对照不同来源，发现分歧要明示并说明依据，"
                 "勿只取单一来源下结论。需要正文细节时再用 web_fetch/浏览器打开具体链接。")
    return "\n".join(lines)

def do_web_search(self, args, response):
    """求证型多源搜索：Bing+搜狗(+Tavily) 并查、交叉验证。"""
    query = str(args.get("query", "")).strip()
    if not query:
        return StepOutcome("[Error] query 不能为空",
                           next_prompt=self._get_anchor_prompt(skip=args.get("_index", 0) > 0))
    yield f"\n[Action] 多源搜索: {query}\n"
    r = search(query, n=int(args.get("n", 8)))
    out = _format(r)
    yield out[:500] + ("...\n" if len(out) > 500 else "\n")
    return StepOutcome(out, next_prompt=self._get_anchor_prompt(skip=args.get("_index", 0) > 0))

GenericAgentHandler.do_web_search = do_web_search

_SCHEMA = {"type": "function", "function": {
    "name": "web_search",
    "description": "求证型多源搜索：同时查 Bing+搜狗（国内可用，无需配置）等多个独立搜索引擎，"
                   "按来源去重并标注收敛度（★=多源都出现=可信度高）。"
                   "适用于事实核查、要写入记忆/做决策的查证场景——比单一搜索源更能发现分歧、降低幻觉。"
                   "返回标题/链接/摘要列表；需要网页正文细节时再用浏览器或 web_fetch 打开具体链接。",
    "parameters": {"type": "object", "properties": {
        "query": {"type": "string", "description": "搜索查询词"},
        "n": {"type": "integer", "description": "每源结果数，默认 8"}},
        "required": ["query"]}}}

@register("agent_before")
def _inject_search_schema(ctx):
    ts = ctx.get("tools_schema")
    if isinstance(ts, list) and not any(
            t.get("function", {}).get("name") == "web_search" for t in ts if isinstance(t, dict)):
        ts.append(_SCHEMA)
