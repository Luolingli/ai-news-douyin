"""Google News 关键词 RSS 爬虫（免登录、稳定）"""
from __future__ import annotations

import feedparser

from ..models import RawItem
from .base import Source, SourceError, http_get_text, strip_html


class GoogleNewsSource(Source):
    type = "googlenews"

    def __init__(self, cfg: dict):
        super().__init__(cfg)
        self.query: str = cfg["query"]
        lang = cfg.get("lang", "en-US")
        gl = cfg.get("gl", lang.split("-")[0] if "-" in lang else lang)
        ceid = cfg.get("ceid", f"{lang}:{gl}")
        import urllib.parse

        self.url = "https://news.google.com/rss/search?" + urllib.parse.urlencode(
            {"q": self.query, "hl": lang, "gl": gl, "ceid": ceid},
        )

    def fetch(self):
        try:
            xml = http_get_text(self.url)
        except Exception as e:
            raise SourceError(f"Google News 抓取失败: {e}") from e
        feed = feedparser.parse(xml)
        items = []
        for entry in feed.entries[: self.max_items]:
            desc = strip_html(entry.get("summary", "")) or entry.get("title", "")
            src = entry.get("source") or {}
            author = src.get("title", "") if isinstance(src, dict) else ""
            items.append(RawItem(
                source=self.name,
                source_type=self.type,
                source_id=entry.get("id", "") or entry.get("link", ""),
                url=entry.get("link", ""),
                author=author,
                title=entry.get("title", ""),
                text=desc,
                published_at=entry.get("published", ""),
            ))
        return items
