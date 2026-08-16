"""封面卡生成（Pillow，1080x1440 竖版）"""
from __future__ import annotations

import logging
from pathlib import Path

log = logging.getLogger("ai_news.cover")

WIDTH, HEIGHT = 1080, 1440

CJK_FONT_CANDIDATES = [
    # macOS
    "/System/Library/Fonts/PingFang.ttc",
    "/System/Library/Fonts/STHeiti Light.ttc",
    "/System/Library/Fonts/Hiragino Sans GB.ttc",
    "/Library/Fonts/Arial Unicode.ttf",
    # Linux
    "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
    "/usr/share/fonts/noto-cjk/NotoSansCJK-Regular.ttc",
    "/usr/share/fonts/truetype/wqy/wqy-microhei.ttc",
    "/usr/share/fonts/truetype/droid/DroidSansFallbackFull.ttf",
    # Windows
    "C:/Windows/Fonts/msyh.ttc",
    "C:/Windows/Fonts/simhei.ttf",
]

ASCII_FALLBACK = "/System/Library/Fonts/Helvetica.ttc" if Path("/System/Library/Fonts/Helvetica.ttc").exists() else None


def find_cjk_font() -> str | None:
    for p in CJK_FONT_CANDIDATES:
        if Path(p).exists():
            return p
    return None


def _hex(c: str) -> tuple[int, int, int]:
    c = c.lstrip("#")
    return tuple(int(c[i : i + 2], 16) for i in (0, 2, 4))  # type: ignore[return-value]


def _gradient(colors: list[str]) -> list[tuple[int, int, int]]:
    rgb = [_hex(c) for c in colors or ["#0f2027", "#2c5364"]]
    if len(rgb) == 1:
        return rgb * HEIGHT
    out = []
    segs = len(rgb) - 1
    for y in range(HEIGHT):
        pos = y / HEIGHT * segs
        i = min(int(pos), segs - 1)
        t = pos - i
        a, b = rgb[i], rgb[i + 1]
        out.append(tuple(int(a[k] + (b[k] - a[k]) * t) for k in range(3)))  # type: ignore[misc]
    return out


def _wrap_by_width(draw, text: str, font, max_width: int) -> list[str]:
    lines: list[str] = []
    cur = ""
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


def generate_cover(title: str, source: str, date_str: str, out_path: str | Path, cfg_cover: dict | None = None) -> bool:
    """生成竖版封面卡；返回是否成功"""
    try:
        from PIL import Image, ImageDraw, ImageFont
    except ImportError:
        log.warning("未安装 Pillow，跳过封面生成")
        return False

    cfg_cover = cfg_cover or {}
    try:
        img = Image.new("RGB", (WIDTH, HEIGHT))
        draw = ImageDraw.Draw(img)
        for y, color in enumerate(_gradient(cfg_cover.get("gradient", ["#0f2027", "#203a43", "#2c5364"]))):
            draw.line([(0, y), (WIDTH, y)], fill=color)

        font_path = find_cjk_font()
        if not font_path:
            log.warning("未找到中文字体，封面中文可能显示为方块")
            font_path = ASCII_FALLBACK
        if not font_path:
            return False

        base_size = int(cfg_cover.get("font_size", 72))
        size = base_size
        font = ImageFont.truetype(font_path, size)
        margin = 80
        max_width = WIDTH - margin * 2
        lines = _wrap_by_width(draw, title or "AI 新闻", font, max_width)
        # 行数超限则缩小字号
        while len(lines) > 5 and size > 40:
            size -= 8
            font = ImageFont.truetype(font_path, size)
            lines = _wrap_by_width(draw, title or "AI 新闻", font, max_width)

        line_h = int(size * 1.4)
        start_y = HEIGHT // 2 - len(lines) * line_h // 2 - 60
        white = (255, 255, 255)
        for i, line in enumerate(lines):
            draw.text((margin, start_y + i * line_h), line, font=font, fill=white)

        # 底部来源 + 日期
        small = ImageFont.truetype(font_path, 34)
        gray = (200, 210, 230)
        draw.text((margin, HEIGHT - 160), f"来源: {source}", font=small, fill=gray)
        draw.text((margin, HEIGHT - 110), date_str, font=small, fill=gray)

        # 顶部角标
        badge = ImageFont.truetype(font_path, 36)
        draw.text((margin, 70), "AI NEWS", font=badge, fill=(130, 200, 255))

        Path(out_path).parent.mkdir(parents=True, exist_ok=True)
        img.save(out_path, "PNG")
        return True
    except Exception as e:
        log.warning("封面生成失败: %s", e)
        return False


