from multi_agent_research_lab.agents import SupervisorAgent
from multi_agent_research_lab.core.schemas import ResearchQuery
from multi_agent_research_lab.core.state import ResearchState


def test_supervisor_routes_researcher_first() -> None:
    """Supervisor should route to researcher when no research notes exist."""
    state = ResearchState(request=ResearchQuery(query="Explain multi-agent systems"))
    result = SupervisorAgent().run(state)
    assert result.route_history[-1] == "researcher"


def test_supervisor_routes_done_when_complete() -> None:
    """Supervisor should route to done when all fields are filled."""
    state = ResearchState(
        request=ResearchQuery(query="Explain multi-agent systems"),
        research_notes="notes",
        analysis_notes="analysis",
        final_answer="answer",
    )
    result = SupervisorAgent().run(state)
    assert result.route_history[-1] == "done"


def test_supervisor_stops_at_max_iterations() -> None:
    """Supervisor should stop when max iterations reached."""
    state = ResearchState(
        request=ResearchQuery(query="Explain multi-agent systems"),
        iteration=20,
    )
    result = SupervisorAgent().run(state)
    assert result.route_history[-1] == "done"
