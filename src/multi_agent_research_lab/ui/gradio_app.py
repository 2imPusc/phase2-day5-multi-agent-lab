"""Gradio chat UI for testing the multi-agent research lab interactively.

Run:
    python -m multi_agent_research_lab.ui.gradio_app
"""

from __future__ import annotations

import logging
from time import perf_counter

import gradio as gr

from multi_agent_research_lab.core.config import get_settings
from multi_agent_research_lab.core.errors import StudentTodoError
from multi_agent_research_lab.core.schemas import AgentName, AgentResult, ResearchQuery
from multi_agent_research_lab.core.state import ResearchState
from multi_agent_research_lab.evaluation.benchmark import (
    MODEL_PRICES,
    _estimate_cost,
    _resolve_model,
)
from multi_agent_research_lab.graph.workflow import MultiAgentWorkflow
from multi_agent_research_lab.observability.logging import configure_logging
from multi_agent_research_lab.services.llm_client import LLMClient

logger = logging.getLogger(__name__)


def _baseline_runner(query: str) -> ResearchState:
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
    state = ResearchState(request=ResearchQuery(query=query))
    return MultiAgentWorkflow().run(state)


def _sum_tokens(state: ResearchState) -> tuple[int, int]:
    in_tok = sum((r.metadata.get("input_tokens") or 0) for r in state.agent_results)
    out_tok = sum((r.metadata.get("output_tokens") or 0) for r in state.agent_results)
    return in_tok, out_tok


def _format_metrics(state: ResearchState, latency: float) -> str:
    in_tok, out_tok = _sum_tokens(state)
    model = _resolve_model()
    cost = _estimate_cost(in_tok, out_tok, model)
    cost_str = f"${cost:.4f}" if cost is not None else "—"

    route = " → ".join(state.route_history) if state.route_history else "baseline (single LLM call)"
    n_agents = len({r.agent.value for r in state.agent_results})

    rows = [
        "### Run details",
        "",
        f"- **Latency:** `{latency:.2f}s`",
        f"- **Tokens:** `{in_tok}` in + `{out_tok}` out = `{in_tok + out_tok}` total",
        f"- **Model:** `{model}`",
        f"- **Estimated cost:** `{cost_str}`",
        f"- **Iterations:** `{state.iteration}`",
        f"- **Distinct agents:** `{n_agents}`",
        f"- **Route:** {route}",
    ]
    if state.errors:
        rows.append(f"- **Errors:** `{len(state.errors)}` — {state.errors[0]}")
    return "\n".join(rows)


def _format_sources(state: ResearchState) -> str:
    if not state.sources:
        return "_No sources fetched (baseline mode does not search)._"
    lines = ["### Sources", ""]
    for i, s in enumerate(state.sources, start=1):
        url = f" — [{s.url}]({s.url})" if s.url else ""
        lines.append(f"**[{i}] {s.title}**{url}")
        if s.snippet:
            lines.append(f"> {s.snippet[:240]}{'…' if len(s.snippet) > 240 else ''}")
        lines.append("")
    return "\n".join(lines)


def _format_agent_breakdown(state: ResearchState) -> str:
    if not state.agent_results:
        return "_No agent results recorded._"
    lines = ["### Agent breakdown", "", "| # | Agent | Tokens (in→out) | Preview |", "|---:|---|---|---|"]
    for i, r in enumerate(state.agent_results, start=1):
        in_t = r.metadata.get("input_tokens") or 0
        out_t = r.metadata.get("output_tokens") or 0
        preview = (r.content or "").replace("\n", " ")[:80]
        lines.append(f"| {i} | `{r.agent.value}` | {in_t}→{out_t} | {preview}{'…' if len(r.content or '') > 80 else ''} |")
    return "\n".join(lines)


