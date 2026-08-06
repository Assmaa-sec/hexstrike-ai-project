"""
Thin, provider-agnostic LLM client (OpenAI-compatible chat completions).

Defaults to the existing PentrAI `llm_proxy` (hooks/llm_proxy.py) so tool calls
keep being logged, but it will talk to any OpenAI-compatible endpoint. Kept
minimal on purpose: the agents build prompts and parse structured output; this
layer just does the HTTP round-trip and retries.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Optional

from ..config import LLMSettings


@dataclass
class LLMResponse:
    text: str
    raw: dict[str, Any]


class LLMClient:
    def __init__(self, settings: LLMSettings):
        self.settings = settings

    def chat(
        self,
        messages: list[dict[str, str]],
        *,
        temperature: float = 0.2,
        tools: Optional[list[dict]] = None,
        response_format: Optional[dict] = None,
    ) -> LLMResponse:
        """POST to `${base_url}/chat/completions` and return the assistant message.

        Implementation notes for later:
          * use `requests` with `self.settings.request_timeout_s`
          * pass `self.settings.model`, temperature, and (when given) `tools` /
            `response_format` straight through — the endpoint is OpenAI-shaped
          * retry idempotently on 5xx / timeout with backoff
        """
        raise NotImplementedError("agents.llm.LLMClient.chat")

    def structured(self, messages: list[dict[str, str]], schema: dict) -> dict:
        """Chat constrained to a JSON schema; return the parsed object.

        Wraps `chat(response_format=...)` and validates the result against `schema`
        so stages get typed data, not free text.
        """
        raise NotImplementedError("agents.llm.LLMClient.structured")
