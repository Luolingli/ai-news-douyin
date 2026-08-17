"""编辑级封面：按用户设计稿（1.html）实现——径向渐变+光晕、抽象隐喻、噪点质感、衬线标题、信息层级"""
from __future__ import annotations

import logging
import math
from pathlib import Path

log = logging.getLogger("ai_news.cover")

WIDTH, HEIGHT = 1080, 1440

# 设计稿配色
COLOR_BG_BOTTOM = (2, 5, 23)
COLOR_BG_MID = (6, 10, 31)
COLOR_BG_TOP = (13, 20, 51)
COLOR_GLOW = (26, 16, 69)
COLOR_ACCENT = (122, 108, 240)
COLOR_TEXT = (240, 240, 255)
COLOR_TEXT_DIM = (176, 179, 214)
COLOR_TEXT_FAINT = (120, 125, 165)
COLOR_METAPHOR = (160, 150, 255)

SERIF_FONTS = [
    "/System/Library/Fonts/Songti.ttc",
    "/System/Library/Fonts/STSongti.ttc",
    "/usr/share/fonts/opentype/noto/NotoSerifCJK-Regular.ttc",
    "/usr/share/fonts/opentype/noto/NotoSerifCJK-Bold.ttc",
]
SANS_FONTS = [
    "/System/Library/Fonts/STHeiti Light.ttc",
    "/System/Library/Fonts/PingFang.ttc",
    "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
]


def find_font(candidates: list[str]) -> str | None:
    for p in candidates:
        if Path(p).exists():
            return p
    return None


def _lerp(a: tuple, b: tuple, t: float) -> tuple:
    return tuple(int(a[i] + (b[i] - a[i]) * t) for i in range(3))


def _base_background(draw, W: int, H: int) -> None:
    """垂直三段渐变（顶→底：#0d1433 → #060a1f → #020517）"""
    stops = [(0.0, COLOR_BG_TOP), (0.55, COLOR_BG_MID), (1.0, COLOR_BG_BOTTOM)]
    for y in range(H):
        t = y / H
        for i in range(len(stops) - 1):
            t0, c0 = stops[i]
            t1, c1 = stops[i + 1]
            if t0 <= t <= t1:
                color = _lerp(c0, c1, (t - t0) / (t1 - t0))
                break
        draw.line([(0, y), (W, y)], fill=color)


def _radial_glow(W: int, H: int) -> "Image":
    from PIL import Image, ImageDraw

    glow = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    gd = ImageDraw.Draw(glow)
    cx, cy, R = int(W * 0.78), int(H * 0.16), int(H * 0.72)
    steps = 90
    for i in range(steps, 0, -1):
        r = int(R * i / steps)
        gd.ellipse([cx - r, cy - r, cx + r, cy + r], fill=COLOR_GLOW + (2,))
    return glow


def metaphor_for(text: str) -> str:
    """按新闻主题选择抽象隐喻：安全/风险→破碎盾牌；模型/技术→神经网络节点；芯片算力→光流；默认→网格"""
    t = (text or "").lower()
    if any(k in t for k in ("安全", "风险", "监管", "团队", "解散", "裁员", "泄露", "违规", "审查", "security", "risk", "safety")):
        return "shield"
    if any(k in t for k in ("芯片", "算力", "gpu", "nvidia", "英伟达", "训练成本", "数据中心", "chip", "compute")):
        return "streams"
    if any(k in t for k in ("模型", "发布", "上线", "开源", "训练", "gpt", "claude", "gemini", "llama", "智能体", "agent", "model", "launch")):
        return "nodes"
    return "grid"


