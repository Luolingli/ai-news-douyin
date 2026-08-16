"""敏感内容检测：硬词表 + 引流信号正则（可选 LLM 复核由 pipeline 调）"""
from __future__ import annotations

import re

from .blocklist import CONTACT_PATTERNS, DEFAULT_BLOCKLIST


def check_sensitive(text: str, extra_terms: list[str] | None = None) -> tuple[bool, list[str]]:
    """返回 (是否敏感, 命中项列表)"""
    if not text:
        return False, []
    lower = text.lower()
    hits: list[str] = []
    terms = DEFAULT_BLOCKLIST + list(extra_terms or [])
    for term in terms:
        if term.lower() in lower:
            hits.append(term)
    for pat in CONTACT_PATTERNS:
        if re.search(pat, text):
            hits.append(f"pattern:{pat[:30]}")
    return (len(hits) > 0), hits
