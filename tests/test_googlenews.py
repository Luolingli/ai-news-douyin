"""Google News 解析器测试"""
from __future__ import annotations

from pathlib import Path

from ai_news.crawlers.googlenews import GoogleNewsSource

FIXTURE = Path(__file__).parent / "fixtures" / "gn_sample.xml"


def test_googlenews_parse():
    import ai_news.crawlers.googlenews as gn_mod

    src = GoogleNewsSource({"name": "google", "query": "\"OpenAI\"", "max_items": 10})
    xml = FIXTURE.read_text(encoding="utf-8")
    orig = gn_mod.http_get_text
    gn_mod.http_get_text = lambda url: xml
    try:
        items = src.fetch()
    finally:
        gn_mod.http_get_text = orig
    assert len(items) > 0
    it = items[0]
    assert it.url.startswith("https://news.google.com/"), it.url
    assert it.title
    assert it.published_at
