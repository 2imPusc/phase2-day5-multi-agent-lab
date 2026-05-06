"""Tracing hooks.

Supports LangSmith when LANGSMITH_API_KEY is set; otherwise falls back to
in-memory spans. This avoids hard-binding to one provider while still letting
students see real traces in LangSmith Studio.
"""

from __future__ import annotations

import atexit
import logging
import os
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import datetime, timezone
from time import perf_counter
from typing import Any
from uuid import uuid4

logger = logging.getLogger(__name__)

_client: Any | None = None
_client_initialised = False


def _langsmith_enabled() -> bool:
    return bool(os.getenv("LANGSMITH_API_KEY"))


def _get_langsmith_client() -> Any | None:
    """Return a singleton LangSmith Client (so its background queue is shared)."""
    global _client, _client_initialised
    if _client_initialised:
        return _client
    _client_initialised = True
    if not _langsmith_enabled():
        return None
    try:
        from langsmith import Client

        _client = Client()
        # Make sure pending runs flush before the process exits.
        atexit.register(_flush_client)
    except Exception as exc:
        logger.warning("LangSmith client unavailable: %s", exc)
        _client = None
    return _client


def _flush_client() -> None:
    if _client is None:
        return
    try:
        flush = getattr(_client, "flush", None)
        if callable(flush):
            flush()
    except Exception as exc:
        logger.warning("LangSmith flush failed: %s", exc)


@contextmanager
def trace_span(name: str, attributes: dict[str, Any] | None = None) -> Iterator[dict[str, Any]]:
    """Span context that emits to LangSmith when configured.

    Always yields an in-memory span dict so callers can attach attributes; the
    LangSmith run is created/closed in parallel when an API key is present.
    """

    started = perf_counter()
    start_time = datetime.now(timezone.utc)
    span: dict[str, Any] = {"name": name, "attributes": attributes or {}, "duration_seconds": None}

    client = _get_langsmith_client()
    run_id = None
    project = os.getenv("LANGSMITH_PROJECT", "multi-agent-research-lab")
    if client is not None:
        try:
            run_id = uuid4()
            client.create_run(
                name=name,
                run_type="chain",
                inputs=dict(span["attributes"]),
                project_name=project,
                id=run_id,
                start_time=start_time,
            )
        except Exception as exc:
            logger.warning("LangSmith create_run failed: %s", exc)
            run_id = None

    error: BaseException | None = None
    try:
        yield span
    except BaseException as exc:
        error = exc
        raise
    finally:
        span["duration_seconds"] = perf_counter() - started
        end_time = datetime.now(timezone.utc)
        if client is not None and run_id is not None:
            try:
                client.update_run(
                    run_id=run_id,
                    outputs=None if error else {"attributes": dict(span["attributes"])},
                    end_time=end_time,
                    error=repr(error) if error else None,
                )
            except Exception as exc:
                logger.warning("LangSmith update_run failed: %s", exc)
