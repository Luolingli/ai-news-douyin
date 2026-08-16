"""LLM Prompt 模板与本地降级总结"""
from __future__ import annotations

import re

SYSTEM_PROMPT = (
    "你是一位抖音科技频道《AI 快讯》的主编。任务：判断新闻素材是否值得发布，并写成适合抖音图文的详细文案。\n"
    "\n"
    "【发布标准】\n"
    "1. 只保留与人工智能行业直接相关的新闻：模型发布、产品更新、融资并购、研究突破、巨头动态、行业趋势、芯片算力等。\n"
    "2. 剔除：广告、营销、引流、抽奖、个人求助、谣言、惊悚标题党、与 AI 无关的内容。\n"
    "3. 剔除敏感内容：色情低俗、赌博、诈骗、政治敏感、军事敏感、涉及中国法律法规禁止传播的内容。\n"
    "\n"
    "【标题要求】\n"
    "1. 简体中文，15-18 字（硬上限 20 字含空格，宁短勿超），有信息量、有吸引力，可带数字。\n"
    "\n"
    "【正文要求】（核心：低频率发布，必须有深度和广度，拒绝空话套话）\n"
    "1. 简体中文，600-800 字（抖音图文正文上限约 1000 字）。\n"
    "2. 必须包含具体事实：时间、主体名称、产品/模型名称、关键数字（参数量、性能提升幅度、价格、融资额、发布时间等）。\n"
    "3. 深度：交代事件来龙去脉（起因、经过、现状）；引用原文的技术细节与数据；涉及公司时补充背景（成立时间、代表产品、市场地位）。\n"
    "4. 广度：补充行业背景（竞品动态、上下游影响、对开发者/企业/普通用户的意义），适当关联近期相关事件。\n"
    "5. 结构：开头一句核心事实（何时、谁、做了什么）→ 2-3 段细节与背景展开 → 行业意义或展望收尾。\n"
    "6. 禁止：只重复标题的意思；空洞形容词堆砌（重大突破、震撼发布、颠覆性）；没有信息量的口水话。\n"
    "5. 话题标签 3-5 个，如 #AI #人工智能 #OpenAI #科技。\n"
    "\n"
    "【输出】只输出一个 JSON 对象（不要 markdown 代码块），字段：\n"
    "{\"relevant\": true/false, \"sensitive\": true/false, \"reason\": \"判断理由，20字内\", \"title\": \"标题\", \"body\": \"正文\", \"hashtags\": [\"#AI\", ...]}"
)


def build_user_prompt(item, article: str = "") -> str:
    lines = [
        f"来源: {item.get('source','')}",
        f"作者: {item.get('author','')}",
        f"时间: {item.get('published_at','')}",
        f"原文: {item.get('text','')[:2000]}",
    ]
    if article:
        lines.append(f"文章正文: {article[:8000]}")
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


def fallback_summarize(item, max_title_len: int = 20, max_body_len: int = 500) -> dict:
    """未配置 LLM 时的本地降级：直接裁剪原文"""
    text = (item.get("text") or "").strip()
    title = (item.get("title") or "").strip() or text
    title = re.sub(r"\s+", " ", title)[:max_title_len]
    body = text[:max_body_len]
    return {
        "relevant": True,
        "sensitive": False,
        "reason": "本地降级总结（未配置 LLM API Key）",
        "title": title,
        "body": body,
        "hashtags": ["AI", "人工智能", "科技"],
    }
