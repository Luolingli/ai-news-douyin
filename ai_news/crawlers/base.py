"""爬虫基类与公共工具"""
from __future__ import annotations

import html as html_mod
import re
from typing import Any

import requests

UA = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
)

TAG_RE = re.compile(r"<[^>]+>");
BR_RE = re.compile(r"<br\s*/?>", re.I);
WS_RE = re.compile(r"[ \t\u00a0]+")
NL = "\n"


class SourceError(Exception):
    """源抓取失败"""


def strip_html(text: str) -> str:
    text = BR_RE.sub("\n", text or "")
    text = TAG_RE.sub("", text)
    text = html_mod.unescape(text)
    text = WS_RE.sub(" ", text)
    return text.strip()


def http_get_text(url: str, timeout: int = 25, **kw: Any) -> str:
    headers = kw.pop("headers", {})
    headers.setdefault("User-Agent", UA)
    resp = requests.get(url, headers=headers, timeout=timeout, **kw)
    resp.raise_for_status()
    return resp.text


def http_get_bytes(url: str, timeout: int = 30, **kw: Any) -> bytes:
    headers = kw.pop("headers", {})
    headers.setdefault("User-Agent", UA)
    resp = requests.get(url, headers=headers, timeout=timeout, **kw)
    resp.raise_for_status()
    return resp.content


def extract_article_text(html_text: str, max_chars: int = 4000) -> str:
    """从文章 HTML 中提取正文（纯函数，便于测试）：取 h1-h3 / p 文本"""
    import html as html_mod

    s = html_text or ''
    s = re.sub(r"(?is)<(script|style|nav|footer|header|aside)[^>]*>.*?</(script|style|nav|footer|header|aside)>", " ", s)
    parts = []
    for m in re.finditer(r"(?is)<(h1|h2|h3|p)[^>]*>(.*?)</(h1|h2|h3|p)>", s):
        t = re.sub(r"<[^>]+>", "", m.group(2))
        t = html_mod.unescape(t)
        t = WS_RE.sub(" ", t).strip()
        if t and len(t) > 15:
            parts.append(t)
    text = NL.join(parts)
    return text[:max_chars]


def fetch_article_text(url: str, timeout: int = 20, max_chars: int = 4000) -> str:
    """尽力抓取文章正文（失败返回空串，不影响流程）"""
    try:
        html_text = http_get_text(url, timeout=timeout)
        return extract_article_text(html_text, max_chars)
    except Exception:
        return ''


class Source:
    """内容源基类：fetch() 返回 RawItem 列表"""

    type = "base"

    def __init__(self, cfg: dict):
        self.cfg = cfg
        self.name: str = cfg.get("name", cfg.get("type", self.type))
        self.max_items: int = int(cfg.get("max_items", 20))

    def fetch(self):  # -> list[RawItem]
        raise NotImplementedError

    def __repr__(self) -> str:
        return f"<Source {self.name} ({self.type})>"


def build_sources(cfg_sources: list[dict]) -> list[Source]:
    from . import googlenews, rss, rsshub_twitter, tme, twitter_playwright

    registry = {
        "tme": tme.TmeSource,
        "googlenews": googlenews.GoogleNewsSource,
        "rss": rss.RssSource,
        "rsshub_twitter": rsshub_twitter.RsshubTwitterSource,
        "twitter_x": twitter_playwright.TwitterXSource,
    }
    out = []
    for s in cfg_sources or []:
        if not s.get("enabled", True):
            continue
        cls = registry.get(s.get("type"))
        if cls is None:
            continue
        out.append(cls(s))
    return out
