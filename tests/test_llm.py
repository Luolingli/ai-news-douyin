"""LLM 工具函数测试（离线）"""
from __future__ import annotations

from ai_news.llm import extract_json, fallback_summarize, sanitize_hashtags


def test_extract_json():
    ok = extract_json('{"a": 1, "b": ["x", "y"]}')
    assert ok == {"a": 1, "b": ["x", "y"]}
    fenced = extract_json('```json\n{"a": 2}\n```')
    assert fenced == {"a": 2}
    noisy = extract_json('好的，结果如下：{"a": 3} 完毕')
    assert noisy == {"a": 3}
    assert extract_json("没有 JSON") is None


def test_sanitize_hashtags():
    out = sanitize_hashtags(["#OpenAI", " 人工智能 ", "bad tag!@#", "OpenAI", "AI", "x" * 40])
    assert out == ["OpenAI", "人工智能", "AI"], out
    assert len(out) <= 5


def test_fallback_summarize():
    item = {"title": "OpenAI 发布 GPT-5", "text": "这是一段很长的正文 " + "内容" * 200, "source": "t"}
    r = fallback_summarize(item, max_title_len=30, max_body_len=100)
    assert r["relevant"] is True
    assert len(r["title"]) <= 30
    assert len(r["body"]) <= 100
    assert r["hashtags"]
