"""Tracing hooks.

Supports LangSmith when LANGSMITH_API_KEY is set; otherwise falls back to
in-memory spans. This avoids hard-binding to one provider while still letting
students see real traces in LangSmith Studio.
"""

from __future__ import annotations

import logging
import os
from collections.abc import Iterator
from contextlib import contextmanager
from time import perf_counter
from typing import Any

logger = logging.getLogger(__name__)


def _langsmith_enabled() -> bool:
    return bool(os.getenv("LANGSMITH_API_KEY"))


def _get_langsmith_client() -> Any | None:
    if not _langsmith_enabled():
        return None
    try:
        from langsmith import Client

        return Client()
    except Exception as exc:
        logger.warning("LangSmith client unavailable: %s", exc)
        return None


@contextmanager
def trace_span(name: str, attributes: dict[str, Any] | None = None) -> Iterator[dict[str, Any]]:
    """Span context that emits to LangSmith when configured.

    Always yields an in-memory span dict so callers can attach attributes; the
    LangSmith run is created/closed in parallel when an API key is present.
    """

    started = perf_counter()
    span: dict[str, Any] = {"name": name, "attributes": attributes or {}, "duration_seconds": None}

    client = _get_langsmith_client()
    run_id = None
    project = os.getenv("LANGSMITH_PROJECT", "multi-agent-research-lab")
    if client is not None:
        try:
            from uuid import uuid4

            run_id = uuid4()
            client.create_run(
                name=name,
                run_type="chain",
                inputs=span["attributes"],
                project_name=project,
                id=run_id,
            )
        except Exception as exc:
            logger.warning("LangSmith create_run failed: %s", exc)
            run_id = None

    try:
        yield span
    finally:
        span["duration_seconds"] = perf_counter() - started
        if client is not None and run_id is not None:
            try:
                client.update_run(
                    run_id=run_id,
                    outputs={"attributes": span["attributes"]},
                    end_time=None,
                )
            except Exception as exc:
                logger.warning("LangSmith update_run failed: %s", exc)
