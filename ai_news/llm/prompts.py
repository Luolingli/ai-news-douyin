"""LLM Prompt 模板与本地降级总结"""
from __future__ import annotations

import re

SYSTEM_PROMPT = (
    "你是一位抖音科技频道《AI 快讯》的主编。你的任务：判断一条新闻素材是否值得发布，并写成适合抖音图文的文案。\n"
    "\n"
    "【发布标准】\n"
    "1. 只保留与人工智能行业直接相关的新闻：模型发布、产品更新、融资并购、研究突破、巨头动态、行业趋势、芯片算力等。\n"
    "2. 剔除：广告、营销、引流、抽奖、个人求助、谣言、惊悚标题党、与 AI 无关的内容。\n"
    "3. 剔除敏感内容：色情低俗、赌博、诈骗、政治敏感、军事敏感、涉及中国法律法规禁止传播的内容。\n"
    "\n"
    "【文案要求】\n"
    "1. 标题：简体中文，20-30 字，有信息量、有吸引力，可带数字和情绪词，不含感叹号堆砌。\n"
    "2. 正文：简体中文，150-350 字，口语化、信息密度高；先讲核心事实，再给背景和影响，最后一句给观点或展望。\n"
    "3. 话题标签：3-5 个，用中文或英文均可，如 #AI #人工智能 #OpenAI #科技。\n"
    "4. 正文里不要出现『据某推文/推特』之类的来源表述，直接陈述事实。\n"
    "\n"
    "【输出】只输出一个 JSON 对象（不要 markdown 代码块），字段：\n"
    "{\"relevant\": true/false, \"sensitive\": true/false, \"reason\": \"判断理由，20字内\", \"title\": \"标题\", \"body\": \"正文\", \"hashtags\": [\"#AI\", ...]}",
)


def build_user_prompt(item) -> str:
    lines = [
        f"来源: {item.get('source','')}",
        f"作者: {item.get('author','')}",
        f"时间: {item.get('published_at','')}",
        f"原文: {item.get('text','')[:2000]}",
    ]
    return "\n".join(lines)


def sanitize_hashtags(tags: list[str], max_tags: int = 5) -> list[str]:
    out = []
    for t in tags or []:
        t = str(t).strip().strip("#").strip()
        if not t:
            continue
        if re.search(r"[!@#$%^&*()+=/]", t):
            continue
        t = re.sub(r"[^\w\u4e00-\u9fff]+", "", t)
        if t and len(t) <= 30 and t not in out:
            out.append(t)
        if len(out) >= max_tags:
            break
    return out


def fallback_summarize(item, max_title_len: int = 30, max_body_len: int = 350) -> dict:
    """未配置 LLM 时的本地降级：直接裁剪原文"""
    text = (item.get("text") or "").strip()
    title = (item.get("title") or "").strip() or text
    title = re.sub(r"\s+", " ", title)[:max_title_len]
    body = text[:max_body_len]
    return {
        "relevant": True,
        "sensitive": False,
        "reason": "本地降级总结（未配置 DeepSeek API Key）",
        "title": title,
        "body": body,
        "hashtags": ["AI", "人工智能", "科技"],
    }
