"""cookies 模块测试"""
from __future__ import annotations

import json
import tempfile
import time
from pathlib import Path

from ai_news.publisher.cookies import load_cookies, resolve_cookies_path, save_cookies


def _write(tmp: Path, data) -> Path:
    p = tmp / "cookies.json"
    p.write_text(json.dumps(data), encoding="utf-8")
    return p


def test_load_valid_and_expired():
    d = tempfile.mkdtemp(prefix="ck_")
    now = time.time()
    p = _write(Path(d), [
        {"name": "ok", "value": "v1", "domain": ".douyin.com", "path": "/", "expires": now + 86400},
        {"name": "dead", "value": "v2", "domain": ".douyin.com", "path": "/", "expires": now - 10},
        {"name": "session", "value": "v3", "domain": "www.douyin.com", "path": "/", "expires": -1},
        {"name": "bad", "value": "v4"},  # 缺 domain
    ])
    cks = load_cookies(str(p))
    names = [c["name"] for c in cks]
    assert "ok" in names and "session" in names and "dead" not in names and "bad" not in names, names


def test_resolve_and_save_roundtrip():
    d = tempfile.mkdtemp(prefix="ck_")
    p = Path(d) / "out.json"
    save_cookies([{"name": "a", "value": "b", "domain": ".douyin.com", "path": "/"}], str(p))
    assert p.exists()
    assert load_cookies(str(p))[0]["name"] == "a"
    assert resolve_cookies_path(str(p)) == str(p)
    assert resolve_cookies_path("", "data").endswith("web_cookies.json")
