"""Analyst agent."""

from __future__ import annotations

import logging

from multi_agent_research_lab.agents.base import BaseAgent
from multi_agent_research_lab.core.schemas import AgentName, AgentResult
from multi_agent_research_lab.core.state import ResearchState
from multi_agent_research_lab.observability.tracing import trace_span
from multi_agent_research_lab.services.llm_client import LLMClient

logger = logging.getLogger(__name__)


class AnalystAgent(BaseAgent):
    """Turns research notes into structured insights."""

    name = "analyst"

    def __init__(self) -> None:
        self._llm = LLMClient()

    def run(self, state: ResearchState) -> ResearchState:
        """Extract key claims, compare viewpoints, and flag weak evidence."""

        with trace_span(
            "analyst_run",
            {
                "query": state.request.query,
                "research_notes_chars": len(state.research_notes or ""),
            },
        ) as span:
            response = self._llm.complete(
                system_prompt=(
                    "You are a research analyst. Given the research notes below:\n"
                    "1. Extract the key claims and findings.\n"
                    "2. Compare different viewpoints if present.\n"
                    "3. Flag any claims with weak or missing evidence.\n"
                    "4. Identify gaps that need further investigation.\n"
                    "Write structured analysis notes."
                ),
                user_prompt=f"Query: {state.request.query}\n\nResearch Notes:\n{state.research_notes}",
            )

            state.analysis_notes = response.content
            state.agent_results.append(
                AgentResult(
                    agent=AgentName.ANALYST,
                    content=response.content,
                    metadata={
                        "input_tokens": response.input_tokens,
                        "output_tokens": response.output_tokens,
                    },
                )
            )
            span["attributes"]["input_tokens"] = response.input_tokens
            span["attributes"]["output_tokens"] = response.output_tokens
            span["attributes"]["analysis_preview"] = response.content[:300]

        state.add_trace_event("analyst_done", {})
        logger.info("Analyst completed analysis")
        return state
