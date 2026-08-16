"""LLM 客户端（OpenAI 兼容：DeepSeek / ModelScope 等，支持多模型自动切换）"""
from __future__ import annotations

import json
import logging
import time

import requests

log = logging.getLogger("ai_news.llm")

DEFAULT_BASE_URL = "https://api.deepseek.com"
EMPTY_RESPONSE_MSG = "模型空响应（限流/排队），等待后重试或切换模型"


def extract_json(text: str) -> dict | None:
    """从模型输出中提取第一个完整 JSON 对象"""
    t = (text or "").strip()
    t = t.removeprefix("```json").removeprefix("```").removesuffix("```").strip()
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
                 model_fallbacks: list[str] | None = None, temperature: float = 0.4,
                 max_retries: int = 2, backoff_base: float = 5.0):
        self.api_key = api_key
        self.base_url = base_url.rstrip("/")
        self.models = [model] + [m for m in (model_fallbacks or []) if m and m != model]
        self.model = self.models[0]
        self.temperature = temperature
        self.max_retries = max_retries
        self.backoff_base = backoff_base

    @property
    def available(self) -> bool:
        return bool(self.api_key)

    def chat_json(self, system: str, user: str, timeout: int = 90) -> dict:
        """依次尝试模型列表；空响应/限流自动等待重试；参数错误自动降级 json 模式"""
        payload = {
            "model": "__PLACEHOLDER__",
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            "temperature": self.temperature,
        }
        last_err: Exception | None = None
        for idx, model in enumerate(self.models):
            log.info("LLM 尝试模型 %s (%d/%d)", model, idx + 1, len(self.models))
            payload["model"] = model
            try:
                return self._chat_once(payload, json_mode=True, timeout=timeout)
            except Exception as e:
                last_err = e
                if "400" in str(e) or "response_format" in str(e).lower():
                    # 该模型不支持 json 模式 → 降级后继续用同一模型
                    log.warning("response_format 不受支持，降级重试: %s", e)
                    try:
                        return self._chat_once(payload, json_mode=False, timeout=timeout)
                    except Exception as e2:
                        last_err = e2
                log.warning("模型 %s 失败: %s", model, str(last_err)[:150])
                if idx < len(self.models) - 1:
                    time.sleep(self.backoff_base)
        raise RuntimeError(f"LLM 所有模型均失败: {last_err}")

    def _chat_once(self, payload: dict, json_mode: bool, timeout: int) -> dict:
        body = dict(payload)
        if json_mode:
            body["response_format"] = {"type": "json_object"}
        url = f"{self.base_url}/chat/completions"
        headers = {"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"}
        last_err: Exception | None = None
        # 空响应/限流需要更长等待，重试次数多一些
        attempts = max(self.max_retries + 1, 3)
        for attempt in range(attempts):
            try:
                resp = requests.post(url, json=body, headers=headers, timeout=timeout)
                if resp.status_code == 429 or resp.status_code >= 500:
                    raise RuntimeError(f"HTTP {resp.status_code}: {resp.text[:200]}")
                resp.raise_for_status()
                data = resp.json()
                choices = data.get("choices") or []
                if not choices or not choices[0].get("message", {}).get("content"):
                    raise RuntimeError(EMPTY_RESPONSE_MSG)
                content = choices[0]["message"]["content"]
                parsed = extract_json(content)
                if parsed is None:
                    raise RuntimeError(f"JSON 解析失败: {content[:200]}")
                return parsed
            except requests.HTTPError as e:
                code = e.response.status_code if e.response is not None else 0
                if code == 400:
                    raise RuntimeError(f"400 Bad Request: {(e.response.text or '')[:200]}") from e
                raise
            except (KeyError, TypeError, IndexError) as e:
                raise RuntimeError(f"响应结构异常: {e}") from e
            except Exception as e:
                last_err = e
                if attempt >= attempts - 1:
                    break
                wait = self.backoff_base * (2 ** attempt)
                log.warning("LLM 调用失败(第 %d 次)，%.0fs 后重试: %s", attempt + 1, wait, e)
                time.sleep(wait)
        raise RuntimeError(f"LLM 调用失败: {last_err}")
