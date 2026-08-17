"""LLM 健康度排序测试"""
from __future__ import annotations

import tempfile
from pathlib import Path

from ai_news.llm.client import LLMClient


def test_health_bump_and_order():
    d = tempfile.mkdtemp(prefix="health_")
    c = LLMClient(api_key="fake", base_url="https://x.example/v1",
                  model="m1", model_fallbacks=["m2", "m3"])
    c._health_file = Path(d) / "h.json"
    c._bump("m1", -3.0)
    c._bump("m2", 2.0)
    ordered = sorted(c.models, key=lambda m: -c._health.get(m, 0.0))
    assert ordered[0] == "m2", ordered
    assert Path(d, "h.json").exists(), "健康度应持久化"
    c2 = LLMClient(api_key="fake", base_url="https://x.example/v1", model="m1")
    c2._health_file = Path(d) / "h.json"
    c2._load_health()
    assert c2._health.get("m2") == 2.0


def test_health_clamp():
    c = LLMClient(api_key="fake", base_url="https://x.example/v1", model="m")
    c._health_file = Path(tempfile.mkdtemp()) / "h.json"
    for _ in range(10):
        c._bump("m", -3.0)
    assert c._health["m"] >= -10.0
