"""Researcher agent."""

from __future__ import annotations

import logging

from multi_agent_research_lab.agents.base import BaseAgent
from multi_agent_research_lab.core.schemas import AgentName, AgentResult
from multi_agent_research_lab.core.state import ResearchState
from multi_agent_research_lab.observability.tracing import trace_span
from multi_agent_research_lab.services.llm_client import LLMClient
from multi_agent_research_lab.services.search_client import SearchClient

logger = logging.getLogger(__name__)


class ResearcherAgent(BaseAgent):
    """Collects sources and creates concise research notes."""

    name = "researcher"

    def __init__(self) -> None:
        self._llm = LLMClient()
        self._search = SearchClient()

    def run(self, state: ResearchState) -> ResearchState:
        """Search for sources and synthesize research notes."""

        with trace_span("researcher_run") as span:
            # Search for sources
            sources = self._search.search(state.request.query, state.request.max_sources)
            state.sources.extend(sources)

            # Build context from sources for LLM
            source_text = "\n\n".join(
                f"[{i + 1}] {s.title}\n{s.snippet}" for i, s in enumerate(sources)
            )

            response = self._llm.complete(
                system_prompt=(
                    "You are a research assistant. Summarize the following sources into "
                    "clear, concise research notes. Include key facts, cite source numbers "
                    "in brackets [1], [2], etc. Write for: " + state.request.audience
                ),
                user_prompt=f"Query: {state.request.query}\n\nSources:\n{source_text}",
            )

            state.research_notes = response.content
            state.agent_results.append(
                AgentResult(
                    agent=AgentName.RESEARCHER,
                    content=response.content,
                    metadata={
                        "sources_found": len(sources),
                        "input_tokens": response.input_tokens,
                        "output_tokens": response.output_tokens,
                    },
                )
            )
            span["attributes"]["sources_found"] = len(sources)

        state.add_trace_event("researcher_done", {"sources": len(sources)})
        logger.info("Researcher found %d sources", len(sources))
        return state
