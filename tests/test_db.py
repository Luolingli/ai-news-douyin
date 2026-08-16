"""数据库测试"""
from __future__ import annotations

import json
import tempfile
from pathlib import Path

from ai_news.db import DB
from ai_news.models import RawItem


def _tmp_db():
    d = tempfile.mkdtemp(prefix="ai_news_test_")
    return DB(Path(d) / "t.db")


def test_insert_and_dedup():
    db = _tmp_db()
    it = RawItem(source="s1", source_type="tme", source_id="1", url="https://t.me/x/1",
                 text="OpenAI 发布新模型", published_at="2025-01-01T00:00:00+00:00", media_urls=["http://a/1.jpg"])
    id1 = db.insert_item(it)
    id2 = db.insert_item(it)  # 重复 URL
    assert id1 is not None and id2 is None
    got = db.get_item(id1)
    assert got["text"] == "OpenAI 发布新模型"
    assert json.loads(got["media"]) == ["http://a/1.jpg"]
    db.close()


def test_posts_and_kv():
    db = _tmp_db()
    db.set_kv("k", "v")
    assert db.get_kv("k") == "v"
    db.set_token("access_token", "abc")
    assert db.get_token("access_token") == "abc"
    pid = db.add_post(1, title="t", body="b", hashtags=["AI"], images=["/x.png"], status="ready")
    db.update_post(pid, status="published", douyin_item_id="123456")
    posts = db.get_posts("published")
    assert posts and posts[0]["douyin_item_id"] == "123456"
    assert db.get_recent_published(10)
    db.close()
