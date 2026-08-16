"""抖音创作者中心网页版图文发布器（Playwright + cookies）"""
from __future__ import annotations

import glob
import logging
import os
import re
import time
from pathlib import Path

from ..config import env
from .cookies import load_cookies, resolve_cookies_path, save_cookies

log = logging.getLogger("ai_news.douyin_web")

UPLOAD_URL = "https://creator.douyin.com/creator-micro/content/upload"
LOGIN_MARKERS = ["创作者登录", "我是创作者", "扫码登录", "验证码登录", "密码登录"]

TAB_图文 = re.compile(r"^\s*图文\s*$")


def find_browser_executable() -> str | None:
    """发现本机已装的 Chrome for Testing / Playwright Chromium"""
    env_exe = env("PLAYWRIGHT_EXECUTABLE")
    if env_exe and Path(env_exe).exists():
        return env_exe
    patterns = [
        # macOS
        str(Path.home() / "Library/Caches/ms-playwright/chromium-*/chrome-mac-*/Google Chrome for Testing.app/Contents/MacOS/Google Chrome for Testing"),
        str(Path.home() / "Library/Caches/ms-playwright/chromium-*/chrome-mac-arm64/Google Chrome for Testing.app/Contents/MacOS/Google Chrome for Testing"),
        # Linux
        str(Path.home() / ".cache/ms-playwright/chromium-*/chrome-linux/chrome"),
        # Windows
        str(Path(os.environ.get("LOCALAPPDATA", "")) / "ms-playwright/chromium-*/chrome-win/chrome.exe"),
    ]
    found = []
    for pat in patterns:
        found += glob.glob(pat)
    if not found:
        return None
    found.sort(reverse=True)
    return found[0]


