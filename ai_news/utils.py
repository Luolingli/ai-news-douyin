"""小工具：状态展示、草稿发布"""
from __future__ import annotations

import json
import logging

log = logging.getLogger("ai_news.utils")


def show_posts(posts: list[dict]) -> str:
    lines = [f"{'ID':>4} {'状态':<10} {'标题':<40} {'抖音ID':<14} 错误"]
    for p in posts:
        err = (p.get("error") or "")[:20]
        lines.append(f"{p['id']:>4} {p['status']:<10} {(p.get('title') or '')[:38]:<40} {(p.get('douyin_item_id') or ''):<14} {err}")
    return "\n".join(lines)


def publish_ready(pipeline, dry_run: bool = False, limit: int = 10) -> dict:
    """发布所有 ready 状态的草稿（用于 LLM 出稿后手动/定时补发）"""
    from datetime import datetime, timezone

    posts = pipeline.db.get_posts("ready", limit=limit)
    if not pipeline.publisher and not dry_run:
        log.warning("未配置抖音凭据，仅展示草稿")
    stats = {"published": 0, "failed": 0}
    for p in posts:
        images = json.loads(p.get("images") or "[]")
        hashtags = json.loads(p.get("hashtags") or "[]")
        src = ""
        it = pipeline.db.get_item(p.get("item_id") or 0)
        if it:
            src = it.get("author") or it.get("source") or ""
        text = pipeline._compose_text(p.get("title", ""), p.get("body", ""), hashtags, src)
        try:
            if dry_run or not pipeline.publisher:
                log.info("[dry-run] 草稿 %d 将发布: %s", p["id"], p.get("title"))
                stats["published"] += 1
                continue
            res = pipeline.publisher.publish(images, text, dry_run=False)
            if isinstance(res, dict):
                ok = bool(res.get("ok"))
                item_id = str(res.get("item_id", ""))
                note = str(res.get("message", ""))
            else:
                ok = True
                item_id = str(res)
                note = ""
            if not ok:
                raise RuntimeError(note or "发布器返回失败")
            pipeline.db.update_post(p["id"], status="published", douyin_item_id=item_id,
                                    published_at=datetime.now(timezone.utc).isoformat(timespec="seconds"),
                                    error=note[:500])
            log.info("[已发布] 草稿 %d -> %s %s", p["id"], item_id, note)
            stats["published"] += 1
        except Exception as e:
            pipeline.db.update_post(p["id"], status="failed", error=str(e)[:500])
            log.error("[发布失败] 草稿 %d: %s", p["id"], e)
            stats["failed"] += 1
    return stats
