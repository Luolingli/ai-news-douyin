"""配置加载：config.yaml + .env + 环境变量覆盖"""
from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import yaml

PROJECT_ROOT = Path(__file__).resolve().parent.parent

DEFAULTS: dict[str, Any] = {
    "data_dir": "data",
    "log_level": "INFO",
    "timezone": "Asia/Shanghai",
    "sources": [],
    "detection": {
        "relevance": {"threshold": 0.4, "extra_keywords": []},
        "sensitive": {"hard_block": True, "llm_verify": True},
        "dedup": {"text_similarity": 0.82, "recent_posts": 30},
    },
    "llm": {"model": "deepseek-chat", "temperature": 0.4, "max_title_len": 30, "max_body_len": 350, "max_hashtags": 5},
    "media": {
        "cover": {"enabled": True, "gradient": ["#0f2027", "#203a43", "#2c5364"], "font_size": 72},
        "download_images": True,
        "max_images": 9,
    },
    "douyin": {"mode": "auto", "api_style": "auto", "scope": "user_info,video.create", "text_prefix": "", "dry_run": False,
               "web": {"cookies_path": "", "headless": False, "timeout": 90000}},
}


def _load_dotenv(path: Path) -> None:
    """极简 .env 解析：KEY=VALUE，已有环境变量优先（不覆盖）"""
    if not path.exists():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, val = line.partition("=")
        key = key.strip()
        val = val.strip().strip('"').strip("'")
        if key and key not in os.environ:
            os.environ[key] = val


def _deep_merge(base: dict, override: dict) -> dict:
    out = dict(base)
    for k, v in (override or {}).items():
        if isinstance(v, dict) and isinstance(out.get(k), dict):
            out[k] = _deep_merge(out[k], v)
        else:
            out[k] = v
    return out


def _apply_env_overrides(cfg: dict) -> dict:
    """环境变量覆盖（供 GitHub Actions 等云端部署用）"""
    import os

    if os.environ.get("DOUYIN_MODE"):
        cfg.setdefault("douyin", {})["mode"] = os.environ["DOUYIN_MODE"]
    if os.environ.get("DOUYIN_WEB_HEADLESS"):
        cfg.setdefault("douyin", {}).setdefault("web", {})["headless"] = (
            os.environ["DOUYIN_WEB_HEADLESS"].lower() in ("1", "true", "yes")
        )
    if os.environ.get("DOUYIN_WEB_COOKIES"):
        cfg.setdefault("douyin", {}).setdefault("web", {})["cookies_path"] = os.environ["DOUYIN_WEB_COOKIES"]
    return cfg


def load_config(config_path: str | None = None) -> dict:
    _load_dotenv(PROJECT_ROOT / ".env")
    path = Path(config_path) if config_path else Path(os.environ.get("AI_NEWS_CONFIG", PROJECT_ROOT / "config.yaml"))
    if not path.exists():
        raise FileNotFoundError(f"配置文件不存在: {path}（复制 config.yaml.example 为 config.yaml 并修改）")
    with open(path, encoding="utf-8") as f:
        user_cfg = yaml.safe_load(f) or {}
    return _apply_env_overrides(_deep_merge(DEFAULTS, user_cfg))


def get(cfg: dict, dotted: str, default: Any = None) -> Any:
    cur: Any = cfg
    for part in dotted.split("."):
        if not isinstance(cur, dict) or part not in cur:
            return default
        cur = cur[part]
    return cur


def env(name: str, default: str = "") -> str:
    return os.environ.get(name, default)
