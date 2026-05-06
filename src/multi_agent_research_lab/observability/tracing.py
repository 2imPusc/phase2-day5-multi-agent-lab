"""Tracing hooks.

Supports LangSmith when LANGSMITH_API_KEY is set; otherwise falls back to
in-memory spans. This avoids hard-binding to one provider while still letting
students see real traces in LangSmith Studio.

Each `trace_span` becomes a parent run on LangSmith. While the span is open,
LangSmith's tracing context is set so that any `wrap_openai`-instrumented LLM
call inside the block is automatically attached as a nested child run with the
full prompt, response, and token usage.
"""

from __future__ import annotations

import atexit
import logging
import os
from collections.abc import Iterator
from contextlib import contextmanager, nullcontext
from time import perf_counter
from typing import Any

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

    Yields an in-memory span dict so callers can record additional outputs.
    Any `attributes` mutated inside the block are sent as the run's outputs
    when the span closes. LLM calls made via a `wrap_openai`-instrumented
    client will appear as nested child runs.
    """

    started = perf_counter()
    initial_attrs = dict(attributes or {})
    span: dict[str, Any] = {
        "name": name,
        "attributes": dict(initial_attrs),
        "duration_seconds": None,
    }

    client = _get_langsmith_client()
    project = os.getenv("LANGSMITH_PROJECT", "multi-agent-research-lab")
    run_tree = None
    parent_ctx: Any = nullcontext()

    if client is not None:
        try:
            from langsmith.run_helpers import tracing_context
            from langsmith.run_trees import RunTree

            run_tree = RunTree(
                name=name,
                run_type="chain",
                inputs=initial_attrs,
                project_name=project,
                client=client,
            )
            run_tree.post()
            parent_ctx = tracing_context(parent=run_tree, client=client, project_name=project)
        except Exception as exc:
            logger.warning("LangSmith RunTree init failed: %s", exc)
            run_tree = None
            parent_ctx = nullcontext()

    error: BaseException | None = None
    try:
        with parent_ctx:
            try:
                yield span
            except BaseException as exc:
                error = exc
                raise
    finally:
        span["duration_seconds"] = perf_counter() - started
        if run_tree is not None:
            try:
                outputs = None if error else dict(span["attributes"])
                run_tree.end(outputs=outputs, error=repr(error) if error else None)
                run_tree.patch()
            except Exception as exc:
                logger.warning("LangSmith RunTree patch failed: %s", exc)
