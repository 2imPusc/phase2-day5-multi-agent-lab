"""Supervisor / router agent."""

from __future__ import annotations

import logging

from multi_agent_research_lab.agents.base import BaseAgent
from multi_agent_research_lab.core.config import get_settings
from multi_agent_research_lab.core.state import ResearchState

logger = logging.getLogger(__name__)


class SupervisorAgent(BaseAgent):
    """Decides which worker should run next and when to stop."""

    name = "supervisor"

    def run(self, state: ResearchState) -> ResearchState:
        """Route to the next agent based on what is missing in the state."""

        settings = get_settings()

        # Enforce max iterations — fallback to done
        if state.iteration >= settings.max_iterations:
            logger.warning("Max iterations (%d) reached — stopping", settings.max_iterations)
            state.record_route("done")
            return state

        # Track which agents have already produced a result (avoid loops)
        writer_ran = any(r.agent.value == "writer" for r in state.agent_results)
        critic_ran = any(r.agent.value == "critic" for r in state.agent_results)

        # Determine next route based on missing fields
        if not state.research_notes:
            route = "researcher"
        elif not state.analysis_notes:
            route = "analyst"
        elif not state.final_answer:
            route = "writer"
        elif writer_ran and not critic_ran:
            route = "critic"
        else:
            route = "done"

        logger.info("Supervisor routing to: %s (iteration %d)", route, state.iteration)
        state.record_route(route)
        state.add_trace_event("supervisor_route", {"route": route, "iteration": state.iteration})
        return state