def _langsmith_hint() -> str:
    settings = get_settings()
    if settings.langsmith_api_key:
        project = settings.langsmith_project
        return (
            f"### Trace\n\n"
            f"LangSmith is enabled (project `{project}`). "
            f"Open [smith.langchain.com](https://smith.langchain.com/) → projects → `{project}` "
            f"to see live spans for this run."
        )
    return (
        "### Trace\n\n"
        "_LangSmith not configured. Set `LANGSMITH_API_KEY` in `.env` to log traces._"
    )


def respond(
    message: str,
    history: list[dict[str, str]],
    mode: str,
) -> tuple[list[dict[str, str]], str, str, str, str]:
    """Single-turn handler. Returns (chatbot_history, metrics_md, agent_md, sources_md, trace_md)."""

    if not message or not message.strip():
        return history, "_Type a query and click Send._", "", "", _langsmith_hint()

    history = (history or []) + [{"role": "user", "content": message}]
    runner = _baseline_runner if mode == "baseline" else _multi_runner

    started = perf_counter()
    try:
        state = runner(message)
    except StudentTodoError as exc:
        history.append({"role": "assistant", "content": f"⚠️ Unimplemented: {exc}"})
        return history, f"_StudentTodoError: {exc}_", "", "", _langsmith_hint()
    except Exception as exc:  # pragma: no cover — UI guard
        logger.exception("UI run failed")
        history.append({"role": "assistant", "content": f"❌ Error: {exc}"})
        return history, f"_Error: {exc}_", "", "", _langsmith_hint()

    latency = perf_counter() - started
    answer = state.final_answer or "_(no answer produced)_"
    history.append({"role": "assistant", "content": answer})

    return (
        history,
        _format_metrics(state, latency),
        _format_agent_breakdown(state),
        _format_sources(state),
        _langsmith_hint(),
    )


def build_demo() -> gr.Blocks:
    with gr.Blocks(title="Multi-Agent Research Lab") as demo:
        gr.Markdown(
            "# Multi-Agent Research Lab\n"
            "Compare the **single-agent baseline** and the **multi-agent workflow** "
            "(supervisor → researcher → analyst → writer → critic) live."
        )

        with gr.Row():
            with gr.Column(scale=3):
                mode = gr.Radio(
                    choices=["multi-agent", "baseline"],
                    value="multi-agent",
                    label="Mode",
                    info="`multi-agent` runs the full graph; `baseline` is a single LLM call.",
                )
                chatbot = gr.Chatbot(
                    height=500,
                    label="Conversation",
                )
                msg = gr.Textbox(
                    placeholder="e.g. Research GraphRAG state-of-the-art and write a 500-word summary",
                    label="Your research query",
                    lines=2,
                )
                with gr.Row():
                    send = gr.Button("Send", variant="primary")
                    clear = gr.Button("Clear", variant="secondary")

            with gr.Column(scale=2):
                metrics_md = gr.Markdown("_no run yet_")
                agents_md = gr.Markdown()
                sources_md = gr.Markdown()
                trace_md = gr.Markdown(_langsmith_hint())

        outputs = [chatbot, metrics_md, agents_md, sources_md, trace_md]
        send.click(respond, inputs=[msg, chatbot, mode], outputs=outputs).then(
            lambda: "", None, msg
        )
        msg.submit(respond, inputs=[msg, chatbot, mode], outputs=outputs).then(
            lambda: "", None, msg
        )
        clear.click(
            lambda: ([], "_no run yet_", "", "", _langsmith_hint()),
            outputs=outputs,
        )

        gr.Markdown(
            "---\n"
            "**Pricing note:** estimated cost uses the per-1K-token table in "
            "`evaluation/benchmark.py:MODEL_PRICES` "
            f"(currently {len(MODEL_PRICES)} models tracked). "
            "Treat as rough estimate."
        )

    return demo


def main() -> None:
    configure_logging(get_settings().log_level)
    demo = build_demo()
    demo.queue().launch(
        server_name="127.0.0.1",
        server_port=7860,
        show_error=True,
        theme=gr.themes.Soft(),
    )


if __name__ == "__main__":
    main()
