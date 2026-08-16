"""封面生成测试"""
from __future__ import annotations

from pathlib import Path

from ai_news.media import generate_cover


def test_cover_generate():
    out = Path(__file__).parent / "tmp_cover.png"
    ok = generate_cover("OpenAI 发布 GPT-5，推理能力大幅提升", "OpenAI", "2025-06-01", out,
                        {"gradient": ["#0f2027", "#203a43", "#2c5364"], "font_size": 72})
    assert ok, "封面生成失败（检查 Pillow 与中文字体）"
    assert out.exists()
    assert out.stat().st_size > 1000
    from PIL import Image

    im = Image.open(out)
    assert im.size == (1080, 1440)
    out.unlink(missing_ok=True)
