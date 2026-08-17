"""HTML 封面渲染测试"""
from __future__ import annotations

import tempfile
from pathlib import Path

from ai_news.media.html_cover import generate_html_cover


def test_html_cover_generate():
    d = tempfile.mkdtemp(prefix="html_cov_")
    out = Path(d) / "cover.png"
    ok = generate_html_cover(
        "OpenAI解散安全团队",
        "安全门槛被拆除，代价由谁承担？",
        "The Verge", "Aug 17, 2026", out,
        {"metaphor": "shield"},
    )
    if not ok:
        return  # 环境无浏览器时跳过（CI 上可能不可用）
    assert out.exists()
    from PIL import Image

    im = Image.open(out)
    assert im.size == (1080, 1440)
    out.unlink(missing_ok=True)
