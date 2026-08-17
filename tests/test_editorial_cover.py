"""编辑级封面测试"""
from __future__ import annotations

import tempfile
from pathlib import Path

from ai_news.media.editorial_cover import generate_editorial_cover, metaphor_for


def test_metaphor_mapping():
    assert metaphor_for("OpenAI 解散风险评估团队 引发安全担忧") == "shield"
    assert metaphor_for("NVIDIA 发布新一代 GPU 芯片 算力翻倍") == "streams"
    assert metaphor_for("OpenAI 发布 GPT-5 新模型 推理能力提升") == "nodes"
    assert metaphor_for("今天天气不错") == "grid"


def test_editorial_cover_generate():
    d = tempfile.mkdtemp(prefix="ed_")
    out = Path(d) / "cover.png"
    ok = generate_editorial_cover(
        "OpenAI解散风险评估团队 引发安全",
        "安全门槛被拆除，代价由谁承担？",
        "The Verge", "2026-08-17", out,
        {"font_size": 68}, metaphor_text="OpenAI 解散风险评估团队 引发安全担忧",
    )
    assert ok, "编辑封面生成失败（检查字体/依赖）"
    assert out.exists()
    from PIL import Image

    im = Image.open(out)
    assert im.size == (1080, 1440)
    assert im.getpixel((100, 100)) != im.getpixel((900, 1300)), "背景应有渐变差异"
    out.unlink(missing_ok=True)
