"""t.me 解析器测试"""
from __future__ import annotations

from pathlib import Path

from ai_news.crawlers.tme import TmeSource

FIXTURE = Path(__file__).parent / "fixtures" / "tme_sample.html"


def test_tme_parse():
    src = TmeSource({"name": "tg", "channel": "AI_News_Official", "max_items": 20})
    # 绕过网络：直接喂本地 HTML
    html = FIXTURE.read_text(encoding="utf-8")
    items = src._parse_html(html) if hasattr(src, "_parse_html") else None
    if items is None:
        # 把解析逻辑临时切到本地文件：monkeypatch 抓取函数
        import ai_news.crawlers.tme as tme_mod

        orig = tme_mod.http_get_text
        tme_mod.http_get_text = lambda url: html
        try:
            items = src.fetch()
        finally:
            tme_mod.http_get_text = orig
    assert len(items) == 10, f"期望 10 条，实际 {len(items)}"
    it = items[0]
    assert it.url.startswith("https://t.me/"), it.url
    assert it.text, "消息文本不能为空"
    assert it.source_id.isdigit()
    assert it.published_at, "时间不能为空"
    # 至少有一条消息带配图
    assert any(len(x.media_urls) > 0 for x in items), "应有消息带配图"
