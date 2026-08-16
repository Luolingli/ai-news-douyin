"""X(Twitter) 直抓爬虫（Playwright + 账号 cookies，实验性）"""
from __future__ import annotations

import json
import re
from pathlib import Path

from ..models import RawItem
from .base import Source, SourceError

TWEET_RE = re.compile(r"(?:twitter|x)\.com/[^/]+/status/(\d+)")


class TwitterXSource(Source):
    """
    需要：
      1) pip install playwright && playwright install chromium
      2) 浏览器登录 x.com 后导出 cookies 为 JSON 数组文件（与 DouYinSparkFlow 的 cookies 格式一致）
    """

    type = "twitter_x"

    def __init__(self, cfg: dict):
        super().__init__(cfg)
        self.accounts: list[str] = cfg.get("accounts", [])
        self.cookies_path: str = cfg.get("cookies_path") or ""

    def fetch(self):
        try:
            from playwright.sync_api import sync_playwright
        except ImportError as e:
            raise SourceError("未安装 playwright：pip install playwright && playwright install chromium") from e

        cookies = []
        if self.cookies_path and Path(self.cookies_path).exists():
            cookies = json.loads(Path(self.cookies_path).read_text(encoding="utf-8"))

        items = []
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            ctx = browser.new_context(timezone_id="Asia/Shanghai", viewport={"width": 1280, "height": 2000})
            if cookies:
                ctx.add_cookies(cookies)
            page = ctx.new_page()
            for acc in self.accounts:
                url = f"https://x.com/{acc}"
                try:
                    page.goto(url, timeout=60000, wait_until="domcontentloaded")
                    page.wait_for_timeout(5000)
                    for _ in range(3):
                        page.mouse.wheel(0, 2000)
                        page.wait_for_timeout(1500)
                    tweets = page.locator("article[data-testid=tweet]").all()
                    for t in tweets[: self.max_items]:
                        text_el = t.locator("[data-testid=tweetText]").first
                        text = text_el.inner_text().strip() if text_el.count() else ""
                        if not text:
                            continue
                        time_el = t.locator("time").first
                        published = time_el.get_attribute("datetime") if time_el.count() else ""
                        a_el = t.locator("a[href*=status]").first
                        href = a_el.get_attribute("href") if a_el.count() else ""
                        m = TWEET_RE.search(href or "")
                        status_id = m.group(1) if m else ""
                        media = []
                        for img in t.locator("img[src*=pbs.twimg.com]").all():
                            s = img.get_attribute("src")
                            if s and s not in media:
                                media.append(s)
                        items.append(RawItem(
                            source=f"{self.name}/{acc}",
                            source_type=self.type,
                            source_id=status_id or href or text[:40],
                            url=href if href.startswith("http") else f"https://x.com{href}",
                            author=acc,
                            text=text,
                            published_at=published,
                            media_urls=media,
                        ))
                except Exception as e:
                    raise SourceError(f"X.com 抓取 {acc} 失败: {e}") from e
            browser.close()
        return items
