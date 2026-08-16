"""SQLite 存储：条目 / 草稿 / 发布记录 / 令牌"""
from __future__ import annotations

import json
import sqlite3
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

SCHEMA = """
CREATE TABLE IF NOT EXISTS items (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  source TEXT NOT NULL,
  source_id TEXT NOT NULL,
  url TEXT UNIQUE NOT NULL,
  author TEXT DEFAULT '',
  title TEXT DEFAULT '',
  text TEXT DEFAULT '',
  published_at TEXT DEFAULT '',
  media TEXT DEFAULT '[]',
  fetched_at TEXT DEFAULT ''
);
CREATE INDEX IF NOT EXISTS idx_items_source ON items(source);

CREATE TABLE IF NOT EXISTS posts (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  item_id INTEGER NOT NULL,
  title TEXT DEFAULT '',
  body TEXT DEFAULT '',
  hashtags TEXT DEFAULT '[]',
  images TEXT DEFAULT '[]',
  status TEXT DEFAULT 'draft',  -- draft/ready/published/skipped/failed
  douyin_item_id TEXT DEFAULT '',
  error TEXT DEFAULT '',
  created_at TEXT DEFAULT '',
  published_at TEXT DEFAULT ''
);
CREATE INDEX IF NOT EXISTS idx_posts_status ON posts(status);

CREATE TABLE IF NOT EXISTS kv (
  key TEXT PRIMARY KEY,
  value TEXT DEFAULT ''
);
"""


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


class DB:
    def __init__(self, db_path: str | Path):
        path = Path(db_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(str(path), check_same_thread=False)
        self.conn.row_factory = sqlite3.Row
        self._lock = threading.Lock()
        with self._lock:
            self.conn.executescript(SCHEMA)
            self.conn.commit()

    # ---------- items ----------
    def insert_item(self, item) -> int | None:
        """插入条目，URL 已存在时返回 None"""
        with self._lock:
            cur = self.conn.execute(
                "INSERT OR IGNORE INTO items(source, source_id, url, author, title, text, published_at, media, fetched_at)"
                " VALUES(?,?,?,?,?,?,?,?,?)",
                (item.source, item.source_id, item.url, item.author, item.title, item.text,
                 item.published_at, json.dumps(item.media_urls, ensure_ascii=False), _now()),
            )
            self.conn.commit()
            if cur.rowcount == 0:
                return None
            return cur.lastrowid

    def get_item(self, item_id: int) -> dict | None:
        with self._lock:
            row = self.conn.execute("SELECT * FROM items WHERE id=?", (item_id,)).fetchone()
        return dict(row) if row else None

    def get_new_items(self, limit: int = 50, sources: list[str] | None = None) -> list[dict]:
        """取尚未生成草稿的条目（按抓取时间倒序）"""
        sql = "SELECT i.* FROM items i LEFT JOIN posts p ON p.item_id = i.id WHERE p.id IS NULL"
        args: list[Any] = []
        if sources:
            sql += " AND i.source IN (" + ",".join("?" * len(sources)) + ")"
            args += sources
        sql += " ORDER BY i.fetched_at DESC LIMIT ?"
        args.append(limit)
        with self._lock:
            rows = self.conn.execute(sql, args).fetchall()
        return [dict(r) for r in rows]

    # ---------- posts ----------
    def add_post(self, item_id: int, title: str = "", body: str = "", hashtags: list[str] | None = None,
                 images: list[str] | None = None, status: str = "draft") -> int:
        with self._lock:
            cur = self.conn.execute(
                "INSERT INTO posts(item_id, title, body, hashtags, images, status, created_at)"
                " VALUES(?,?,?,?,?,?,?)",
                (item_id, title, body, json.dumps(hashtags or [], ensure_ascii=False),
                 json.dumps(images or [], ensure_ascii=False), status, _now()),
            )
            self.conn.commit()
            return cur.lastrowid

    def update_post(self, post_id: int, **fields: Any) -> None:
        if not fields:
            return
        keys = list(fields)
        for k in ("hashtags", "images"):
            if k in fields and isinstance(fields[k], list):
                fields[k] = json.dumps(fields[k], ensure_ascii=False)
        sql = "UPDATE posts SET " + ",".join(f"{k}=?" for k in keys) + " WHERE id=?"
        with self._lock:
            self.conn.execute(sql, [fields[k] for k in keys] + [post_id])
            self.conn.commit()

    def get_posts(self, status: str | None = None, limit: int = 50) -> list[dict]:
        sql = "SELECT * FROM posts"
        args: list[Any] = []
        if status:
            sql += " WHERE status=?"
            args.append(status)
        sql += " ORDER BY id DESC LIMIT ?"
        args.append(limit)
        with self._lock:
            rows = self.conn.execute(sql, args).fetchall()
        return [dict(r) for r in rows]

    def get_recent_published(self, n: int = 30) -> list[dict]:
        with self._lock:
            rows = self.conn.execute(
                "SELECT * FROM posts WHERE status IN ('published','ready') ORDER BY id DESC LIMIT ?", (n,),
            ).fetchall()
        return [dict(r) for r in rows]

    # ---------- kv / tokens ----------
    def set_kv(self, key: str, value: str) -> None:
        with self._lock:
            self.conn.execute("INSERT OR REPLACE INTO kv(key, value) VALUES(?,?)", (key, value))
            self.conn.commit()

    def get_kv(self, key: str, default: str = "") -> str:
        with self._lock:
            row = self.conn.execute("SELECT value FROM kv WHERE key=?", (key,)).fetchone()
        return row["value"] if row else default

    def set_token(self, name: str, value: str) -> None:
        self.set_kv(f"token.{name}", value)

    def get_token(self, name: str) -> str:
        return self.get_kv(f"token.{name}")

    def close(self) -> None:
        self.conn.close()