def _draw_metaphor(kind: str, W: int, H: int) -> "Image":
    from PIL import Image, ImageDraw

    ov = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(ov)
    cx, cy = int(W * 0.76), int(H * 0.30)
    if kind == "shield":
        R = int(H * 0.15)
        for seg in range(0, 360, 6):
            if (seg // 6) % 3 == 0:
                continue
            d.arc([cx - R, cy - R, cx + R, cy + R], seg, seg + 5, fill=COLOR_METAPHOR + (42,), width=2)
        pts = [(cx, cy - R), (cx + int(R * 0.55), cy), (cx, cy + R), (cx - int(R * 0.55), cy), (cx, cy - R)]
        d.line(pts, fill=COLOR_METAPHOR + (32,), width=1)
        d.line([(cx, cy - int(R * 0.35)), (cx, cy - int(R * 0.08))], fill=(185, 175, 255, 55), width=2)
        d.line([(cx, cy + int(R * 0.08)), (cx, cy + int(R * 0.35))], fill=(185, 175, 255, 55), width=2)
    elif kind == "nodes":
        pts = [(cx - 150, cy - 60), (cx, cy - 120), (cx + 140, cy - 40), (cx + 60, cy + 80), (cx - 110, cy + 90)]
        for i in range(len(pts)):
            for j in range(i + 1, len(pts)):
                d.line([pts[i], pts[j]], fill=COLOR_METAPHOR + (18,), width=1)
        for (x, y) in pts:
            r = 6 if (x, y) != (cx, cy - 120) else 9
            d.ellipse([x - r, y - r, x + r, y + r], fill=(150, 140, 255, 70))
    elif kind == "streams":
        import random

        random.seed(7)
        for _ in range(7):
            x0, y0 = cx - 160, cy + random.randint(-120, 120)
            x1 = cx + 150
            mid = (x0 + x1) / 2 + random.randint(-40, 40)
            pts = [(x0, y0), (int(mid), y0 - 60), (x1, y0)]
            d.line(pts, fill=COLOR_METAPHOR + (40,), width=2)
    else:
        for i in range(4):
            x = int(W * 0.62) + i * 90
            d.line([(x, int(H * 0.12)), (x, int(H * 0.50))], fill=COLOR_METAPHOR + (14,), width=1)
        for j in range(3):
            y = int(H * 0.14) + j * 110
            d.line([(int(W * 0.62), y), (W - 60, y)], fill=COLOR_METAPHOR + (14,), width=1)
    return ov


def _add_noise(img: "Image", alpha: int = 30) -> "Image":
    from PIL import Image

    W, H = img.size
    n = Image.effect_noise((W // 6, H // 6), 40).convert("L").resize((W, H))
    a = Image.new("L", (W, H), alpha)
    return Image.alpha_composite(img.convert("RGBA"), Image.merge("RGBA", (n, n, n, a))).convert("RGB")


def _draw_spaced(draw, xy, text: str, font, fill, tracking: int = 0):
    """逐字绘制实现字距（letter-spacing）"""
    x, y = xy
    for ch in text:
        draw.text((x, y), ch, font=font, fill=fill)
        x += draw.textlength(ch, font=font) + tracking


def _wrap(draw, text: str, font, max_width: int) -> list[str]:
    lines, cur = [], ""
    for ch in text:
        if draw.textlength(cur + ch, font=font) <= max_width:
            cur += ch
        else:
            if cur:
                lines.append(cur)
            cur = ch
    if cur:
        lines.append(cur)
    return lines


def generate_editorial_cover(title: str, subtitle: str, source: str, date_str: str,
                             out_path: str | Path, cfg_cover: dict | None = None,
                             metaphor_text: str = "") -> bool:
    """生成编辑级封面（1080x1440）。失败返回 False，由调用方回退基础封面"""
    try:
        from PIL import Image, ImageDraw, ImageFont
    except ImportError:
        log.warning("未安装 Pillow，跳过封面生成")
        return False

    cfg_cover = cfg_cover or {}
    try:
        serif = find_font(SERIF_FONTS) or find_font(SANS_FONTS)
        sans = find_font(SANS_FONTS)
        if not serif or not sans:
            log.warning("缺少字体，跳过编辑封面")
            return False

        # 1) 背景 + 光晕
        img = Image.new("RGB", (WIDTH, HEIGHT))
        _base_background(ImageDraw.Draw(img), WIDTH, HEIGHT)
        img = Image.alpha_composite(img.convert("RGBA"), _radial_glow(WIDTH, HEIGHT)).convert("RGB")

        # 2) 抽象隐喻（低透明度）
        kind = cfg_cover.get("metaphor", "auto")
        if kind == "auto":
            kind = metaphor_for(metaphor_text or title)
        img = Image.alpha_composite(img.convert("RGBA"), _draw_metaphor(kind, WIDTH, HEIGHT)).convert("RGB")

        # 3) 噪点质感
        img = _add_noise(img, alpha=int(cfg_cover.get("noise", 30)))
        draw = ImageDraw.Draw(img)
        margin = 70

        # 4) 品牌标（左上，细字重+大字距，AI 白 + NEWS 紫）
        brand_font = ImageFont.truetype(sans, 24)
        _draw_spaced(draw, (margin, 64), "AI", brand_font, COLOR_TEXT, tracking=7)
        x_ai = margin + draw.textlength("AI", font=brand_font) + 7 + 12
        _draw_spaced(draw, (x_ai, 64), "NEWS", brand_font, COLOR_ACCENT, tracking=7)

        # 5) 主标题（宋体 900，左对齐，微阴影）
        size = int(cfg_cover.get("font_size", 68))
        font = ImageFont.truetype(serif, size)
        max_w = WIDTH - margin * 2
        lines = _wrap(draw, title or "AI 新闻", font, max_w)
        while len(lines) > 5 and size > 42:
            size -= 6
            font = ImageFont.truetype(serif, size)
            lines = _wrap(draw, title or "AI 新闻", font, max_w)
        line_h = int(size * 1.32)
        start_y = int(HEIGHT * 0.36)
        shadow = (90, 80, 160)
        for i, line in enumerate(lines):
            y = start_y + i * line_h
            draw.text((margin + 2, y + 2), line, font=font, fill=shadow)
            draw.text((margin, y), line, font=font, fill=COLOR_TEXT)

        # 6) 副标题胶囊行（紫色竖线 + 细字重 + 大字距）
        sub = (subtitle or "").strip()
        if sub:
            cap_y = start_y + len(lines) * line_h + 64
            draw.rectangle([margin, cap_y, margin + 4, cap_y + 76], fill=COLOR_ACCENT)
            cap_font = ImageFont.truetype(sans, 26)
            _draw_spaced(draw, (margin + 22, cap_y + 20), sub[:24], cap_font, COLOR_TEXT_DIM, tracking=3)

        # 7) 底部元信息（hairline + 来源/日期 + COVER STORY）
        rule_y = HEIGHT - 190
        draw.rectangle([margin, rule_y, WIDTH - margin, rule_y + 1], fill=(255, 255, 255, 0) if False else (255, 255, 255))
        # 用低透明度实现 hairline
        rule = Image.new("RGBA", (WIDTH, HEIGHT), (0, 0, 0, 0))
        ImageDraw.Draw(rule).rectangle([margin, rule_y, WIDTH - margin, rule_y + 1], fill=(255, 255, 255, 22))
        img = Image.alpha_composite(img.convert("RGBA"), rule).convert("RGB")
        draw = ImageDraw.Draw(img)
        meta_font = ImageFont.truetype(sans, 25)
        draw.text((margin, rule_y + 26), "来源：" + source, font=meta_font, fill=COLOR_TEXT_DIM)
        draw.text((margin, rule_y + 62), date_str, font=meta_font, fill=COLOR_TEXT_FAINT)
        tag_font = ImageFont.truetype(sans, 20)
        tag = "COVER STORY"
        tag_w = draw.textlength(tag, font=tag_font) + 4 * (len(tag) - 1)
        _draw_spaced(draw, (WIDTH - margin - tag_w, rule_y + 26), tag, tag_font, (95, 100, 135), tracking=4)

        Path(out_path).parent.mkdir(parents=True, exist_ok=True)
        img.save(out_path, "PNG")
        return True
    except Exception as e:
        log.warning("编辑封面生成失败: %s", e)
        return False
