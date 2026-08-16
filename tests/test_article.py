"""文章正文提取测试"""
from __future__ import annotations

from ai_news.crawlers.base import extract_article_text


def test_extract_article_text():
    html = (
        "<html><head><title>x</title></head><body>"
        "<nav>导航菜单内容</nav>"
        "<h1>OpenAI 发布全新推理模型引发行业关注</h1>"
        "<p>第一段：这是足够长的正文内容，包含具体信息。</p>"
        "<p>第二段：模型参数达到 1.8 万亿，性能提升 40%。</p>"
        "<script>var a = 1;</script>"
        "<style>.x{}</style>"
        "</body></html>"
    )
    t = extract_article_text(html)
    assert "OpenAI 发布全新推理模型引发行业关注" in t
    assert "第一段" in t and "第二段" in t
    assert "var a" not in t
    assert "导航菜单" not in t
