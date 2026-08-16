"""Telegram 频道公开预览页爬虫：https://t.me/s/<channel>（免登录、稳定）"""
from __future__ import annotations

import re

from ..models import RawItem
from .base import Source, SourceError, http_get_text, strip_html

CHUNK_RE = re.compile(
    r'<div class="tgme_widget_message_wrap[^"]*"[^>]*>.*?(?=<div class="tgme_widget_message_wrap|$)', re.S
)
POST_RE = re.compile(r'data-post="([^"]+)"')
DATE_URL_RE = re.compile(r'<a class="tgme_widget_message_date" href="([^"]+)"')
TIME_RE = re.compile(r'<time datetime="([^"]+)"')
TEXT_RE = re.compile(r'<div class="tgme_widget_message_text[^"]*"[^>]*>(.*?)</div>', re.S)
IMG_RE = re.compile(r'''background-image:url\('?([^')]+)'?\)''')
IMG_SRC_RE = re.compile(r'<img[^>]+src="([^"]+)"[^>]*>')
AUTHOR_RE = re.compile(r'<a class="tgme_widget_message_owner_name"[^>]*>([^<]*)</a>')
AUTHOR2_RE = re.compile(r'class="tgme_widget_message_author[^"]*"[^>]*>([^<]*)</a>')


class TmeSource(Source):
    type = "tme"

    def __init__(self, cfg: dict):
        super().__init__(cfg)
        self.channel: str = cfg["channel"].strip().lstrip("@")
        self.base = f"https://t.me/s/{self.channel}"

    def fetch(self):
        try:
            html = http_get_text(self.base)
        except Exception as e:
            raise SourceError(f"t.me 抓取失败: {e}") from e

        items = []
        for chunk in CHUNK_RE.findall(html):
            m = POST_RE.search(chunk)
            if not m:
                continue
            post = m.group(1)  # channel/123
            msg_id = post.split("/")[-1]
            m = DATE_URL_RE.search(chunk)
            url = m.group(1) if m else f"https://t.me/{post}"
            m = TIME_RE.search(chunk)
            published = m.group(1) if m else ""
            m = TEXT_RE.search(chunk)
            text = strip_html(m.group(1)) if m else ""
            if not text:
                continue
            media = []
            for u in IMG_RE.findall(chunk) + IMG_SRC_RE.findall(chunk):
                u = u.strip().strip("'").strip('"')
                if u.startswith("//"):
                    u = "https:" + u
                if any(k in u for k in ("telegram", "telesco", "cdn")) and u not in media:
                    media.append(u)
            m = AUTHOR_RE.search(chunk)
            author = m.group(1).strip() if m else self.channel
            if not author or author.startswith("http"):
                m2 = AUTHOR2_RE.search(chunk)
                author = m2.group(1).strip() if m2 else self.channel
            items.append(RawItem(
                source=self.name,
                source_type=self.type,
                source_id=msg_id,
                url=url,
                author=author,
                text=text,
                published_at=published,
                media_urls=media,
            ))
        items.sort(key=lambda x: int(x.source_id) if x.source_id.isdigit() else 0, reverse=True)
        return items[: self.max_items]
