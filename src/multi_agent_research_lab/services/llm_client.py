"""LLM client abstraction.

Production note: agents should depend on this interface instead of importing an SDK directly.
Supports OpenAI and Google Gemini (via OpenAI-compatible endpoint).
"""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass
from typing import Any

from openai import OpenAI
from tenacity import retry, stop_after_attempt, wait_exponential

from multi_agent_research_lab.core.config import get_settings

logger = logging.getLogger(__name__)


def _maybe_wrap_for_langsmith(client: OpenAI) -> Any:
    """Wrap an OpenAI client with LangSmith tracing when LANGSMITH_API_KEY is set.

    `wrap_openai` makes each chat-completion call show up in LangSmith Studio as a
    nested LLM run with the full prompt, response, and token usage — so traces
    contain real content instead of just the meta-attributes our `trace_span`
    context manager records.
    """

    if not os.getenv("LANGSMITH_API_KEY"):
        return client
    try:
        from langsmith.wrappers import wrap_openai

        return wrap_openai(client)
    except Exception as exc:
        logger.warning("wrap_openai failed, continuing without LLM tracing: %s", exc)
        return client


@dataclass(frozen=True)
class LLMResponse:
    content: str
    input_tokens: int | None = None
    output_tokens: int | None = None
    cost_usd: float | None = None


class LLMClient:
    """Provider-agnostic LLM client. Auto-selects Google Gemini or OpenAI based on available keys."""

    def __init__(self) -> None:
        settings = get_settings()

        if settings.openai_api_key:
            raw_client = OpenAI(api_key=settings.openai_api_key)
            self._client = _maybe_wrap_for_langsmith(raw_client)
            self._model = settings.openai_model
            logger.info("LLMClient using OpenAI model=%s", self._model)
        elif settings.google_api_key:
            raw_client = OpenAI(
                api_key=settings.google_api_key,
                base_url="https://generativelanguage.googleapis.com/v1beta/openai/",
            )
            self._client = _maybe_wrap_for_langsmith(raw_client)
            self._model = settings.google_model
            logger.info("LLMClient using Google Gemini model=%s", self._model)
        else:
            raise RuntimeError(
                "No LLM API key found. Set OPENAI_API_KEY or GOOGLE_API_KEY in .env"
            )

    @retry(stop=stop_after_attempt(5), wait=wait_exponential(min=2, max=30))
    def complete(self, system_prompt: str, user_prompt: str) -> LLMResponse:
        """Return a model completion with retry and token logging."""

        response = self._client.chat.completions.create(
            model=self._model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
        )
        choice = response.choices[0]
        usage = response.usage

        input_tokens = usage.prompt_tokens if usage else None
        output_tokens = usage.completion_tokens if usage else None
        logger.info(
            "LLM call model=%s input_tokens=%s output_tokens=%s",
            self._model,
            input_tokens,
            output_tokens,
        )

        return LLMResponse(
            content=choice.message.content or "",
            input_tokens=input_tokens,
            output_tokens=output_tokens,
        )
