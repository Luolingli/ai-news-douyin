"""HTML/CSS 封面渲染：Playwright 截图，像素级复刻设计稿（data/samples/1.html）"""
from __future__ import annotations

import logging
from pathlib import Path

log = logging.getLogger("ai_news.html_cover")

WIDTH, HEIGHT = 1080, 1440

TEMPLATE = """<!DOCTYPE html>
<html lang="zh-CN"><head><meta charset="UTF-8"><style>
* { margin: 0; padding: 0; box-sizing: border-box; }
body { background: #020517; display: flex; align-items: center; justify-content: center; }
.cover {
  position: relative; width: 1080px; height: 1440px; overflow: hidden;
  background:
    linear-gradient(rgba(6,10,31,0.55), rgba(2,5,23,0.45)),
    __BG__ ,
    radial-gradient(ellipse at 78% 16%, #1a1045 0%, rgba(6,10,31,0.92) 55%, #020517 100%);
}
.glow { position: absolute; top: -20%; right: -15%; width: 760px; height: 760px;
  background: radial-gradient(circle, rgba(122,108,240,0.16) 0%, transparent 70%);
  filter: blur(60px); pointer-events: none; }
.metaphor { position: absolute; top: 12%; right: 6%; width: 460px; height: 560px; opacity: 0.28;
  pointer-events: none; }
.metaphor svg { width: 100%; height: 100%; }
.noise { position: absolute; inset: 0; pointer-events: none; opacity: 0.5;
  background-image: url("data:image/svg+xml,%3Csvg viewBox='0 0 256 256' xmlns='http://www.w3.org/2000/svg'%3E%3Cfilter id='n'%3E%3CfeTurbulence type='fractalNoise' baseFrequency='0.8' numOctaves='4' stitchTiles='stitch'/%3E%3C/filter%3E%3Crect width='100%25' height='100%25' filter='url(%23n)' opacity='0.05'/%3E%3C/svg%3E"); }
.brand { position: absolute; top: 82px; left: 95px; z-index: 10;
  font-family: 'Helvetica Neue', 'PingFang SC', sans-serif; font-weight: 600;
  font-size: 30px; letter-spacing: 9px; color: #f0f0ff; }
.brand b { color: #7a6cf0; font-weight: 700; }
.main-title { position: absolute; top: 33%; left: 95px; right: 16%; z-index: 10;
  font-family: 'Songti SC', 'Noto Serif CJK SC', 'Noto Serif SC', serif;
  font-weight: 900; font-size: 74px; line-height: 1.32; color: #f0f0ff;
  letter-spacing: 5px; text-shadow: 0 20px 60px rgba(122,108,240,0.28);
  word-break: break-all; }
.capsule { position: absolute; left: 95px; z-index: 10;
  font-family: 'PingFang SC', 'Helvetica Neue', sans-serif; font-weight: 300;
  font-size: 30px; color: #b0b3d6; letter-spacing: 4px;
  border-left: 5px solid #7a6cf0; padding-left: 22px; line-height: 1.9; opacity: 0.92; }
.meta { position: absolute; bottom: 92px; left: 95px; right: 95px; z-index: 10;
  border-top: 1px solid rgba(255,255,255,0.10); padding-top: 30px;
  display: flex; justify-content: space-between; align-items: flex-end; }
.meta-left { font-family: 'PingFang SC', sans-serif; font-size: 28px; color: #b0b3d6;
  font-weight: 300; letter-spacing: 2px; line-height: 2; }
.meta-left strong { color: #f0f0ff; font-weight: 500; }
.meta-left .date { color: #787d8f; font-size: 26px; }
.meta-right { font-family: 'Helvetica Neue', sans-serif; font-size: 24px;
  color: rgba(255,255,255,0.35); letter-spacing: 5px; font-weight: 500; }
</style></head><body>
<div class="cover">
  <div class="glow"></div>
  <div class="metaphor">__METAPHOR__</div>
  <div class="noise"></div>
  <div class="brand">AI <b>NEWS</b></div>
  <h1 class="main-title">__TITLE__</h1>
  __CAPSULE__
  <div class="meta">
    <div class="meta-left"><strong>来源：__SOURCE__</strong><br><span class="date">__DATE__</span></div>
    <div class="meta-right">COVER STORY</div>
  </div>
</div></body></html>
"""

