"""LLM 客户端：官方 openai SDK + 多模型回退 + 空响应重试（参考 Fudan_iCourse_Subscriber 的鲁棒性设计）"""
from __future__ import annotations

import json
import logging
import time

from openai import OpenAI

log = logging.getLogger("ai_news.llm")

DEFAULT_BASE_URL = "https://api.deepseek.com"


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


class EmptyResponseError(RuntimeError):
    """HTTP 200 但 choices 为空（ModelScope 免费档限流/排队特征）"""


class LLMClient:
    """
    多模型自动回退：依次尝试 models 列表，全部失败抛 RuntimeError。
    - 官方 openai SDK：连接超时/429/5xx 自动重试（max_retries 次，指数退避）
    - 空响应（choices 为空）：手动指数退避重试（SDK 不会处理这种情况）
    - response_format 不受支持（400）：自动降级为不带 json 模式的请求
    """

    def __init__(self, api_key: str, base_url: str = DEFAULT_BASE_URL, model: str = "deepseek-chat",
                 model_fallbacks: list[str] | None = None, temperature: float = 0.4,
                 max_retries: int = 3, backoff_base: float = 5.0, timeout: int = 180):
        self.api_key = api_key
        self.base_url = base_url.rstrip("/")
        self.models = [model] + [m for m in (model_fallbacks or []) if m and m != model]
        self.model = self.models[0]
        self.temperature = temperature
        self.max_retries = max_retries
        self.backoff_base = backoff_base
        self.timeout = timeout
        # 无 key 时不构造客户端（SDK 会拒绝空 key），available=False 走本地降级
        self._client = (
            OpenAI(api_key=api_key, base_url=self.base_url, timeout=timeout, max_retries=max_retries)
            if api_key
            else None
        )

    @property
    def available(self) -> bool:
        return bool(self.api_key)

    def chat_json(self, system: str, user: str, timeout: int | None = None) -> dict:
        """依次尝试模型列表；空响应/限流自动等待重试；参数错误自动降级 json 模式"""
        if not self.available:
            raise RuntimeError("未配置 LLM API key（DEEPSEEK_API_KEY）")
        payload = {
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            "temperature": self.temperature,
        }
        timeout = timeout or self.timeout
        last_err: Exception | None = None
        for idx, model in enumerate(self.models):
            log.info("LLM 尝试模型 %s (%d/%d)", model, idx + 1, len(self.models))
            try:
                return self._call_model(model, payload, json_mode=True, timeout=timeout)
            except Exception as e:
                last_err = e
                if "400" in str(e) or "response_format" in str(e).lower():
                    log.warning("response_format 不受支持，降级重试: %s", str(e)[:120])
                    try:
                        return self._call_model(model, payload, json_mode=False, timeout=timeout)
                    except Exception as e2:
                        last_err = e2
                log.warning("模型 %s 失败: %s", model, str(last_err)[:150])
                if idx < len(self.models) - 1:
                    time.sleep(self.backoff_base)
        raise RuntimeError(f"LLM 所有模型均失败: {last_err}")

    def _call_model(self, model: str, payload: dict, json_mode: bool, timeout: int) -> dict:
        kwargs: dict = {
            "model": model,
            "messages": payload["messages"],
            "temperature": payload["temperature"],
            "timeout": timeout,
        }
        if json_mode:
            kwargs["response_format"] = {"type": "json_object"}
        # 空响应（HTTP 200 + choices=null）SDK 不会重试，这里手动退避
        attempts = 3
        for attempt in range(attempts):
            try:
                resp = self._client.chat.completions.create(**kwargs)
            except Exception as e:
                # openai.BadRequestError(400) / APIConnectionError / RateLimitError 等
                # 除 400 外 SDK 已按 max_retries 内部重试过，直接抛给上层切模型
                raise RuntimeError(f"{type(e).__name__}: {str(e)[:200]}") from e
            choices = resp.choices or []
            content = (choices[0].message.content or "").strip() if choices else ""
            if not content:
                if attempt >= attempts - 1:
                    raise EmptyResponseError("模型空响应（限流/排队）")
                wait = self.backoff_base * (2 ** attempt)
                log.warning("空响应(第 %d 次)，%.0fs 后重试: %s", attempt + 1, wait, model)
                time.sleep(wait)
                continue
            parsed = extract_json(content)
            if parsed is None:
                raise RuntimeError(f"JSON 解析失败: {content[:200]}")
            return parsed
        raise EmptyResponseError("模型空响应（限流/排队）")
