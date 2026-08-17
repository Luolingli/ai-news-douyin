"""通用 RSS 爬虫（任意 RSS/Atom，含 RSSHub 输出）"""
from __future__ import annotations

import feedparser

from ..models import RawItem
from .base import Source, SourceError, http_get_text, strip_html


class RssSource(Source):
    type = "rss"

    def __init__(self, cfg: dict):
        super().__init__(cfg)
        self.url: str = cfg["url"]

    def fetch(self):
        try:
            xml = http_get_text(self.url)
        except Exception as e:
            raise SourceError(f"RSS 抓取失败: {e}") from e
        feed = feedparser.parse(xml)
        feed_title = (feed.feed.get("title") or "").strip()
        if " | " in feed_title:
            feed_title = feed_title.split(" | ")[-1].strip()
        items = []
        for entry in feed.entries[: self.max_items]:
            media = []
            for enc in entry.get("enclosures", []) or []:
                url = enc.get("href") or enc.get("url")
                if url:
                    media.append(url)
            if not media:
                for lnk in entry.get("links", []) or []:
                    if str(lnk.get("type", "")).startswith("image"):
                        media.append(lnk.get("href", ""))
            items.append(RawItem(
                source=self.name,
                source_type=self.type,
                source_id=entry.get("id", "") or entry.get("link", ""),
                url=entry.get("link", ""),
                author=(feed_title or entry.get("author") or ""),
                title=entry.get("title", ""),
                text=strip_html(entry.get("summary", "") or entry.get("description", "")),
                published_at=entry.get("published", ""),
                media_urls=media,
            ))
        return items
