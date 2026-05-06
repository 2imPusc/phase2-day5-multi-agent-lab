"""Benchmark report rendering."""

from __future__ import annotations

from datetime import datetime, timezone

from multi_agent_research_lab.core.schemas import BenchmarkMetrics


def render_markdown_report(
    metrics: list[BenchmarkMetrics],
    failure_modes: list[dict[str, str]] | None = None,
    trace_links: list[dict[str, str]] | None = None,
) -> str:
    """Render benchmark metrics to markdown.

    Sections produced:
      1. Title + run timestamp
      2. Summary table (latency, cost, quality, notes)
      3. Per-run analysis paragraphs
      4. Failure modes (if provided)
      5. Trace links (if provided)
      6. Conclusion stub
    """

    lines: list[str] = []
    lines.append("# Benchmark Report")
    lines.append("")
    lines.append(f"_Generated: {datetime.now(timezone.utc).isoformat(timespec='seconds')}_")
    lines.append("")

    # Section 1 — Summary table
    lines.append("## 1. Summary")
    lines.append("")
    lines.append("| Run | Latency (s) | Cost (USD) | Quality | Notes |")
    lines.append("|---|---:|---:|---:|---|")
    for item in metrics:
        cost = "" if item.estimated_cost_usd is None else f"{item.estimated_cost_usd:.4f}"
        quality = "" if item.quality_score is None else f"{item.quality_score:.1f}"
        lines.append(
            f"| {item.run_name} | {item.latency_seconds:.2f} | {cost} | {quality} | {item.notes} |"
        )
    lines.append("")

    # Section 2 — Per-run analysis
    lines.append("## 2. Per-run analysis")
    lines.append("")
    if not metrics:
        lines.append("_No runs recorded._")
    else:
        for item in metrics:
            lines.append(f"### {item.run_name}")
            lines.append("")
            lines.append(f"- **Latency:** {item.latency_seconds:.2f}s")
            if item.estimated_cost_usd is not None:
                lines.append(f"- **Estimated cost:** ${item.estimated_cost_usd:.4f}")
            if item.quality_score is not None:
                lines.append(f"- **Quality (peer review 0-10):** {item.quality_score:.1f}")
            lines.append(f"- **Notes:** {item.notes}")
            lines.append("")
    lines.append("")

    # Section 3 — Failure modes
    lines.append("## 3. Failure modes observed")
    lines.append("")
    if not failure_modes:
        lines.append(
            "_No failure modes recorded yet. After running the benchmark, document any "
            "hallucinations, citation gaps, or guardrail breaches here._"
        )
    else:
        for fm in failure_modes:
            lines.append(f"### {fm.get('title', 'Untitled failure mode')}")
            lines.append("")
            if fm.get("where"):
                lines.append(f"- **Where:** {fm['where']}")
            if fm.get("why"):
                lines.append(f"- **Why:** {fm['why']}")
            if fm.get("fix"):
                lines.append(f"- **Fix:** {fm['fix']}")
            lines.append("")
    lines.append("")

    # Section 4 — Trace links
    lines.append("## 4. Trace links")
    lines.append("")
    if not trace_links:
        lines.append(
            "_Paste LangSmith / Langfuse run URLs here after enabling tracing. Example:_"
        )
        lines.append("")
        lines.append("- baseline run: https://smith.langchain.com/...")
        lines.append("- multi-agent run: https://smith.langchain.com/...")
    else:
        for link in trace_links:
            lines.append(f"- **{link.get('label', 'trace')}:** {link.get('url', '')}")
    lines.append("")

    # Section 5 — Conclusion
    lines.append("## 5. Conclusion")
    lines.append("")
    lines.append(
        "_Write a 3-5 sentence summary: when did multi-agent beat the baseline? "
        "When was it overkill? What is the cost / quality trade-off?_"
    )
    lines.append("")

    return "\n".join(lines) + "\n"
