"""LangGraph DAG assembly.

W1 Wed: retrieval stub -> extraction node.
Subsequent weeks add contradiction, risk, assembler nodes.
"""
from langgraph.graph import END, START, StateGraph

from app.agents.extraction import extraction_node
from app.agents.state import AgentState


def build_graph():
    """Compile and return the agent graph."""
    builder = StateGraph(AgentState)
    builder.add_node("extraction", extraction_node)
    builder.add_edge(START, "extraction")
    builder.add_edge("extraction", END)
    return builder.compile()


graph = build_graph()
