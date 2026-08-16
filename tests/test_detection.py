"""内容检测测试"""
from __future__ import annotations

from ai_news.detection import check_sensitive, decide, is_duplicate, normalize, similarity


def test_relevance_strong():
    passed, score, reason = decide("OpenAI releases GPT-5 with new reasoning capabilities")
    assert passed, reason
    assert score >= 2.0


def test_relevance_weak():
    passed, score, reason = decide("今天天气不错，适合出去走走")
    assert not passed
    assert score == 0.0


def test_relevance_edge():
    # 只有弱词，落在边缘区需要 LLM
    passed, score, reason = decide("A new startup raised funding for its model", threshold=0.4)
    assert reason.startswith("边缘") or passed


def test_sensitive_block():
    bad, hits = check_sensitive("加我微信 xxx888 领取红包")
    assert bad, hits
    bad2, hits2 = check_sensitive("OpenAI 发布新模型，性能提升 50%")
    assert not bad2, hits2


def test_dedup():
    a = "OpenAI 发布 GPT-5，推理能力大幅提升 https://t.co/abc"
    b = "OpenAI 发布 GPT-5，推理能力大幅提升"
    c = "今天天气不错"
    assert similarity(a, b) > 0.9
    dup, sim, _ = is_duplicate(a, [b], threshold=0.82)
    assert dup, sim
    dup2, _, _ = is_duplicate(a, [c], threshold=0.82)
    assert not dup2
    assert normalize("  Hello  #AI  https://t.co/x ") == "hello"
