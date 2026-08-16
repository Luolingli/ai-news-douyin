"""抖音令牌存储：环境变量优先，其次 SQLite；可选 GitHub Actions 回写"""
from __future__ import annotations

import logging
import os
import shutil
import subprocess

log = logging.getLogger("ai_news.token")

TOKEN_KEYS = ("DOUYIN_ACCESS_TOKEN", "DOUYIN_REFRESH_TOKEN", "DOUYIN_OPEN_ID", "DOUYIN_OPEN_NAME")


class TokenStore:
    """读取优先级：环境变量 > 数据库。写入：数据库 + （可选）gh secret 回写"""

    def __init__(self, db):
        self.db = db

    def get(self, name: str) -> str:
        key = f"DOUYIN_{name.upper()}" if not name.startswith("DOUYIN_") else name
        return os.environ.get(key) or self.db.get_token(name.lower()) or ""

    def set(self, name: str, value: str) -> None:
        if not value:
            return
        key = f"DOUYIN_{name.upper()}" if not name.startswith("DOUYIN_") else name
        self.db.set_token(key.lower(), value)
        # 可选：GitHub Actions 部署时回写 secrets，保证云端长期运行
        repo = os.environ.get("GH_WRITEBACK_REPO")
        pat = os.environ.get("GH_WRITEBACK_TOKEN")
        if repo and pat and shutil.which("gh"):
            try:
                subprocess.run(
                    ["gh", "secret", "set", key, "--repo", repo, "--body", value],
                    capture_output=True, timeout=30, env={**os.environ, "GH_TOKEN": pat},
                    check=True,
                )
                log.info("已回写 GitHub secret %s", key)
            except Exception as e:
                log.warning("GitHub secret 回写失败: %s", e)

    def all(self) -> dict:
        return {k: self.get(k) for k in TOKEN_KEYS}
