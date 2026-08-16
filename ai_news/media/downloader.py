"""图片下载（尽力而为，失败不影响发布）"""
from __future__ import annotations

import logging
import re
from pathlib import Path

import requests

from ..crawlers.base import UA

log = logging.getLogger("ai_news.media")

MAX_BYTES = 15 * 1024 * 1024  # 15MB
EXT_MAP = {"image/jpeg": ".jpg", "image/png": ".png", "image/webp": ".webp", "image/gif": ".gif"}
SAFE_NAME = re.compile(r"[^a-zA-Z0-9_.-]+")


def download_image(url: str, dest_dir: str | Path, name: str = "") -> str | None:
    """下载图片到 dest_dir，返回本地路径或 None"""
    try:
        resp = requests.get(url, headers={"User-Agent": UA}, timeout=25, stream=True)
        if resp.status_code != 200:
            log.debug("图片下载 HTTP %s: %s", resp.status_code, url[:80])
            return None
        ctype = (resp.headers.get("Content-Type") or "").split(";")[0].strip().lower()
        if not ctype.startswith("image/"):
            log.debug("非图片内容类型 %s: %s", ctype, url[:80])
            return None
        content = resp.content
        if len(content) > MAX_BYTES:
            log.debug("图片过大 %dKB: %s", len(content) // 1024, url[:80])
            return None
        # 过滤过小图片（表情/图标），至少 200x200
        try:
            from PIL import Image

            import io

            with Image.open(io.BytesIO(content)) as im:
                if im.width < 200 or im.height < 200:
                    log.debug("图片过小 %dx%d: %s", im.width, im.height, url[:80])
                    return None
        except Exception:
            pass
        ext = EXT_MAP.get(ctype, ".jpg")
        fname = (name or SAFE_NAME.sub("_", url.split("?")[0].split("/")[-1][:40]) or "img") + ext
        if not fname.lower().endswith(ext):
            fname += ext
        dest = Path(dest_dir) / fname
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(content)
        return str(dest)
    except Exception as e:
        log.debug("图片下载失败 %s: %s", url[:80], e)
        return None
