# Multi-Agent Research Lab

> **Lab 20 — VinUniversity · Phase 2 · Day 5**
> Hệ thống nghiên cứu đa-agent dùng LangGraph, gồm 5 agent
> (Supervisor → Researcher → Analyst → Writer → Critic), với tracing LangSmith,
> benchmark tự động và Gradio UI để demo trực tiếp.

[![tests](https://img.shields.io/badge/tests-6%2F6%20passing-brightgreen)](#6-test)
[![python](https://img.shields.io/badge/python-3.11%2B-blue)](https://www.python.org)
[![lint](https://img.shields.io/badge/lint-ruff-orange)](https://docs.astral.sh/ruff/)

---

## 1. Mô tả ngắn

Hệ thống nhận một câu hỏi nghiên cứu (research query), sau đó:

1. **Supervisor** quyết định agent nào chạy tiếp theo dựa trên trạng thái hiện tại.
2. **Researcher** search Brave Search API → trả về 5 source.
3. **Analyst** đọc research notes, trích claims, flag điểm yếu evidence.
4. **Writer** tổng hợp final answer kèm citation `[1]`–`[N]` và References section.
5. **Critic** fact-check final answer dựa trên sources, phát hiện hallucination.

Tất cả agent chia sẻ một `ResearchState` (Pydantic model) — single source of
truth, dễ debug, dễ benchmark.

### So sánh với single-agent baseline (số thật từ run 2026-05-06)

| Metric                | Baseline   | Multi-agent | Hệ số       |
| --------------------- | ---------: | ----------: | ----------: |
| Latency trung bình    | 11.66s     | 41.24s      | **3.54×**   |
| Cost trung bình       | $0.00043   | $0.00183    | **4.26×**   |
| Token sử dụng         | 787        | 5746        | **7.30×**   |
| **Citation coverage** | **0%**     | **100%**    | **+100 pp** |

→ Trade-off chi tiết xem `reports/benchmark_report.md`.

---

## 2. Kiến trúc

```text
            ┌──────────────┐
            │    START      │
            └──────┬────────┘
                   ▼
            ┌──────────────┐
            │  Supervisor   │◀────────────────────────────┐
            └──────┬────────┘                             │
                   │                                      │
       ┌───────────┼─────────────┬────────────┬────────┐  │
       ▼           ▼             ▼            ▼        ▼  │
  researcher    analyst       writer       critic    done │
       │           │             │            │        │  │
       └───────────┴─────────────┴────────────┘        │  │
                          (mỗi worker quay về Supervisor)─┘
                                                          │
                                                       END │
```

- **Shared state pattern:** `ResearchState` (`core/state.py`) — agent không gọi
  trực tiếp lẫn nhau, chỉ đọc/ghi state.
- **Service abstractions:** `LLMClient`, `SearchClient` (`services/`) tách agent
  khỏi OpenAI/Gemini/Brave SDK.
- **Guardrails:** `MAX_ITERATIONS=6`, `TIMEOUT_SECONDS=60`, retry exponential
  backoff với `tenacity` (5 lần / 2-30s).

### Cấu trúc thư mục

```text
.
├── src/multi_agent_research_lab/
│   ├── agents/          # 5 agent: supervisor, researcher, analyst, writer, critic
│   ├── core/            # config, state, schemas, errors
│   ├── graph/           # LangGraph StateGraph workflow
│   ├── services/        # LLMClient, SearchClient, LocalArtifactStore
│   ├── evaluation/      # benchmark + report renderer
│   ├── observability/   # logging, LangSmith tracing
│   ├── ui/              # Gradio chat app
│   └── cli.py           # CLI entrypoint (baseline / multi-agent / benchmark)
├── configs/lab_default.yaml
├── docs/                # design template, lab guide, peer review rubric
├── reports/             # benchmark output
├── tests/               # 6 unit tests (pytest)
└── Makefile
```

---

## 3. Cài đặt

### Yêu cầu

- Python 3.11+
- (Tùy chọn) `OPENAI_API_KEY` **hoặc** `GOOGLE_API_KEY` để gọi LLM thật
- (Tùy chọn) `BRAVE_API_KEY` để search thật, không có thì dùng mock
- (Tùy chọn) `LANGSMITH_API_KEY` để có trace trên smith.langchain.com

### Setup nhanh

```bash
# Tạo venv
python -m venv .venv
.venv\Scripts\activate          # Windows
# source .venv/bin/activate     # macOS / Linux

# Install (gồm dev + llm + ui)
pip install -e ".[dev,llm,ui]"

# Cấu hình
cp .env.example .env
# Mở .env và điền key:
#   OPENAI_API_KEY=sk-...
#   BRAVE_API_KEY=...
#   LANGSMITH_API_KEY=...
```

### Verify install

```bash
make test      # 6 tests phải pass
python -m multi_agent_research_lab.cli --help
```

---

## 4. Cách dùng

### 4.1. CLI

3 commands chính:

```bash
# Single-agent baseline (1 LLM call, ~$0.0004 / call)
python -m multi_agent_research_lab.cli baseline -q "Explain RAG in 100 words"

# Multi-agent workflow (4 LLM calls + 1 search, ~$0.002 / call)
python -m multi_agent_research_lab.cli multi-agent -q "Research GraphRAG state-of-the-art"

# Benchmark cả 2 mode trên 3 query trong configs/lab_default.yaml
python -m multi_agent_research_lab.cli benchmark
python -m multi_agent_research_lab.cli benchmark --queries-limit 1   # quick demo
```

Output benchmark: `reports/benchmark_report.md`.

### 4.2. Gradio UI

```bash
make ui
# hoặc:
python -m multi_agent_research_lab.ui.gradio_app
```

Mở <http://127.0.0.1:7860> — chat box hỗ trợ:

- Toggle baseline ↔ multi-agent
- Hiện route_history live
- Side panel: latency, tokens, cost USD, model
- Bảng agent breakdown (token in/out của từng agent)
- Danh sách sources có URL
- Hint mở LangSmith trace

Demo screenshot: [`reports/screenshots/gradio_demo.png`](reports/screenshots/gradio_demo.png)

### 4.3. Make targets

```bash
make install       # cài dependencies
make test          # pytest
make lint          # ruff check
make format        # ruff format
make typecheck     # mypy strict
make run-baseline  # demo baseline với query mặc định
make run-multi     # demo multi-agent với query mặc định
make ui            # mở Gradio
make clean         # xóa cache
```

---

## 5. Quy ước production

- **Strict typing:** mypy strict mode, mọi function có type hint.
- **Lint:** ruff với rules `E, F, I, B, UP, SIM`.
- **Schema validation:** input/output dùng Pydantic 2 (`ResearchQuery`,
  `SourceDocument`, `AgentResult`, `BenchmarkMetrics`).
- **Không hard-code API key:** đọc qua `pydantic-settings` từ `.env`.
- **Logging + tracing:** Python logging + LangSmith span.
- **Guardrails đa tầng:** max iterations (Supervisor + graph router),
  retry với exponential backoff, fallback (OpenAI → Gemini, Brave → mock).
- **Benchmark có metric cụ thể:** latency, cost, tokens, citation coverage,
  failure rate — không demo bằng cảm tính.

---

## 6. Test

```bash
make test
# .....                                                                   [100%]
# 6 passed in 0.5s
```

Test coverage:

- `test_state.py` — `ResearchState.record_route` + `add_trace_event`
- `test_config.py` — Settings load từ env
- `test_report.py` — markdown renderer
- `test_agents_todo.py` — supervisor routing (3 cases: routes_researcher_first,
  routes_done_when_complete, stops_at_max_iterations)

---

## 7. Deliverables (lab submission)

| #   | Deliverable                                    | Vị trí                                                            | Trạng thái                            |
| --- | ---------------------------------------------- | ----------------------------------------------------------------- | ------------------------------------- |
| 1   | GitHub repo cá nhân                            | URL repo                                                          | ✅                                    |
| 2   | Benchmark report so sánh single vs multi-agent | `reports/benchmark_report.md`                                     | ✅ (số thật trên 3 query)             |
| 3   | Failure-mode write-up                          | section 3 trong `benchmark_report.md`                             | ✅ (5 mode)                           |
| 4   | Screenshot/link trace                          | `reports/screenshots/{gradio_demo,langsmith}.png` + sections 4, 5 | ✅ screenshot; ⏳ paste 6 trace URL   |
| 5   | Design document                                | `docs/design_template.md`                                         | ✅                                    |
| 6   | Peer review (Milestone 5)                      | live trong lab                                                    | ⏳                                    |
| 7   | Exit ticket (Milestone 6)                      | live trong lab + section 7 báo cáo                                | ✅ draft trong report; ⏳ live answer |

---

## 8. Tham khảo

- Anthropic — [Building effective agents](https://www.anthropic.com/engineering/building-effective-agents)
- OpenAI — [Agents SDK orchestration / handoffs](https://developers.openai.com/api/docs/guides/agents/orchestration)
- LangGraph — [Concepts](https://langchain-ai.github.io/langgraph/concepts/)
- LangSmith — [Tracing docs](https://docs.smith.langchain.com/)
- Brave Search API — [docs](https://api.search.brave.com/)

---

## 9. License

MIT — xem `LICENSE`.
