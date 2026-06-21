"""Shared state passed between LangGraph agent nodes.

The DAG grows over W1-W2: retrieval -> contradiction -> risk -> assembler.
For now it carries the inputs and a `claims` slot the Wed extraction node fills.
"""
from typing import Any, TypedDict


class AgentState(TypedDict, total=False):
    document_ids: list[str]
    query_config: dict[str, Any]
    chunks: list[dict[str, Any]]
    claims: list[dict[str, Any]]
