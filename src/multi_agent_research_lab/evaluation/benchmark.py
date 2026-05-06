"""Benchmark for single-agent vs multi-agent."""

from collections.abc import Callable
from time import perf_counter

from multi_agent_research_lab.core.config import get_settings
from multi_agent_research_lab.core.schemas import BenchmarkMetrics
from multi_agent_research_lab.core.state import ResearchState

Runner = Callable[[str], ResearchState]


# Per-1K-token prices (USD). Update when provider pricing changes.
# Source: provider public pricing pages as of 2025; treat as estimates.
MODEL_PRICES: dict[str, dict[str, float]] = {
    "gpt-4o-mini": {"input": 0.00015, "output": 0.0006},
    "gpt-4o": {"input": 0.0025, "output": 0.01},
    "gpt-4-turbo": {"input": 0.01, "output": 0.03},
    "gpt-3.5-turbo": {"input": 0.0005, "output": 0.0015},
    "gemini-2.0-flash": {"input": 0.000075, "output": 0.0003},
    "gemini-1.5-flash": {"input": 0.000075, "output": 0.0003},
    "gemini-1.5-pro": {"input": 0.00125, "output": 0.005},
}


def _resolve_model() -> str:
    settings = get_settings()
    if settings.openai_api_key:
        return settings.openai_model
    if settings.google_api_key:
        return settings.google_model
    return settings.openai_model


def _estimate_cost(input_tokens: int, output_tokens: int, model: str) -> float | None:
    price = MODEL_PRICES.get(model)
    if price is None:
        return None
    return (input_tokens / 1000.0) * price["input"] + (output_tokens / 1000.0) * price["output"]


def _count_tokens(state: ResearchState) -> tuple[int, int]:
    """Sum input and output tokens from all agent results."""

    total_in = 0
    total_out = 0
    for result in state.agent_results:
        total_in += result.metadata.get("input_tokens", 0) or 0
        total_out += result.metadata.get("output_tokens", 0) or 0
    return total_in, total_out


def _citation_coverage(state: ResearchState) -> float | None:
    """Fraction of sources referenced in final answer (rough heuristic)."""

    if not state.final_answer or not state.sources:
        return None
    referenced = sum(
        1 for i in range(len(state.sources)) if f"[{i + 1}]" in state.final_answer
    )
    return referenced / len(state.sources)


def run_benchmark(run_name: str, query: str, runner: Runner) -> tuple[ResearchState, BenchmarkMetrics]:
    """Measure latency, token cost, citation coverage, and error rate."""

    started = perf_counter()
    state = runner(query)
    latency = perf_counter() - started

    input_tokens, output_tokens = _count_tokens(state)
    total_tokens = input_tokens + output_tokens
    coverage = _citation_coverage(state)

    model = _resolve_model()
    cost = _estimate_cost(input_tokens, output_tokens, model)

    notes_parts: list[str] = []
    notes_parts.append(f"tokens={total_tokens} ({input_tokens}in+{output_tokens}out)")
    if coverage is not None:
        notes_parts.append(f"citation_coverage={coverage:.0%}")
    if state.errors:
        notes_parts.append(f"errors={len(state.errors)}")
    notes_parts.append(f"agents={'→'.join(state.route_history) or 'baseline'}")

    metrics = BenchmarkMetrics(
        run_name=run_name,
        latency_seconds=latency,
        estimated_cost_usd=cost,
        notes="; ".join(notes_parts),
    )
    return state, metrics
