"""网页发布器模块测试（不启动浏览器）"""
from __future__ import annotations

import tempfile
from copy import deepcopy
from pathlib import Path

from ai_news.config import DEFAULTS
from ai_news.db import DB
from ai_news.pipeline import Pipeline
from ai_news.publisher.douyin_web import DouyinWebPublisher, find_browser_executable


def test_find_browser():
    exe = find_browser_executable()
    if exe:
        assert Path(exe).exists(), exe


def test_publisher_construct():
    pub = DouyinWebPublisher({"headless": True, "cookies_path": "/tmp/nonexistent_ck.json", "data_dir": "data"})
    assert pub.headless is True
    assert pub.cookies_path == "/tmp/nonexistent_ck.json"


def test_pipeline_selects_web_publisher():
    d = tempfile.mkdtemp(prefix="sel_")
    cfg = deepcopy(DEFAULTS)
    cfg["data_dir"] = d
    cfg["douyin"]["mode"] = "web"
    cfg["douyin"]["web"]["cookies_path"] = "/nonexistent.json"
    db = DB(Path(d) / "app.db")
    pipe = Pipeline(cfg, db)
    assert isinstance(pipe.publisher, DouyinWebPublisher), type(pipe.publisher)
    db.close()


def test_pipeline_selects_none_without_creds():
    d = tempfile.mkdtemp(prefix="sel2_")
    cfg = deepcopy(DEFAULTS)
    cfg["data_dir"] = d
    cfg["douyin"]["mode"] = "api"  # 强制 API 但无凭据
    db = DB(Path(d) / "app.db")
    pipe = Pipeline(cfg, db)
    assert pipe.publisher is None
    db.close()


def test_pipeline_web_auto_needs_cookies():
    """auto 模式下没有 cookies 文件 → publisher 为 None（等用户先 web login）"""
    d = tempfile.mkdtemp(prefix="sel3_")
    cfg = deepcopy(DEFAULTS)
    cfg["data_dir"] = d
    cfg["douyin"]["mode"] = "auto"
    cfg["douyin"]["web"]["cookies_path"] = "/nonexistent.json"
    db = DB(Path(d) / "app.db")
    pipe = Pipeline(cfg, db)
    assert pipe.publisher is None
    db.close()