class DouyinWebPublisher:
    """
    在 creator.douyin.com 上模拟人工发布图文。
    需要：playwright 已安装、cookies 有效（keepalive 设施会自动维护）。
    选择器基于 2026 年创作者中心界面，改版后如失败会截图存档，便于适配。
    """

    def __init__(self, cfg: dict | None = None):
        cfg = cfg or {}
        self.cookies_path = resolve_cookies_path(cfg.get("cookies_path") or "", cfg.get("data_dir", "data"))
        self.headless = bool(cfg.get("headless", False))
        self.timeout = int(cfg.get("timeout", 90000))
        self.screenshot_dir = cfg.get("screenshot_dir") or "data/logs/screenshots"

    # ---------- 基础 ----------
    def _new_context(self, playwright):
        exe = find_browser_executable()
        if exe:
            log.info("使用浏览器: %s", exe)
            browser = playwright.chromium.launch(headless=self.headless, executable_path=exe)
        else:
            log.warning("未找到 Chrome for Testing，尝试 playwright 自带浏览器（需 playwright install chromium）")
            browser = playwright.chromium.launch(headless=self.headless)
        ctx = browser.new_context(timezone_id="Asia/Shanghai", viewport={"width": 1440, "height": 900},
                                 locale="zh-CN")
        cookies = load_cookies(self.cookies_path)
        if cookies:
            ctx.add_cookies(cookies)
            log.info("已加载 %d 条 cookies (%s)", len(cookies), self.cookies_path)
        else:
            log.warning("未加载到 cookies（%s），需要登录", self.cookies_path or "未配置")
        return browser, ctx

    def _is_logged_in(self, page) -> bool:
        try:
            text = page.locator("body").inner_text(timeout=6000)
        except Exception:
            return False
        if any(m in text for m in LOGIN_MARKERS):
            return False
        if "passport" in page.url or "sso" in page.url:
            return False
        return True

    def _snapshot(self, page, name: str) -> str:
        d = Path(self.screenshot_dir)
        d.mkdir(parents=True, exist_ok=True)
        p = d / f"{name}.png"
        try:
            page.screenshot(path=str(p), full_page=False)
            log.info("已截图: %s", p)
        except Exception as e:
            log.warning("截图失败: %s", e)
        return str(p)

    # ---------- 登录检查 ----------
    def check_login(self) -> dict:
        """只读检查：cookies 是否能在创作者中心保持登录（不发布任何内容）"""
        from playwright.sync_api import sync_playwright

        with sync_playwright() as p:
            browser, ctx = self._new_context(p)
            try:
                page = ctx.new_page()
                page.goto(UPLOAD_URL, wait_until="domcontentloaded", timeout=self.timeout)
                page.wait_for_timeout(6000)
                ok = self._is_logged_in(page)
                self._snapshot(page, "login_check")
                name = ""
                if ok:
                    try:
                        name = page.locator("[class*=avatar-name], .name, [class*=user-name]").first.inner_text(timeout=3000)
                    except Exception:
                        name = ""
                return {"logged_in": ok, "url": page.url, "account": name.strip()[:40] if name else ""}
            finally:
                browser.close()

    # ---------- 交互登录（扫码） ----------
    def login_interactive(self, wait_minutes: int = 5) -> dict:
        """弹出可见浏览器，等待用户扫码登录后保存 cookies"""
        from playwright.sync_api import sync_playwright

        log.info("弹出浏览器窗口，请用抖音 APP 扫码登录（最多等 %d 分钟）", wait_minutes)
        with sync_playwright() as p:
            browser, ctx = self._new_context(p)
            try:
                page = ctx.new_page()
                page.goto(UPLOAD_URL, wait_until="domcontentloaded", timeout=self.timeout)
                deadline = time.time() + wait_minutes * 60
                while time.time() < deadline:
                    page.wait_for_timeout(3000)
                    if self._is_logged_in(page):
                        page.wait_for_timeout(3000)
                        break
                if self._is_logged_in(page):
                    if self.cookies_path:
                        save_cookies(ctx.cookies(), self.cookies_path)
                    self._snapshot(page, "login_ok")
                    return {"ok": True, "cookies_path": self.cookies_path}
                self._snapshot(page, "login_timeout")
                return {"ok": False, "error": "等待登录超时"}
            finally:
                browser.close()

    # ---------- 发布 ----------
    def publish(self, image_paths: list[str], text: str, dry_run: bool = False) -> dict:
        if dry_run:
            log.info("[dry-run] 将打开网页版发布：%d 张图，文案 %d 字", len(image_paths), len(text))
            return {"ok": True, "dry_run": True}
        from playwright.sync_api import sync_playwright

        result: dict = {"ok": False, "message": "", "item_id": ""}
        with sync_playwright() as p:
            browser, ctx = self._new_context(p)
            try:
                page = ctx.new_page()
                page.goto(UPLOAD_URL, wait_until="domcontentloaded", timeout=self.timeout)
                page.wait_for_timeout(6000)
                if not self._is_logged_in(page):
                    self._snapshot(page, "publish_not_login")
                    raise RuntimeError("未登录或 cookies 失效，请先执行: python main.py douyin web login")

                self._click_image_tab(page)
                self._upload_images(page, image_paths)
                self._fill_description(page, text)
                self._add_topics(page, text)
                self._click_publish(page)
                ok = self._verify_success(page, result)
                if ok and result.get("message") == "发布成功" and self.cookies_path:
                    save_cookies(ctx.cookies(), self.cookies_path)
                result["ok"] = ok
            except Exception as e:
                self._snapshot(page, "publish_failed")
                result["message"] = str(e)[:300]
                log.error("网页发布失败: %s", e)
            finally:
                browser.close()
        return result

    # ---------- 试发布（不点发布按钮） ----------
    def upload_only(self, image_paths: list[str], text: str) -> dict:
        """验证上传流程：切图文页签→传图→填描述→加话题，然后停住（不点发布）"""
        from playwright.sync_api import sync_playwright

        result: dict = {"ok": False, "message": ""}
        with sync_playwright() as p:
            browser, ctx = self._new_context(p)
            try:
                page = ctx.new_page()
                page.goto(UPLOAD_URL, wait_until="domcontentloaded", timeout=self.timeout)
                page.wait_for_timeout(6000)
                if not self._is_logged_in(page):
                    self._snapshot(page, "try_not_login")
                    raise RuntimeError("未登录或 cookies 失效，请先执行: python main.py douyin web login")
                self._click_image_tab(page)
                self._upload_images(page, image_paths)
                self._fill_description(page, text)
                self._add_topics(page, text)
                self._snapshot(page, "try_ready")
                result["ok"] = True
                result["message"] = "上传与文案填写完成（未点发布），见截图 try_ready.png"
                log.info("试发布完成（未点发布按钮）")
            except Exception as e:
                self._snapshot(page, "try_failed")
                result["message"] = str(e)[:300]
                log.error("试发布失败: %s", e)
            finally:
                browser.close()
        return result

    # ---------- 各步骤（防御式选择器） ----------
    def _click_image_tab(self, page) -> None:
        """切换到「图文」上传页签"""
        attempts = [
            lambda: page.locator("[class*=tab-item]").filter(has_text=re.compile(r"^发布图文$")).first.click(timeout=8000),
            lambda: page.locator("[class*=tab]").filter(has_text=re.compile(r"^发布图文$")).first.click(timeout=8000),
            lambda: page.get_by_text("发布图文", exact=True).first.click(timeout=8000),
        ]
        last_err = None
        for fn in attempts:
            try:
                fn()
                page.wait_for_timeout(1500)
                return
            except Exception as e:
                last_err = e
        raise RuntimeError(f"找不到「图文」页签: {last_err}")

    def _upload_images(self, page, image_paths: list[str]) -> None:
        """选择图片文件并等待上传完成"""
        inputs = page.locator("input[type=file]")
        count = inputs.count()
        if count == 0:
            raise RuntimeError("找不到文件上传控件（图文页签未激活？）")
        # 优先选 accept 含 image 的输入框，否则取最后一个
        target = None
        for i in range(count):
            acc = (inputs.nth(i).get_attribute("accept") or "").lower()
            if "image" in acc:
                target = inputs.nth(i)
                break
        if target is None:
            target = inputs.nth(count - 1)
        target.set_input_files(image_paths)
        log.info("已选择 %d 张图片，等待上传...", len(image_paths))
        # 等待上传完成：预览图出现且不再有「上传中」
        deadline = time.time() + 120
        while time.time() < deadline:
            page.wait_for_timeout(2000)
            try:
                body = page.locator("body").inner_text(timeout=3000)
            except Exception:
                body = ""
            imgs = page.locator(".semi-upload-picture img, [class*=upload] img, img[src*=douyinpic], img[src*=byteimg]")
            if imgs.count() >= len(image_paths) and "上传中" not in body:
                log.info("图片上传完成（预览 %d 张）", imgs.count())
                page.wait_for_timeout(1500)
                return
        raise RuntimeError("等待图片上传完成超时")

    def _fill_description(self, page, text: str) -> None:
        """填写标题输入框 + 正文（contenteditable，输入 # 会自动变成话题标签）"""
        title, _, rest = text.partition(chr(10) * 2)
        # 标题输入框
        title_inp = page.locator("input[placeholder='添加作品标题']").first
        if title_inp.count() > 0 and title_inp.is_visible():
            title_inp.click()
            title_inp.fill(title[:50])
            log.info("标题已填写: %s", title[:30])
        # 正文（含 #话题）
        ce = page.locator("[contenteditable=true]").first
        ce.wait_for(state="visible", timeout=15000)
        ce.click()
        page.keyboard.type(rest or title, delay=3)
        page.wait_for_timeout(800)
        log.info("正文已填写（%d 字）", len(rest or title))
    def _add_topics(self, page, text: str) -> None:
        """话题已在正文中通过 # 自动转为标签；这里校验数量并记录（失败不阻断）"""
        tags = re.findall(r"#([\w一-鿿]+)", text)
        if not tags:
            return
        try:
            chips = page.locator("[class*=tag-hash-view-name]")
            page.wait_for_timeout(1500)
            log.info("话题标签已生效 %d/%d: %s", chips.count(), len(tags[:5]), ", ".join(tags[:5]))
        except Exception as e:
            log.warning("话题校验失败（不影响发布）: %s", e)
    def _click_publish(self, page) -> None:
        """点击发布按钮（含二次确认弹窗）"""
        attempts = [
            lambda: page.get_by_role("button", name=re.compile(r"^发布$")).first.click(timeout=8000),
            lambda: page.get_by_role("button", name=re.compile(r"发布作品")).first.click(timeout=8000),
            lambda: page.locator(".semi-button-primary").filter(has_text=re.compile(r"发布")).first.click(timeout=8000),
        ]
        last_err = None
        for fn in attempts:
            try:
                fn()
                page.wait_for_timeout(2000)
                # 二次确认弹窗
                confirm = page.get_by_role("dialog")
                if confirm.count() > 0:
                    btn = confirm.locator("button").filter(has_text=re.compile(r"发布|确定|确认")).first
                    if btn.count() > 0:
                        btn.click(timeout=5000)
                        page.wait_for_timeout(2000)
                log.info("已点击发布")
                return
            except Exception as e:
                last_err = e
        raise RuntimeError(f"找不到发布按钮: {last_err}")

    def _verify_success(self, page, result: dict) -> bool:
        """等待发布结果：URL 跳转 / 成功提示"""
        deadline = time.time() + 90
        while time.time() < deadline:
            page.wait_for_timeout(3000)
            url = page.url
            try:
                body = page.locator("body").inner_text(timeout=3000)
            except Exception:
                body = ""
            if "发布成功" in body or "作品已发布" in body or "上传成功" in body or "内容管理" in url:
                m = re.search(r"aweme_id[=/](\d+)|item_id[=/](\d+)", url)
                result["item_id"] = m.group(1) if m else ""
                result["message"] = "发布成功"
                self._snapshot(page, "publish_ok")
                return True
        self._snapshot(page, "publish_unknown")
        result["message"] = f"已点击发布但未确认成功（当前URL: {page.url[:120]}），请到创作者中心-内容管理查看"
        return True  # 视为已提交，交由人工确认
