"""主流水线：抓取 → 检测 → 去重 → 总结 → 出图 → 发布"""
from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from pathlib import Path

from . import config as cfg_mod
from .config import get
from .crawlers import build_sources
from .db import DB
from .detection import check_sensitive, decide, is_duplicate
from .llm import LLMClient, SYSTEM_PROMPT, build_user_prompt, fallback_summarize, sanitize_hashtags
from .media import download_image, generate_cover
from .publisher import DouyinOpenClient, TokenStore

log = logging.getLogger("ai_news.pipeline")


class Pipeline:
    def __init__(self, cfg: dict, db: DB):
        self.cfg = cfg
        self.db = db
        data_dir = Path(get(cfg, "data_dir", "data"))
        self.image_root = data_dir / "images"
        api_key = cfg_mod.env("DEEPSEEK_API_KEY")
        self.llm = LLMClient(
            api_key=api_key,
            base_url=cfg_mod.env("LLM_BASE_URL", "https://api.deepseek.com"),
            model=get(cfg, "llm.model", "deepseek-chat"),
            temperature=get(cfg, "llm.temperature", 0.4),
        )
        self.publisher = None
        douyin_cfg = get(cfg, "douyin", {})
        mode = (douyin_cfg.get("mode") or "auto").lower()
        has_api_creds = bool(cfg_mod.env("DOUYIN_CLIENT_KEY"))
        if mode in ("auto", "api") and has_api_creds:
            from .publisher import DouyinOpenClient, TokenStore

            self.publisher = DouyinOpenClient(douyin_cfg, TokenStore(db))
            log.info("发布器: 抖音开放平台 API")
        elif mode in ("auto", "web"):
            from .publisher.cookies import resolve_cookies_path
            from .publisher.douyin_web import DouyinWebPublisher

            web_cfg = dict(get(douyin_cfg, "web", {}))
            data_dir = str(Path(get(cfg, "data_dir", "data")))
            web_cfg["data_dir"] = data_dir
            web_cfg["screenshot_dir"] = str(Path(data_dir) / "logs" / "screenshots")
            cookies_exist = Path(resolve_cookies_path(web_cfg.get("cookies_path") or "", data_dir)).exists()
            if mode == "web" or cookies_exist:
                self.publisher = DouyinWebPublisher(web_cfg)
                log.info("发布器: 抖音网页版（Playwright）")
            else:
                log.info("未找到抖音 cookies，暂以 dry-run 模式生成草稿（可执行 python main.py douyin web login）")

    # ---------- 阶段 1: 抓取 ----------
    def crawl(self, sources_filter: list[str] | None = None) -> list[int]:
        new_ids: list[int] = []
        for src in build_sources(get(self.cfg, "sources", [])):
            if sources_filter and src.name not in sources_filter:
                continue
            try:
                items = src.fetch()
            except Exception as e:
                log.error("源 %s 抓取失败: %s", src.name, e)
                continue
            got = 0
            for it in items:
                if not it.text and not it.title:
                    continue
                row_id = self.db.insert_item(it)
                if row_id:
                    new_ids.append(row_id)
                    got += 1
            log.info("源 %s: 抓取 %d 条，新增 %d 条", src.name, len(items), got)
        return new_ids

    # ---------- 阶段 2~5: 检测 + 总结 + 出图 ----------
    def process_item(self, item_id: int, dry_run: bool = False, skip_llm: bool = False) -> dict | None:
        item = self.db.get_item(item_id)
        if not item:
            return None
        text = (item.get("text") or "").strip() or (item.get("title") or "").strip()
        det = get(self.cfg, "detection", {})
        rel_cfg = get(det, "relevance", {})
        sen_cfg = get(det, "sensitive", {})
        dedup_cfg = get(det, "dedup", {})
        llm_cfg = get(self.cfg, "llm", {})
        media_cfg = get(self.cfg, "media", {})

        # 1) AI 相关性（规则）
        passed, score, reason = decide(text, float(rel_cfg.get("threshold", 0.4)), rel_cfg.get("extra_keywords"))
        need_llm_judge = (not passed) and reason.startswith("边缘")
        if not passed and not need_llm_judge:
            post_id = self.db.add_post(item_id, status="skipped", body=reason)
            log.info("[跳过] %s: %s", item["url"], reason)
            return {"post_id": post_id, "status": "skipped", "reason": reason}

        # 2) 敏感（规则）
        sensitive, hits = check_sensitive(text, sen_cfg.get("extra_terms"))
        if sensitive and sen_cfg.get("hard_block", True):
            reason = f"命中敏感词: {', '.join(hits[:5])}"
            post_id = self.db.add_post(item_id, status="skipped", body=reason)
            log.info("[跳过-敏感] %s: %s", item["url"], reason)
            return {"post_id": post_id, "status": "skipped", "reason": reason}

        # 3) 与已发布内容去重
        recent = self.db.get_recent_published(int(dedup_cfg.get("recent_posts", 30)))
        # 分别与标题和正文比较（拼接会稀释相似度）
        recent_texts: list[str] = []
        for r in recent:
            if r.get("body"):
                recent_texts.append(r["body"])
            if r.get("title"):
                recent_texts.append(r["title"])
        dup, sim, best_txt = is_duplicate(text, recent_texts,
                                        float(dedup_cfg.get("text_similarity", 0.82)))
        if dup:
            reason = f"与已发布内容重复(相似度 {sim}): {best_txt}"
            post_id = self.db.add_post(item_id, status="skipped", body=reason)
            log.info("[跳过-重复] %s: %s", item["url"], reason)
            return {"post_id": post_id, "status": "skipped", "reason": reason}

        # 4) LLM 总结 + 复核
        if self.llm.available and not skip_llm:
            try:
                result = self.llm.chat_json(SYSTEM_PROMPT, build_user_prompt(item))
            except Exception as e:
                log.warning("LLM 总结失败，改用本地降级: %s", e)
                result = fallback_summarize(item)
            if need_llm_judge and not result.get("relevant", True):
                reason = f"LLM 判定与 AI 无关: {result.get('reason', '')}"
                post_id = self.db.add_post(item_id, status="skipped", body=reason)
                log.info("[跳过] %s", reason)
                return {"post_id": post_id, "status": "skipped", "reason": reason}
            if result.get("sensitive") or (sensitive and sen_cfg.get("llm_verify", True)):
                reason = f"敏感内容: {result.get('reason', 'LLM 判定敏感')}"
                post_id = self.db.add_post(item_id, status="skipped", body=reason)
                log.info("[跳过-敏感] %s", reason)
                return {"post_id": post_id, "status": "skipped", "reason": reason}
        else:
            result = fallback_summarize(item,
                                       int(llm_cfg.get("max_title_len", 30)),
                                       int(llm_cfg.get("max_body_len", 350)))

        title = str(result.get("title") or "").strip()[: int(llm_cfg.get("max_title_len", 30))]
        body = str(result.get("body") or "").strip()[: int(llm_cfg.get("max_body_len", 350))]
        hashtags = sanitize_hashtags(result.get("hashtags"), int(llm_cfg.get("max_hashtags", 5)))
        if not title and not body:
            post_id = self.db.add_post(item_id, status="skipped", body="LLM 输出为空")
            return {"post_id": post_id, "status": "skipped", "reason": "LLM 输出为空"}

        # 5) 出图：封面 + 原文配图
        images: list[str] = []
        img_dir = self.image_root / f"item_{item_id}"
        if get(media_cfg, "cover.enabled", True):
            cover_path = img_dir / "cover.png"
            source_label = item.get("author") or item.get("source") or "AI News"
            ok = generate_cover(title, source_label, (item.get("published_at") or "")[:10],
                               cover_path, get(media_cfg, "cover", {}))
            if ok:
                images.append(str(cover_path))
        if get(media_cfg, "download_images", True):
            try:
                media_urls = json.loads(item.get("media") or "[]")
            except json.JSONDecodeError:
                media_urls = []
            max_img = int(get(media_cfg, "max_images", 9))
            for i, u in enumerate(media_urls):
                if len(images) >= max_img:
                    break
                p = download_image(u, img_dir, name=f"media_{i}")
                if p and p not in images:
                    images.append(p)
        if not images:
            reason = "没有任何可用图片（封面生成失败且无配图）"
            post_id = self.db.add_post(item_id, status="failed", body=reason)
            log.warning("[失败] %s", reason)
            return {"post_id": post_id, "status": "failed", "reason": reason}

        # 6) 发布
        text_full = self._compose_text(title, body, hashtags)
        post_id = self.db.add_post(item_id, title=title, body=body, hashtags=hashtags,
                                   images=images, status="ready")
        if dry_run or not self.publisher:
            log.info("[dry-run/未配置发布] 待发布: %s | %s", title, item["url"])
            return {"post_id": post_id, "status": "ready", "title": title}
        try:
            res = self.publisher.publish(images, text_full, dry_run=False)
            # 网页发布器返回 dict，API 发布器返回字符串 item_id
            if isinstance(res, dict):
                ok = bool(res.get("ok"))
                douyin_item_id = str(res.get("item_id", ""))
                note = str(res.get("message", ""))
            else:
                ok = True
                douyin_item_id = str(res)
                note = ""
            if ok:
                self.db.update_post(post_id, status="published", douyin_item_id=douyin_item_id,
                                    published_at=datetime.now(timezone.utc).isoformat(timespec="seconds"),
                                    error=note[:500])
                log.info("[已发布] %s -> 抖音 item_id=%s %s", title, douyin_item_id, note)
                return {"post_id": post_id, "status": "published", "title": title, "note": note}
            raise RuntimeError(note or "发布器返回失败")
        except Exception as e:
            self.db.update_post(post_id, status="failed", error=str(e)[:500])
            log.error("[发布失败] %s: %s", title, e)
            return {"post_id": post_id, "status": "failed", "title": title, "error": str(e)}

    def _compose_text(self, title: str, body: str, hashtags: list[str]) -> str:
        prefix = get(self.cfg, "douyin.text_prefix", "") or ""
        parts = [prefix, title, "", body]
        if hashtags:
            parts += ["", " ".join("#" + t for t in hashtags)]
        text = "\n".join(p for p in parts if p != "" or p is None)
        return text[:1000]

    # ---------- 整体运行 ----------
    def run(self, limit: int = 5, sources: list[str] | None = None, dry_run: bool = False,
            skip_llm: bool = False) -> dict:
        stats = {"fetched_new": 0, "processed": 0, "skipped": 0, "ready": 0, "published": 0, "failed": 0}
        new_ids = self.crawl(sources)
        stats["fetched_new"] = len(new_ids)
        for item_id in new_ids[:limit]:
            res = self.process_item(item_id, dry_run=dry_run, skip_llm=skip_llm)
            if not res:
                continue
            stats["processed"] += 1
            s = res.get("status", "skipped")
            if s in stats:
                stats[s] += 1
        return stats
