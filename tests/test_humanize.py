"""拟人化改造测试"""
from __future__ import annotations

import time
from unittest.mock import patch

from ai_news.publisher.douyin_web import DouyinWebPublisher


def test_human_pause_range():
    pub = DouyinWebPublisher({"headless": True, "cookies_path": "/nonexistent.json"})
    captured: list[float] = []
    with patch("ai_news.publisher.douyin_web.time.sleep", side_effect=lambda s: captured.append(s)):
        pub._human_pause(2, 8, "test")
    assert len(captured) == 1
    assert 2.0 <= captured[0] <= 8.0, captured


def test_human_pause_min_max():
    pub = DouyinWebPublisher({"headless": True, "cookies_path": "/nonexistent.json"})
    captured: list[float] = []
    with patch("ai_news.publisher.douyin_web.time.sleep", side_effect=lambda s: captured.append(s)):
        pub._human_pause(5, 5, "fixed")
    assert captured[0] == 5.0
