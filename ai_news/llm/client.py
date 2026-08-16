"""DeepSeek 客户端（OpenAI 兼容）"""
from __future__ import annotations

import json
import logging
import time

import requests

log = logging.getLogger("ai_news.llm")

DEFAULT_BASE_URL = "https://api.deepseek.com"


def extract_json(text: str) -> dict | None:
    """从模型输出中提取第一个完整 JSON 对象"""
    t = (text or "").strip()
    t = t.removeprefix("```json").removeprefix("```").removesuffix("```").strip()
    # 找第一对平衡花括号
    start = t.find("{")
    if start == -1:
        return None
    depth = 0
    for i in range(start, len(t)):
        if t[i] == "{":
            depth += 1
        elif t[i] == "}":
            depth -= 1
            if depth == 0:
                try:
                    return json.loads(t[start : i + 1])
                except json.JSONDecodeError:
                    return None
    return None


class LLMClient:
    def __init__(self, api_key: str, base_url: str = DEFAULT_BASE_URL, model: str = "deepseek-chat",
                 temperature: float = 0.4, max_retries: int = 2):
        self.api_key = api_key
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.temperature = temperature
        self.max_retries = max_retries

    @property
    def available(self) -> bool:
        return bool(self.api_key)

    def chat_json(self, system: str, user: str, timeout: int = 90) -> dict:
        url = f"{self.base_url}/chat/completions"
        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            "temperature": self.temperature,
            "response_format": {"type": "json_object"},
        }
        headers = {"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"}
        last_err: Exception | None = None
        for attempt in range(self.max_retries + 1):
            try:
                resp = requests.post(url, json=payload, headers=headers, timeout=timeout)
                if resp.status_code == 429 or resp.status_code >= 500:
                    raise RuntimeError(f"HTTP {resp.status_code}: {resp.text[:200]}")
                resp.raise_for_status()
                data = resp.json()
                content = data["choices"][0]["message"]["content"]
                parsed = extract_json(content)
                if parsed is None:
                    raise RuntimeError(f"JSON 解析失败: {content[:200]}")
                return parsed
            except Exception as e:
                last_err = e
                log.warning("LLM 调用失败(第 %d 次): %s", attempt + 1, e)
                time.sleep(2 * (attempt + 1))
        raise RuntimeError(f"LLM 调用最终失败: {last_err}")
