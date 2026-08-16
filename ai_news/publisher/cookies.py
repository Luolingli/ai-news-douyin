"""抖音网页版 cookies 读写（Playwright 格式）"""
from __future__ import annotations

import json
import logging
import os
import time
from pathlib import Path

log = logging.getLogger("ai_news.cookies")


def resolve_cookies_path(configured: str = "", project_data_dir: str = "data") -> str:
    """确定 cookies 文件路径（存在与否不影响返回）：配置 > 环境变量 > 项目 data/ 下默认"""
    if configured:
        return str(Path(configured).expanduser())
    p = os.environ.get("DOUYIN_WEB_COOKIES", "")
    if p:
        return str(Path(p).expanduser())
    return str(Path(project_data_dir) / "web_cookies.json")


def load_cookies(path: str | None) -> list[dict]:
    """读取 cookies，返回 Playwright add_cookies 兼容的列表；文件不存在或格式错返回 []"""
    if not path or not Path(path).exists():
        return []
    try:
        data = json.loads(Path(path).read_text(encoding="utf-8"))
    except Exception as e:
        log.warning("cookies 解析失败 %s: %s", path, e)
        return []
    if not isinstance(data, list):
        return []
    now = time.time()
    valid = []
    for c in data:
        if not isinstance(c, dict) or not c.get("name") or not c.get("domain"):
            continue
        exp = c.get("expires", -1)
        if isinstance(exp, (int, float)) and exp > 0 and exp < now:
            continue
        valid.append(c)
    return valid


def save_cookies(cookies: list[dict], path: str) -> None:
    """写回 cookies（与 keepalive 设施同格式，可直接复用）"""
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(cookies, ensure_ascii=False), encoding="utf-8")
    log.info("cookies 已回写 %s（%d 条）", path, len(cookies))
