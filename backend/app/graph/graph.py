"""Wires the outreach multi-agent graph.

Topology:
    START -> supervisor
    supervisor --(conditional)--> { jd_analyzer | recruiter_finder | writer | END }
    jd_analyzer      -> supervisor
    recruiter_finder -> supervisor
    writer -> critic
    critic --(conditional)--> { writer | supervisor }

The writer<->critic cycle is a self-contained reflection loop: the Supervisor
delegates "produce a good email" and the loop runs autonomously until the critic
passes or the revision budget is spent, then reports back.
"""
from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, START, StateGraph

from app import config
from app.graph.nodes import critic, jd_analyzer, recruiter_finder, supervisor, writer
from app.graph.state import OutreachState


def _route_from_supervisor(state: OutreachState) -> str:
    """Supervisor already computed the decision; just read it."""
    return state["next"]


def _route_from_critic(state: OutreachState) -> str:
    """Reflection-loop guard: revise again only if the critique failed AND the
    revision budget is not yet spent."""
    critique = state.get("critique")
    revisions = state.get("revision_count", 0)
    if critique is not None and not critique.passed and revisions < config.MAX_REVISIONS:
        return "writer"
    return "supervisor"


def build_graph():
    g = StateGraph(OutreachState)

    g.add_node("supervisor", supervisor)
    g.add_node("jd_analyzer", jd_analyzer)
    g.add_node("recruiter_finder", recruiter_finder)
    g.add_node("writer", writer)
    g.add_node("critic", critic)

    g.add_edge(START, "supervisor")
    g.add_conditional_edges(
        "supervisor",
        _route_from_supervisor,
        {
            "jd_analyzer": "jd_analyzer",
            "recruiter_finder": "recruiter_finder",
            "writer": "writer",
            "END": END,
        },
    )
    g.add_edge("jd_analyzer", "supervisor")
    g.add_edge("recruiter_finder", "supervisor")
    g.add_edge("writer", "critic")
    g.add_conditional_edges(
        "critic",
        _route_from_critic,
        {"writer": "writer", "supervisor": "supervisor"},
    )

    # MemorySaver keeps per-thread state in memory so follow-up requests resume
    # the same job context. No database — deliberate scope decision.
    return g.compile(checkpointer=MemorySaver())


graph = build_graph()
