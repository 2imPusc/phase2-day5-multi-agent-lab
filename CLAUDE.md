# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Multi-agent research lab starter for VinUniversity. A production-grade skeleton teaching multi-agent orchestration with LangGraph. A supervisor agent routes between researcher, analyst, and writer agents via shared state (`ResearchState`). Most agent logic contains `TODO(student)` markers for students to implement.

**Stack:** Python 3.11+, LangGraph 0.2+, OpenAI, Pydantic 2.7+, Typer CLI, pytest, ruff, mypy.

## Commands

```bash
make install          # pip install -e ".[dev,llm]"
make test             # pytest
make lint             # ruff check src tests
make format           # ruff format src tests
make typecheck        # mypy src
make run-baseline     # single-agent placeholder
make run-multi        # multi-agent workflow (raises StudentTodoError for unimplemented parts)
```

CLI directly: `python -m multi_agent_research_lab.cli baseline --query "..."` or `malab multi-agent --query "..."` after install.

Run a single test: `pytest tests/test_state.py -k test_name`

## Architecture

```
User Query → Supervisor → [Researcher | Analyst | Writer | Done] → ResearchState
```

- **Shared state pattern:** `ResearchState` (in `core/state.py`) is the single mutable object passed through the entire workflow. Agents read and modify it—no direct inter-agent communication.
- **Agent contract:** All agents inherit `BaseAgent` (`agents/base.py`) with `run(state) -> ResearchState`.
- **Service abstractions:** `LLMClient` and `SearchClient` (in `services/`) decouple agents from OpenAI/Tavily APIs.
- **Graph orchestration:** `MultiAgentWorkflow` (in `graph/workflow.py`) uses LangGraph `StateGraph` with conditional edges based on supervisor routing decisions.
- **Guardrails:** `MAX_ITERATIONS` (default 6) and `TIMEOUT_SECONDS` (default 60), configurable via env vars. Errors accumulate in `state.errors`.

## Key Conventions

- **Strict typing:** mypy strict mode; all functions need type hints.
- **Ruff rules:** E, F, I, B, UP, SIM enabled.
- **StudentTodoError:** Raised by unimplemented sections. Tests in `test_agents_todo.py` verify this behavior—don't remove these raises until implementing the actual logic.
- **Config:** Env vars loaded via pydantic-settings (`core/config.py`). Copy `.env.example` to `.env` for local dev.
- **Tracing:** Use `trace_span()` context manager and `state.add_trace_event()` for observability.
- **YAML config:** `configs/lab_default.yaml` holds agent temperatures, benchmark queries, and lab limits.

## Finding Student TODOs

```bash
grep -rn "TODO(student)" src tests docs
```
