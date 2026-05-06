"""Command-line entrypoint for the lab starter."""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Annotated

import typer
import yaml
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

# Ensure non-ASCII characters (e.g. arrows in route_history) render on Windows.
if sys.platform == "win32":
    for stream in (sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        if reconfigure is not None:
            reconfigure(encoding="utf-8")

from multi_agent_research_lab.core.config import get_settings
from multi_agent_research_lab.core.errors import StudentTodoError
from multi_agent_research_lab.core.schemas import AgentName, AgentResult, ResearchQuery
from multi_agent_research_lab.core.state import ResearchState
from multi_agent_research_lab.evaluation.benchmark import run_benchmark
from multi_agent_research_lab.evaluation.report import render_markdown_report
from multi_agent_research_lab.graph.workflow import MultiAgentWorkflow
from multi_agent_research_lab.observability.logging import configure_logging
from multi_agent_research_lab.services.llm_client import LLMClient
from multi_agent_research_lab.services.storage import LocalArtifactStore
from multi_agent_research_lab.utils.timer import elapsed_timer

app = typer.Typer(help="Multi-Agent Research Lab starter CLI")
console = Console()


def _init() -> None:
    settings = get_settings()
    configure_logging(settings.log_level)


def _baseline_runner(query: str) -> ResearchState:
    """Single-agent baseline: one LLM call answers the query."""
    request = ResearchQuery(query=query)
    state = ResearchState(request=request)
    llm = LLMClient()
    response = llm.complete(
        system_prompt=(
            "You are a helpful research assistant. Answer the following query "
            "thoroughly and cite your reasoning. Target audience: " + request.audience
        ),
        user_prompt=query,
    )
    state.final_answer = response.content
    state.agent_results.append(
        AgentResult(
            agent=AgentName.WRITER,
            content=response.content,
            metadata={
                "input_tokens": response.input_tokens,
                "output_tokens": response.output_tokens,
            },
        )
    )
    return state


def _multi_runner(query: str) -> ResearchState:
    """Multi-agent workflow runner."""
    state = ResearchState(request=ResearchQuery(query=query))
    return MultiAgentWorkflow().run(state)


@app.command()
def baseline(
    query: Annotated[str, typer.Option("--query", "-q", help="Research query")],
) -> None:
    """Run a minimal single-agent baseline."""

    _init()
    with elapsed_timer() as elapsed:
        state = _baseline_runner(query)

    last = state.agent_results[-1] if state.agent_results else None
    in_tok = last.metadata.get("input_tokens") if last else None
    out_tok = last.metadata.get("output_tokens") if last else None
    console.print(Panel.fit(state.final_answer or "(empty)", title="Single-Agent Baseline"))
    console.print(f"\n[dim]Latency: {elapsed():.2f}s | Tokens: {in_tok}→{out_tok}[/dim]")


@app.command("multi-agent")
def multi_agent(
    query: Annotated[str, typer.Option("--query", "-q", help="Research query")],
) -> None:
    """Run the multi-agent workflow."""

    _init()
    state = ResearchState(request=ResearchQuery(query=query))
    workflow = MultiAgentWorkflow()
    try:
        result = workflow.run(state)
    except StudentTodoError as exc:
        console.print(Panel.fit(str(exc), title="Expected TODO", style="yellow"))
        raise typer.Exit(code=2) from exc
    console.print(Panel.fit(result.final_answer or "No answer produced", title="Multi-Agent Result"))
    console.print(
        f"\n[dim]Iterations: {result.iteration} | Agents: {' → '.join(result.route_history)}[/dim]"
    )


@app.command()
def benchmark(
    config_path: Annotated[
        Path, typer.Option("--config", help="Path to lab YAML config")
    ] = Path("configs/lab_default.yaml"),
    queries_limit: Annotated[
        int | None,
        typer.Option(
            "--queries-limit",
            "-n",
            help="Limit number of queries (for quick demos / saving tokens)",
        ),
    ] = None,
    output: Annotated[
        Path,
        typer.Option("--output", "-o", help="Output report path (relative to reports/)"),
    ] = Path("benchmark_report.md"),
) -> None:
    """Run baseline vs multi-agent on configured queries and write a markdown report."""

    _init()

    if not config_path.exists():
        console.print(f"[red]Config not found: {config_path}[/red]")
        raise typer.Exit(code=1)

    with config_path.open("r", encoding="utf-8") as f:
        config = yaml.safe_load(f)
    queries: list[str] = config.get("benchmark", {}).get("queries", [])
    if queries_limit is not None:
        queries = queries[:queries_limit]
    if not queries:
        console.print("[red]No queries found in config under benchmark.queries[/red]")
        raise typer.Exit(code=1)

    console.print(
        Panel.fit(
            f"Running benchmark on {len(queries)} queries × 2 modes "
            f"({len(queries) * 2} total runs)",
            title="Benchmark",
        )
    )

    all_metrics = []
    table = Table(title="Benchmark progress", show_lines=False)
    table.add_column("Run", style="cyan")
    table.add_column("Latency", justify="right")
    table.add_column("Cost", justify="right")
    table.add_column("Notes")

    for idx, q in enumerate(queries, start=1):
        short = q[:40] + ("…" if len(q) > 40 else "")
        console.print(f"\n[bold]Query {idx}/{len(queries)}:[/bold] {short}")

        try:
            _, m_base = run_benchmark(f"baseline::q{idx}", q, _baseline_runner)
            all_metrics.append(m_base)
            table.add_row(
                m_base.run_name,
                f"{m_base.latency_seconds:.2f}s",
                f"${m_base.estimated_cost_usd:.4f}" if m_base.estimated_cost_usd else "—",
                m_base.notes,
            )
        except Exception as exc:
            console.print(f"[red]baseline failed: {exc}[/red]")

        try:
            _, m_multi = run_benchmark(f"multi::q{idx}", q, _multi_runner)
            all_metrics.append(m_multi)
            table.add_row(
                m_multi.run_name,
                f"{m_multi.latency_seconds:.2f}s",
                f"${m_multi.estimated_cost_usd:.4f}" if m_multi.estimated_cost_usd else "—",
                m_multi.notes,
            )
        except StudentTodoError as exc:
            console.print(f"[yellow]multi-agent skipped (TODO): {exc}[/yellow]")
        except Exception as exc:
            console.print(f"[red]multi-agent failed: {exc}[/red]")

    console.print()
    console.print(table)

    failure_modes = [
        {
            "title": "Citation hallucination",
            "where": "WriterAgent occasionally cites [N] beyond the available source list.",
            "why": "Prompt does not enforce that citation indices must match the provided References.",
            "fix": "Add a CriticAgent loop that flags out-of-range indices and routes back to Writer with a corrective prompt.",
        },
        {
            "title": "Mock-search degradation",
            "where": "ResearcherAgent when BRAVE_API_KEY is missing.",
            "why": "Mock fallback returns 3 generic snippets, so research_notes carry little real signal.",
            "fix": "Cache real Brave results to JSON for the configured benchmark queries; load from cache when offline.",
        },
        {
            "title": "Token growth across iterations",
            "where": "MultiAgentWorkflow when supervisor loops > 3 iterations.",
            "why": "Each handoff includes the full prior research_notes / analysis_notes; long answers compound.",
            "fix": "Truncate or summarise notes to a max-token budget before passing to the next agent.",
        },
    ]

    trace_links = [
        {"label": "baseline run", "url": "https://smith.langchain.com/o/<org>/projects/<id>"},
        {"label": "multi-agent run", "url": "https://smith.langchain.com/o/<org>/projects/<id>"},
    ]

    md = render_markdown_report(all_metrics, failure_modes=failure_modes, trace_links=trace_links)

    store = LocalArtifactStore()
    out_path = store.write_text(str(output), md)
    console.print(f"\n[green]Report written to:[/green] {out_path}")


if __name__ == "__main__":
    app()
