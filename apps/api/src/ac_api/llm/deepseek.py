"""DeepSeek 客户端：OpenAI 兼容，结构化输出带 json 修复与校验重试。"""

from __future__ import annotations

import json
import re
import time
from typing import Any, TypeVar

import httpx
from pydantic import BaseModel, ValidationError
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential_jitter

from ac_api.config import settings
from ac_api.llm.usage import record as record_usage
from ac_api.obs.logger import get_logger
from ac_api.obs.metrics import metrics

log = get_logger("llm")
T = TypeVar("T", bound=BaseModel)
FENCE = re.compile(r"^\s*```(?:json)?\s*|\s*```\s*$")


class LlmUnavailable(Exception):
    pass


class RetryableLlmError(Exception):
    pass


def _strip_fence(text: str) -> str:
    return FENCE.sub("", text.strip())


class DeepSeekClient:
    name = "deepseek"

    def __init__(self) -> None:
        s = settings()
        if not s.deepseek_api_key:
            raise LlmUnavailable("缺少 DEEPSEEK_API_KEY")
        if not s.deepseek_model:
            raise LlmUnavailable("缺少 DEEPSEEK_MODEL（先跑 make preflight 核实 model id）")
        self._base = s.deepseek_base_url.rstrip("/")
        self._key = s.deepseek_api_key
        self._model = s.deepseek_model
        self._timeout = float(load_timeout())

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential_jitter(initial=0.5, max=4),
        retry=retry_if_exception_type(RetryableLlmError),
        reraise=True,
    )
    def _post(self, payload: dict[str, Any]) -> dict[str, Any]:
        headers = {"Authorization": f"Bearer {self._key}", "Content-Type": "application/json"}
        try:
            with httpx.Client(timeout=self._timeout) as client:
                resp = client.post(f"{self._base}/chat/completions", json=payload, headers=headers)
        except httpx.HTTPError as exc:
            raise RetryableLlmError(str(exc)) from exc
        if resp.status_code in (429, 500, 502, 503, 504):
            raise RetryableLlmError(f"HTTP {resp.status_code}: {resp.text[:200]}")
        if resp.status_code >= 400:
            raise LlmUnavailable(f"HTTP {resp.status_code}: {resp.text[:300]}")
        return resp.json()

    def chat(
        self,
        system: str,
        user: str,
        *,
        temperature: float = 0.2,
        max_tokens: int = 1200,
        json_mode: bool = False,
        agent: str = "llm",
        run_id: str | None = None,
    ) -> str:
        payload: dict[str, Any] = {
            "model": self._model,
            "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}],
            "temperature": temperature,
            "max_tokens": max_tokens,
        }
        if json_mode:
            payload["response_format"] = {"type": "json_object"}
            if "json" not in system.lower():
                payload["messages"][0]["content"] = system + "\n\n只输出 JSON。"
        started = time.monotonic()
        data = self._post(payload)
        latency = int((time.monotonic() - started) * 1000)
        usage = data.get("usage", {})
        record_usage(agent, int(usage.get("prompt_tokens", 0)), int(usage.get("completion_tokens", 0)), latency, run_id)
        metrics.inc("llm_calls_total", {"agent": agent, "status": "ok"})
        metrics.inc("llm_tokens_total", {"agent": agent, "kind": "prompt"}, usage.get("prompt_tokens", 0))
        metrics.inc("llm_tokens_total", {"agent": agent, "kind": "completion"}, usage.get("completion_tokens", 0))
        choices = data.get("choices") or []
        if not choices:
            raise LlmUnavailable("响应里没有 choices")
        return choices[0]["message"].get("content") or ""

    def json(
        self,
        system: str,
        user: str,
        schema: type[T],
        *,
        temperature: float = 0.2,
        max_tokens: int = 1200,
        agent: str = "llm",
        run_id: str | None = None,
    ) -> dict[str, Any]:
        for attempt in range(2):
            content = self.chat(
                system,
                user,
                temperature=temperature if attempt == 0 else 0.0,
                max_tokens=max_tokens,
                json_mode=True,
                agent=agent,
                run_id=run_id,
            )
            if not content.strip():
                log.info("llm_empty_content", extra={"data": {"agent": agent, "attempt": attempt}})
                continue
            try:
                parsed = json.loads(_strip_fence(content))
                schema.model_validate(parsed)
                return parsed
            except (json.JSONDecodeError, ValidationError) as exc:
                metrics.inc("llm_json_repair_total", {"agent": agent})
                log.info("llm_json_repair", extra={"data": {"error": str(exc)[:200], "attempt": attempt}})
        raise LlmUnavailable("结构化输出连续两次不可解析")


def load_timeout() -> float:
    from ac_api.config import load_config

    return float(load_config().providers.get("llm", {}).get("timeout_s", 60))
