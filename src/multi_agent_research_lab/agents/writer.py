"""Writer agent."""

from __future__ import annotations

import logging

from multi_agent_research_lab.agents.base import BaseAgent
from multi_agent_research_lab.core.schemas import AgentName, AgentResult
from multi_agent_research_lab.core.state import ResearchState
from multi_agent_research_lab.observability.tracing import trace_span
from multi_agent_research_lab.services.llm_client import LLMClient

logger = logging.getLogger(__name__)


class WriterAgent(BaseAgent):
    """Produces final answer from research and analysis notes."""

    name = "writer"

    def __init__(self) -> None:
        self._llm = LLMClient()

    def run(self, state: ResearchState) -> ResearchState:
        """Synthesize a clear response with citations or source references."""

        with trace_span(
            "writer_run",
            {
                "query": state.request.query,
                "num_sources": len(state.sources),
                "audience": state.request.audience,
            },
        ) as span:
            # Build source reference list
            source_refs = "\n".join(
                f"[{i + 1}] {s.title} — {s.url or 'no url'}"
                for i, s in enumerate(state.sources)
            )

            response = self._llm.complete(
                system_prompt=(
                    "You are a research writer. Using the research notes and analysis below, "
                    "write a clear, well-structured response. Include citations using bracket "
                    "notation [1], [2], etc. matching the source list. End with a References "
                    "section. Target audience: " + state.request.audience
                ),
                user_prompt=(
                    f"Query: {state.request.query}\n\n"
                    f"Research Notes:\n{state.research_notes}\n\n"
                    f"Analysis Notes:\n{state.analysis_notes}\n\n"
                    f"Sources:\n{source_refs}"
                ),
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
            span["attributes"]["input_tokens"] = response.input_tokens
            span["attributes"]["output_tokens"] = response.output_tokens
            span["attributes"]["final_answer_chars"] = len(response.content)
            span["attributes"]["final_answer_preview"] = response.content[:400]

        state.add_trace_event("writer_done", {})
        logger.info("Writer completed final answer")
        return state
