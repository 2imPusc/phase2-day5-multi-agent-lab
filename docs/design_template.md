# Design Document

## Problem

Build a research assistant that, given a long-form query, produces a well-cited
written answer for a technical audience. The system must:

- Accept a free-form research query.
- Retrieve relevant external sources.
- Synthesise sources into research notes.
- Analyse claims, evidence quality, and gaps.
- Produce a final answer with bracket-style citations and a References section.

## Why multi-agent?

A single agent can answer trivial questions, but degrades on long, multi-step
research because:

1. **Specialisation:** Each subtask (search vs. analyse vs. write) benefits from
   a dedicated system prompt and temperature setting. One mega-prompt is hard to
   tune without regressions.
2. **Failure isolation:** When the answer is wrong we want to know whether the
   research, the analysis, or the writing was at fault. Separate agents make
   the bug observable in `route_history` and `agent_results`.
3. **Composable guardrails:** A Critic agent can fact-check the writer without
   rewriting the writer prompt. We can add or remove agents per use-case.
4. **Routing flexibility:** A Supervisor can short-circuit to "done" when the
   query is simple, or loop back when the critic flags issues — something one
   monolithic prompt cannot do cleanly.

## Agent roles

| Agent | Responsibility | Input | Output | Failure mode |
|---|---|---|---|---|
| Supervisor | Decide which worker runs next; enforce `max_iterations` | `ResearchState` (whole) | `state.route_history` updated | Wrong routing → wasted iterations; mitigated by deterministic rule-based logic |
| Researcher | Search the web (Brave or mock) and write `research_notes` with citations | `state.request.query`, `state.request.max_sources` | `state.sources`, `state.research_notes` | Empty / noisy mock results when no API key; over-trims long sources |
| Analyst | Extract claims, compare viewpoints, flag weak evidence | `state.research_notes` | `state.analysis_notes` | Hallucinates structure when notes are very short |
| Writer | Produce final answer with `[N]` citations and References section | `state.research_notes`, `state.analysis_notes`, `state.sources` | `state.final_answer` | Cites `[N]` beyond available sources |
| Critic | Fact-check the final answer against sources; flag hallucinations | `state.final_answer`, `state.sources`, `state.research_notes` | review appended to `state.agent_results` | Adds latency + cost; review may be vague |

## Shared state

`ResearchState` (`core/state.py`) is the single mutable Pydantic model passed
through the graph.

| Field | Why we need it |
|---|---|
| `request: ResearchQuery` | Original query, audience, max_sources — read by every agent |
| `iteration: int` | Counted by `record_route()`, used by Supervisor and graph router to enforce `max_iterations` |
| `route_history: list[str]` | Audit trail: who ran in what order, used for trace explanation and benchmark notes |
| `sources: list[SourceDocument]` | Researcher writes; Writer reads to format References; Critic reads to fact-check |
| `research_notes: str \| None` | Handoff Researcher → Analyst → Writer |
| `analysis_notes: str \| None` | Handoff Analyst → Writer |
| `final_answer: str \| None` | Output of Writer; the "is the run done?" signal |
| `agent_results: list[AgentResult]` | Per-agent token usage / metadata, drives token-count metric in benchmark; also used by supervisor to detect "writer_ran" / "critic_ran" |
| `trace: list[dict]` | Lightweight in-memory span events; persisted to LangSmith when key set |
| `errors: list[str]` | Accumulated errors, surfaced in benchmark notes as failure rate |

## Routing policy

```
            ┌──────────────┐
            │   START       │
            └──────┬────────┘
                   ▼
            ┌──────────────┐
            │  Supervisor   │◀────────────────────────────┐
            └──────┬────────┘                             │
                   │ route_history[-1]                    │
       ┌───────────┼─────────────┬────────────┬────────┐  │
       ▼           ▼             ▼            ▼        ▼  │
  researcher    analyst       writer       critic    done │
       │           │             │            │        │  │
       └───────────┴─────────────┴────────────┘        │  │
                          (each returns to Supervisor)─┘  │
                                                          │
                                                       END │
```

Supervisor logic (rule-based, in `agents/supervisor.py`):

1. If `iteration >= max_iterations` → `done` (guardrail).
2. Else if `research_notes` is empty → `researcher`.
3. Else if `analysis_notes` is empty → `analyst`.
4. Else if `final_answer` is empty → `writer`.
5. Else if writer has run and critic has not → `critic`.
6. Else → `done`.

Conditional edges in `graph/workflow.py` route END whenever the last route is
`done` or `iteration >= max_iterations`.

## Guardrails

- **Max iterations:** `MAX_ITERATIONS = 6` (env-configurable). Enforced in both
  Supervisor and `MultiAgentWorkflow._route()`.
- **Timeout:** `TIMEOUT_SECONDS = 60` (env-configurable). Available via
  `get_settings()` for any agent that wants to wrap work in a deadline.
- **Retry:** `LLMClient.complete` uses `tenacity` with 5 attempts and exponential
  backoff (2s–30s). `SearchClient._brave_search` uses 3 attempts (1s–10s).
- **Fallback:** `LLMClient` auto-selects OpenAI → Gemini based on which key is
  set. `SearchClient.search` falls back to `_mock_search` when `BRAVE_API_KEY`
  is missing.
- **Validation:** All public payloads (`ResearchQuery`, `SourceDocument`,
  `AgentResult`, `BenchmarkMetrics`) are Pydantic models with field constraints
  (`query` min length, `max_sources` 1–20, `quality_score` 0–10).
- **Type safety:** mypy strict; ruff (E, F, I, B, UP, SIM).

## Benchmark plan

Queries (from `configs/lab_default.yaml`):

1. `Research GraphRAG state-of-the-art and write a 500-word summary`
2. `Compare single-agent and multi-agent workflows for customer support`
3. `Summarize production guardrails for LLM agents`

For each query we run `baseline` (1 LLM call) and `multi-agent` (full graph)
through `evaluation.benchmark.run_benchmark` and produce a markdown report via
`evaluation.report.render_markdown_report`.

Metrics collected per run:

| Metric | Source | Expected outcome (hypothesis) |
|---|---|---|
| Latency (s) | `perf_counter()` around runner | Multi-agent ≈ 3–5× slower than baseline |
| Cost (USD) | Tokens × `MODEL_PRICES` | Multi-agent ≈ 4× more expensive |
| Total tokens | Sum of `agent_results[*].metadata` | Multi-agent ≈ 4× more tokens (≥4 LLM calls) |
| Citation coverage | `[i]` markers in `final_answer` ÷ `len(sources)` | Multi-agent higher (Writer prompt enforces References) |
| Error rate | `len(state.errors) ÷ runs` | Both should be 0 in happy path |
| Quality 0–10 | Peer-review rubric | Multi-agent higher on long queries, similar/worse on short ones |
