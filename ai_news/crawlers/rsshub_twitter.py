"""RSSHub Twitter 路由爬虫：<base>/twitter/user/<account>（需自建 RSSHub 实例）"""
from __future__ import annotations

import feedparser

from ..models import RawItem
from .base import Source, SourceError, http_get_text, strip_html


class RsshubTwitterSource(Source):
    type = "rsshub_twitter"

    def __init__(self, cfg: dict):
        super().__init__(cfg)
        self.base_url: str = cfg["base_url"].rstrip("/")
        self.accounts: list[str] = cfg.get("accounts", [])

    def fetch(self):
        items = []
        for acc in self.accounts:
            url = f"{self.base_url}/twitter/user/{acc}"
            try:
                xml = http_get_text(url)
            except Exception as e:
                raise SourceError(f"RSSHub 抓取 {acc} 失败: {e}") from e
            feed = feedparser.parse(xml)
            if feed.bozo and not feed.entries:
                continue
            for entry in feed.entries[: self.max_items]:
                media = []
                for enc in entry.get("enclosures", []) or []:
                    u = enc.get("href") or enc.get("url")
                    if u and u not in media:
                        media.append(u)
                items.append(RawItem(
                    source=f"{self.name}/{acc}",
                    source_type=self.type,
                    source_id=entry.get("id", "") or entry.get("link", ""),
                    url=entry.get("link", ""),
                    author=acc,
                    title=entry.get("title", ""),
                    text=strip_html(entry.get("summary", "") or entry.get("description", "")),
                    published_at=entry.get("published", ""),
                    media_urls=media,
                ))
        return items