def overlay_on_image(title: str, source: str, date_str: str, bg_path: str,
                     out_path: str | Path, cfg_cover: dict | None = None) -> bool:
    """AI 底图上叠加标题/来源/日期，生成最终封面（1080x1440）"""
    try:
        from PIL import Image, ImageDraw, ImageFont, ImageEnhance
    except ImportError:
        log.warning("未安装 Pillow，跳过封面叠加")
        return False

    cfg_cover = cfg_cover or {}
    try:
        # 1) 底图 cover 缩放（填满 1080x1440 后居中裁剪）
        bg = Image.open(bg_path).convert("RGB")
        scale = max(WIDTH / bg.width, HEIGHT / bg.height)
        bg = bg.resize((int(bg.width * scale), int(bg.height * scale)), Image.LANCZOS)
        left = (bg.width - WIDTH) // 2
        top = (bg.height - HEIGHT) // 2
        img = bg.crop((left, top, left + WIDTH, top + HEIGHT))

        # 2) 压暗：整体半透明黑 + 顶部渐变（保证标题可读）
        dark = Image.new("RGBA", (WIDTH, HEIGHT), (0, 0, 0, 100))
        img = Image.alpha_composite(img.convert("RGBA"), dark).convert("RGB")
        grad = Image.new("RGBA", (WIDTH, HEIGHT), (0, 0, 0, 0))
        gd = ImageDraw.Draw(grad)
        for y in range(HEIGHT):
            a = 0
            if y < 500:
                a = int(160 * (1 - y / 500))
            elif y > HEIGHT - 260:
                a = int(120 * (y - (HEIGHT - 260)) / 260)
            if a:
                gd.line([(0, y), (WIDTH, y)], fill=(0, 0, 0, a))
        img = Image.alpha_composite(img.convert("RGBA"), grad).convert("RGB")

        draw = ImageDraw.Draw(img)
        font_path = find_cjk_font() or ASCII_FALLBACK
        if not font_path:
            return False

        # 3) 标题（自适应字号，最多 5 行）
        size = int(cfg_cover.get("font_size", 72))
        font = ImageFont.truetype(font_path, size)
        margin = 80
        max_width = WIDTH - margin * 2
        lines = _wrap_by_width(draw, title or "AI 新闻", font, max_width)
        while len(lines) > 5 and size > 40:
            size -= 8
            font = ImageFont.truetype(font_path, size)
            lines = _wrap_by_width(draw, title or "AI 新闻", font, max_width)
        line_h = int(size * 1.4)
        start_y = HEIGHT // 2 - len(lines) * line_h // 2 - 60
        for i, line in enumerate(lines):
            draw.text((margin, start_y + i * line_h), line, font=font, fill=(255, 255, 255))

        # 4) 底部来源 + 日期
        small = ImageFont.truetype(font_path, 34)
        draw.text((margin, HEIGHT - 160), "来源: " + source, font=small, fill=(200, 210, 230))
        draw.text((margin, HEIGHT - 110), date_str, font=small, fill=(200, 210, 230))

        # 5) 角标
        badge = ImageFont.truetype(font_path, 36)
        draw.text((margin, 70), "AI NEWS", font=badge, fill=(130, 200, 255))

        Path(out_path).parent.mkdir(parents=True, exist_ok=True)
        img.save(out_path, "PNG")
        return True
    except Exception as e:
        log.warning("封面叠加失败: %s", e)
        return False
