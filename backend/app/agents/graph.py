"""LangGraph DAG assembly.

W1 Tue: a single no-op node, just to prove LangGraph is installed and wired.
Subsequent days replace/extend this with the real agents
(retrieval -> contradiction -> risk -> assembler).
"""
from langgraph.graph import END, START, StateGraph

from app.agents.state import AgentState


def _noop(state: AgentState) -> AgentState:
    """Placeholder agent — passes state through unchanged."""
    return state


def build_graph():
    """Compile and return the agent graph."""
    builder = StateGraph(AgentState)
    builder.add_node("noop", _noop)
    builder.add_edge(START, "noop")
    builder.add_edge("noop", END)
    return builder.compile()


graph = build_graph()
