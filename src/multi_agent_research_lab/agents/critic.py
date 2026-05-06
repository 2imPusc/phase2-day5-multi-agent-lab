"""Optional critic agent for fact-checking and validation."""

from __future__ import annotations

import logging

from multi_agent_research_lab.agents.base import BaseAgent
from multi_agent_research_lab.core.schemas import AgentName, AgentResult
from multi_agent_research_lab.core.state import ResearchState
from multi_agent_research_lab.observability.tracing import trace_span
from multi_agent_research_lab.services.llm_client import LLMClient

logger = logging.getLogger(__name__)


class CriticAgent(BaseAgent):
    """Optional fact-checking and safety-review agent."""

    name = "critic"

    def __init__(self) -> None:
        self._llm = LLMClient()

    def run(self, state: ResearchState) -> ResearchState:
        """Validate final answer: fact-check, citation coverage, hallucination detection."""

        with trace_span("critic_run"):
            source_titles = [s.title for s in state.sources]

            response = self._llm.complete(
                system_prompt=(
                    "You are a research critic. Review the final answer below and:\n"
                    "1. Check if claims are supported by the cited sources.\n"
                    "2. Identify any potential hallucinations (claims not in sources).\n"
                    "3. Assess citation coverage (are all major claims cited?).\n"
                    "4. Flag any safety or accuracy concerns.\n"
                    "Provide a brief review with a pass/fail recommendation."
                ),
                user_prompt=(
                    f"Final Answer:\n{state.final_answer}\n\n"
                    f"Available Sources: {source_titles}\n\n"
                    f"Research Notes:\n{state.research_notes}"
                ),
            )

            state.agent_results.append(
                AgentResult(
                    agent=AgentName.CRITIC,
                    content=response.content,
                    metadata={
                        "input_tokens": response.input_tokens,
                        "output_tokens": response.output_tokens,
                    },
                )
            )

        state.add_trace_event("critic_done", {})
        logger.info("Critic completed review")
        return state