METAPHOR_SVG = {
    "shield": (
        "<svg viewBox='0 0 460 560'><defs><linearGradient id='g1' x1='0%25' y1='0%25' x2='100%25' y2='100%25'>"
        "<stop offset='0%25' stop-color='#7a6cf0'/><stop offset='100%25' stop-color='#2a1b5e'/></linearGradient></defs>"
        "<circle cx='230' cy='210' r='150' stroke='url(%23g1)' stroke-width='1.5' stroke-dasharray='10 7' fill='none'/>"
        "<circle cx='230' cy='210' r='110' stroke='url(%23g1)' stroke-width='1' stroke-dasharray='5 9' fill='none'/>"
        "<path d='M230 60 L360 270 L230 480 L100 270 Z' stroke='url(%23g1)' stroke-width='1.2' stroke-dasharray='14 5' fill='none'/>"
        "<line x1='230' y1='60' x2='230' y2='480' stroke='url(%23g1)' stroke-width='0.6' opacity='0.5'/>"
        "<line x1='100' y1='270' x2='360' y2='270' stroke='url(%23g1)' stroke-width='0.6' opacity='0.5'/></svg>"
    ),
    "nodes": (
        "<svg viewBox='0 0 460 560'><defs><linearGradient id='g1' x1='0%25' y1='0%25' x2='100%25' y2='100%25'>"
        "<stop offset='0%25' stop-color='#7a6cf0'/><stop offset='100%25' stop-color='#2a1b5e'/></linearGradient></defs>"
        "<circle cx='150' cy='180' r='8' fill='url(%23g1)'/><circle cx='300' cy='120' r='11' fill='url(%23g1)'/>"
        "<circle cx='360' cy='260' r='8' fill='url(%23g1)'/><circle cx='240' cy='340' r='8' fill='url(%23g1)'/>"
        "<circle cx='110' cy='380' r='7' fill='url(%23g1)'/><circle cx='320' cy='430' r='9' fill='url(%23g1)'/>"
        "<line x1='150' y1='180' x2='300' y2='120' stroke='url(%23g1)' stroke-width='1'/>"
        "<line x1='300' y1='120' x2='360' y2='260' stroke='url(%23g1)' stroke-width='1'/>"
        "<line x1='360' y1='260' x2='240' y2='340' stroke='url(%23g1)' stroke-width='1'/>"
        "<line x1='240' y1='340' x2='110' y2='380' stroke='url(%23g1)' stroke-width='1'/>"
        "<line x1='110' y1='380' x2='150' y2='180' stroke='url(%23g1)' stroke-width='1'/>"
        "<line x1='300' y1='120' x2='320' y2='430' stroke='url(%23g1)' stroke-width='0.8' opacity='0.5'/>"
        "<line x1='150' y1='180' x2='360' y2='260' stroke='url(%23g1)' stroke-width='0.6' opacity='0.4'/></svg>"
    ),
    "streams": (
        "<svg viewBox='0 0 460 560'><defs><linearGradient id='g1' x1='0%25' y1='0%25' x2='100%25' y2='100%25'>"
        "<stop offset='0%25' stop-color='#7a6cf0'/><stop offset='100%25' stop-color='#2a1b5e'/></linearGradient></defs>"
        "<path d='M60 150 Q230 60 400 150' stroke='url(%23g1)' stroke-width='1.6' fill='none'/>"
        "<path d='M60 240 Q230 150 400 240' stroke='url(%23g1)' stroke-width='1.2' fill='none' opacity='0.8'/>"
        "<path d='M60 340 Q230 430 400 340' stroke='url(%23g1)' stroke-width='1.6' fill='none'/>"
        "<path d='M60 440 Q230 530 400 440' stroke='url(%23g1)' stroke-width='1' fill='none' opacity='0.7'/>"
        "<circle cx='230' cy='105' r='6' fill='url(%23g1)'/><circle cx='230' cy='385' r='6' fill='url(%23g1)'/></svg>"
    ),
    "grid": (
        "<svg viewBox='0 0 460 560'><defs><linearGradient id='g1' x1='0%25' y1='0%25' x2='100%25' y2='100%25'>"
        "<stop offset='0%25' stop-color='#7a6cf0'/><stop offset='100%25' stop-color='#2a1b5e'/></linearGradient></defs>"
        "<line x1='120' y1='60' x2='120' y2='500' stroke='url(%23g1)' stroke-width='0.8'/>"
        "<line x1='230' y1='60' x2='230' y2='500' stroke='url(%23g1)' stroke-width='0.8'/>"
        "<line x1='340' y1='60' x2='340' y2='500' stroke='url(%23g1)' stroke-width='0.8'/>"
        "<line x1='80' y1='180' x2='400' y2='180' stroke='url(%23g1)' stroke-width='0.8'/>"
        "<line x1='80' y1='300' x2='400' y2='300' stroke='url(%23g1)' stroke-width='0.8'/>"
        "<line x1='80' y1='420' x2='400' y2='420' stroke='url(%23g1)' stroke-width='0.8'/></svg>"
    ),
}


def _esc(s: str) -> str:
    return (s or "").replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def generate_html_cover(title: str, subtitle: str, source: str, date_str: str,
                        out_path: str | Path, cfg_cover: dict | None = None,
                        metaphor_text: str = "", bg_image: str | None = None) -> bool:
    """HTML/CSS 渲染封面（设计稿同款），失败返回 False 由调用方回退"""
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        return False
    from .editorial_cover import metaphor_for

    cfg_cover = cfg_cover or {}
    kind = cfg_cover.get("metaphor", "auto")
    if kind == "auto":
        kind = metaphor_for(metaphor_text or title)
    html = TEMPLATE
    html = html.replace("__TITLE__", _esc(title or "AI 新闻"))
    html = html.replace("__SOURCE__", _esc(source))
    html = html.replace("__DATE__", _esc(date_str))
    html = html.replace("__METAPHOR__", METAPHOR_SVG.get(kind, METAPHOR_SVG["grid"]))
    sub = (subtitle or "").strip()
    if sub:
        html = html.replace("__CAPSULE__", "<div class='capsule' style='top: __CAP_TOP__px'>" + _esc(sub[:24]) + "</div>")
    else:
        html = html.replace("__CAPSULE__", "")
    if bg_image and Path(bg_image).exists():
        uri = Path(bg_image).resolve().as_uri()
        html = html.replace("__BG__", "url('" + uri + "')")
    else:
        html = html.replace("__BG__", "none")
    # 副标题位置由标题行数决定（估算：10字内一行，否则两行）
    cap_top = 552 if len(title or "") <= 10 else 760
    html = html.replace("__CAP_TOP__", str(cap_top))
    try:
        Path(out_path).parent.mkdir(parents=True, exist_ok=True)
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True, channel="chrome")
            try:
                page = browser.new_page(viewport={"width": WIDTH, "height": HEIGHT})
                page.set_content(html, wait_until="load")
                page.wait_for_timeout(600)
                page.locator(".cover").screenshot(path=str(out_path))
                return True
            finally:
                browser.close()
    except Exception as e:
        log.warning("HTML 封面渲染失败: %s", e)
        return False
