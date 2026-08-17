"""AI 相关性检测：关键词打分 + 边界值交给 LLM"""
from __future__ import annotations

import re

# 强信号：直接指向 AI 行业主体/技术
STRONG_KEYWORDS = [
    "openai", "anthropic", "google deepmind", "deepmind", "meta ai", "xai", "x ai",
    "hugging face", "huggingface", "stability ai", "midjourney", "runway", "perplexity",
    "chatgpt", "gpt-4", "gpt-5", "gpt-4o", "o1", "o3", "claude", "gemini", "llama",
    "qwen", "deepseek", "kimi", "doubao", "ernie", "grok", "sora", "veo", "whisper",
    "sam altman", "ilya sutskever", "demis hassabis", "dario amodei", "yann lecun",
    "andrew ng", "andrewyng", "karpathy", "fei-fei li", "李飞飞", "奥特曼",
    "大模型", "人工智能", "智能体", "生成式ai", "通用人工智能", "机器学习", "深度学习",
    "神经网络", "transformer", "llm", "agi", "multimodal", "多模态", "diffusion",
    "rag", "fine-tuning", "fine tuning", "rlhf", "量化模型", "开源模型", "本地模型",
    "gpu集群", "ai芯片", "nvidia", "英伟达", "h100", "b200", "a100", "昇腾", "寒武纪",
    "自动驾驶", "robotaxi", "humanoid", "具身智能", "机器人",
    # 用户偏好主题：新模型发布 / 泄露 / benchmark 跑分 / AI数学 / AI金融
    "benchmark", "benchmarks", "mmlu", "gpqa", "humaneval", "swe-bench", "swebench",
    "arena", "elo", "跑分", "基准测试", "得分", "评测", "排名", "榜首",
    "leak", "leaked", "泄露", "权重泄露", "模型泄露", "开源权重",
    "theorem", "定理", "proof", "证明", "olympiad", "奥数", "imo", "math benchmark",
    "数学推理", "quant", "量化交易", "hedge fund", "对冲基金", "fintech", "ai finance",
    "金融大模型", "交易模型", "量化投资",
]

# 弱信号：语境词，与强信号叠加计分
WEAK_KEYWORDS = [
    "ai", "artificial intelligence", "model", "models", "release", "released", "launch",
    "funding", "fundraise", "valuation", "startup", "benchmark", "research paper", "arxiv",
    "paper", "training", "inference", "parameters", "token", "agents", "chatbot",
    "copilot", "assistant", "api", "open source", "opensource", "数据集", "模型发布",
    "融资", "估值", "创业公司", "论文", "算法", "算力", "智能", "自动化", "生成", "数字人",
    "vision pro", "苹果", "apple", "microsoft", "google", "microsoft", "aws", "azure",
    "芯片", "半导体", "算力", "数据中心", "服务器",
]

STRONG_RE = re.compile(r"(?<![a-z0-9])[" + "|".join(re.escape(k) for k in STRONG_KEYWORDS) + r"](?![a-z0-9])", re.I)
WEAK_RE = re.compile(r"(?<![a-z0-9])[" + "|".join(re.escape(k) for k in WEAK_KEYWORDS) + r"](?![a-z0-9])", re.I)


def score_text(text: str, extra_keywords: list[str] | None = None) -> tuple[float, list[str]]:
    """返回 (得分, 命中的关键词)。得分=强词1.0 + 弱词0.4"""
    lower = (text or "").lower()
    hits: list[str] = []
    score = 0.0
    for kw in STRONG_KEYWORDS + (extra_keywords or []):
        if re.search(r"(?<![a-z0-9])" + re.escape(kw.lower()) + r"(?![a-z0-9])", lower):
            score += 1.0
            hits.append(kw)
    for kw in WEAK_KEYWORDS:
        if re.search(r"(?<![a-z0-9])" + re.escape(kw.lower()) + r"(?![a-z0-9])", lower):
            score += 0.4
            hits.append(kw)
    return round(score, 2), hits


def decide(text: str, threshold: float = 0.4, extra_keywords: list[str] | None = None) -> tuple[bool, float, str]:
    """
    返回 (是否通过, 得分, 判定说明):
      score >= threshold        → 通过
      threshold*0.5 <= score < threshold → 边缘，需 LLM 判定（返回 False + need_llm 标记）
      score < threshold*0.5     → 直接丢弃
    """
    score, hits = score_text(text, extra_keywords)
    if score >= threshold:
        return True, score, f"关键词命中({len(hits)}): {', '.join(hits[:6])}"
    if score >= threshold * 0.5:
        return False, score, "边缘分数，需 LLM 判定"
    return False, score, f"与 AI 无关(得分 {score})"
