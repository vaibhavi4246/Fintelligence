"""Claim-extraction agent node.

Given a single chunk of text and its fiscal period, returns a list of atomic
Claim objects extracted via structured LLM output (Groq primary, Ollama fallback).

This node replaces the Tue no-op in the LangGraph DAG.
"""
import logging

from app.agents.state import AgentState
from app.core.llm import chat_json
from app.schemas.claim import Claim, ClaimExtraction

logger = logging.getLogger(__name__)

_SYSTEM = """\
You are a financial analyst extracting atomic factual claims from SEC filing excerpts.

For each distinct fact in the text, extract:
- claim: the full factual assertion as a standalone sentence
- subject: the entity or metric the claim is about
- predicate: the verb or relationship (e.g., "increased", "was", "declined")
- object: the value, amount, or target of the assertion
- period: the fiscal period this claim applies to (use the period provided if not explicit)
- stated_cause: ONLY if the filing explicitly states why something changed (e.g., "due to FX
  headwinds"). Leave null if no cause is stated. This is critical — it distinguishes legitimate
  business changes from factual contradictions.
- confidence: your confidence in the extraction (0.0–1.0)

Extract ALL distinct claims. Include numerical claims, directional claims, and qualitative
assertions. Do not invent information not present in the text.
"""


def extract_claims(chunk_text: str, period: str) -> list[Claim]:
    """Extract atomic claims from a single chunk.

    Args:
        chunk_text: Raw text of the chunk from a filing.
        period: Fiscal period context (e.g. "Q2-2023").

    Returns:
        List of validated Claim objects.
    """
    user = f"Fiscal period: {period}\n\nFiling excerpt:\n{chunk_text}"
    result: ClaimExtraction = chat_json(_SYSTEM, user, ClaimExtraction)
    return result.claims


def extraction_node(state: AgentState) -> AgentState:
    """LangGraph node: extract claims from all chunks in state."""
    chunks = state.get("chunks", [])
    all_claims: list[dict] = []
    for chunk in chunks:
        try:
            claims = extract_claims(chunk["content"], chunk.get("fiscal_period", "unknown"))
            all_claims.extend(c.model_dump() for c in claims)
        except Exception:  # noqa: BLE001
            logger.exception("Claim extraction failed for chunk %s", chunk.get("id"))
    return {**state, "claims": all_claims}
