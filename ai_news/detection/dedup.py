"""重复检测：URL 精确去重（DB 层）+ 文本语义相似度去重"""
from __future__ import annotations

import difflib
import re

URL_RE = re.compile(r"https?://\S+")
HASH_RE = re.compile(r"#\w+")
PUNCT_RE = re.compile(r"[^\w\u4e00-\u9fff ]+")


def normalize(text: str) -> str:
    t = (text or "").lower()
    t = URL_RE.sub(" ", t)
    t = HASH_RE.sub(" ", t)
    t = PUNCT_RE.sub(" ", t)
    return re.sub(r"\s+", " ", t).strip()


def similarity(a: str, b: str) -> float:
    na, nb = normalize(a), normalize(b)
    if not na or not nb:
        return 0.0
    if na == nb:
        return 1.0
    return difflib.SequenceMatcher(None, na, nb).ratio()


def is_duplicate(text: str, recent_texts: list[str], threshold: float = 0.82) -> tuple[bool, float, str]:
    """与最近已发布内容比较，返回 (是否重复, 最高相似度, 匹配文本片段)"""
    best = 0.0
    best_txt = ""
    for rt in recent_texts or []:
        s = similarity(text, rt)
        if s > best:
            best = s
            best_txt = rt[:60]
    return (best >= threshold), round(best, 3), best_txt
