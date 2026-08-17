"""流水线离线测试（不联网、不发布）"""
from __future__ import annotations

import json
import tempfile
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path

from ai_news.config import DEFAULTS
from ai_news.db import DB
from ai_news.models import RawItem
from ai_news.pipeline import Pipeline


def _setup() -> tuple[dict, DB, Pipeline]:
    d = tempfile.mkdtemp(prefix="ai_news_pipe_")
    cfg = deepcopy(DEFAULTS)
    cfg["data_dir"] = d
    cfg["douyin"]["web"]["cookies_path"] = "/nonexistent.json"  # 避免本机 keepalive cookies 干扰测试
    db = DB(Path(d) / "app.db")
    pipe = Pipeline(cfg, db)
    return cfg, db, pipe


def test_pipeline_ready_and_cover():
    cfg, db, pipe = _setup()
    it = RawItem(source="s", source_type="tme", source_id="1", url="https://t.me/s/1",
                 text="OpenAI 发布 GPT-5 新模型，推理能力大幅提升，支持多模态输入",
                 published_at=datetime.now(timezone.utc).isoformat(timespec="seconds"))
    item_id = db.insert_item(it)
    assert item_id is not None
    res = pipe.process_item(item_id, dry_run=True, skip_llm=True)
    assert res["status"] == "ready", res
    post = db.get_posts("ready")[0]
    assert post["title"]
    images = json.loads(post["images"])
    assert len(images) >= 1 and Path(images[0]).exists()
    db.close()


def test_pipeline_skip_irrelevant():
    cfg, db, pipe = _setup()
    it = RawItem(source="s", source_type="tme", source_id="2", url="https://t.me/s/2",
                 text="今天天气很好，适合出去散步")
    item_id = db.insert_item(it)
    res = pipe.process_item(item_id, dry_run=True, skip_llm=True)
    assert res["status"] == "skipped", res
    assert "无关" in res["reason"] or "边缘" in res["reason"]
    db.close()


def test_pipeline_skip_sensitive():
    cfg, db, pipe = _setup()
    it = RawItem(source="s", source_type="tme", source_id="3", url="https://t.me/s/3",
                 text="OpenAI 新模型发布，加我微信领取免费体验名额")
    item_id = db.insert_item(it)
    res = pipe.process_item(item_id, dry_run=True, skip_llm=True)
    assert res["status"] == "skipped", res
    assert "敏感" in res["reason"] or "命中" in res["reason"], res
    db.close()


def test_pipeline_dedup_against_published():
    cfg, db, pipe = _setup()
    txt = "Anthropic 发布 Claude 新版本，代码能力大幅提升，开发者反馈积极"
    it1 = RawItem(source="s", source_type="tme", source_id="4", url="https://t.me/s/4", text=txt)
    id1 = db.insert_item(it1)
    r1 = pipe.process_item(id1, dry_run=True, skip_llm=True)
    assert r1["status"] == "ready"
    # 同一条新闻换个说法再来
    it2 = RawItem(source="s", source_type="tme", source_id="5", url="https://t.me/s/5",
                  text=txt + " 这是补充说明")
    id2 = db.insert_item(it2)
    r2 = pipe.process_item(id2, dry_run=True, skip_llm=True)
    assert r2["status"] == "skipped", r2
    assert "重复" in r2["reason"]
    db.close()


def test_compose_text_with_footer():
    cfg, db, pipe = _setup()
    t = pipe._compose_text("标题示例二十个字内", "正文内容比较详细的一段话。", ["AI", "人工智能"])
    assert "AI 转录" in t, t
    assert "#AI" in t and "#人工智能" in t
    assert t.rstrip().endswith("#人工智能") and t.endswith(" "), repr(t[-20:])
    assert t.startswith("标题示例") and "正文内容" in t
    db.close()
