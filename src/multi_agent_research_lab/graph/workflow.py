"""LangGraph workflow for multi-agent research."""

from __future__ import annotations

import logging
from typing import Any, TypedDict

from langgraph.graph import END, StateGraph

from multi_agent_research_lab.agents.analyst import AnalystAgent
from multi_agent_research_lab.agents.critic import CriticAgent
from multi_agent_research_lab.agents.researcher import ResearcherAgent
from multi_agent_research_lab.agents.supervisor import SupervisorAgent
from multi_agent_research_lab.agents.writer import WriterAgent
from multi_agent_research_lab.core.config import get_settings
from multi_agent_research_lab.core.state import ResearchState

logger = logging.getLogger(__name__)


class _GraphState(TypedDict, total=False):
    """Dict-based state for LangGraph; mirrors ResearchState fields."""

    request: dict[str, Any]
    iteration: int
    route_history: list[str]
    sources: list[dict[str, Any]]
    research_notes: str | None
    analysis_notes: str | None
    final_answer: str | None
    agent_results: list[dict[str, Any]]
    trace: list[dict[str, Any]]
    errors: list[str]


class MultiAgentWorkflow:
    """Builds and runs the multi-agent graph.

    Keep orchestration here; keep agent internals in `agents/`.
    """

    def __init__(self) -> None:
        self._supervisor = SupervisorAgent()
        self._agents: dict[str, Any] = {
            "researcher": ResearcherAgent(),
            "analyst": AnalystAgent(),
            "writer": WriterAgent(),
            "critic": CriticAgent(),
        }
        self._settings = get_settings()

    def _make_node(self, agent: Any) -> Any:
        """Wrap an agent so it accepts/returns a dict for LangGraph."""

        def node_fn(state: _GraphState) -> _GraphState:
            rs = ResearchState.model_validate(state)
            rs = agent.run(rs)
            return rs.model_dump()  # type: ignore[return-value]

        return node_fn

    def _route(self, state: _GraphState) -> str:
        """Determine next node from the last route in history."""

        history = state.get("route_history", [])
        if not history:
            return END
        last_route = history[-1]
        if last_route == "done":
            return END
        if state.get("iteration", 0) >= self._settings.max_iterations:
            return END
        if last_route in self._agents:
            return last_route
        return END

    def build(self) -> Any:
        """Create a LangGraph StateGraph with supervisor routing."""

        graph: StateGraph[_GraphState] = StateGraph(_GraphState)  # type: ignore[type-arg]

        # Add nodes
        graph.add_node("supervisor", self._make_node(self._supervisor))
        for name, agent in self._agents.items():
            graph.add_node(name, self._make_node(agent))

        # Entry point
        graph.set_entry_point("supervisor")

        # Supervisor decides which worker runs next (or END)
        graph.add_conditional_edges(
            "supervisor",
            self._route,
            {name: name for name in self._agents} | {END: END},
        )

        # Each worker returns to supervisor for re-evaluation
        for name in self._agents:
            graph.add_edge(name, "supervisor")

        return graph.compile()

    def run(self, state: ResearchState) -> ResearchState:
        """Compile graph, invoke it, and convert result back to ResearchState."""

        compiled = self.build()
        logger.info("Starting multi-agent workflow for query: %s", state.request.query)
        result = compiled.invoke(state.model_dump())
        return ResearchState.model_validate(result)
