"""Seed 20 manual eval test cases (W1 Fri deliverable).

Inserts into eval_test_cases with test_set_id='w1-manual', adversarial=False.
Safe to re-run; skips insertion if the test_set already has 20+ rows.

Usage:
    python backend/scripts/seed_eval_cases.py
"""
import os
import uuid
from datetime import datetime, timezone

from dotenv import load_dotenv
from sqlalchemy import create_engine, text

load_dotenv()

# 20 hand-crafted cases covering: factuality, citation, contradiction, explained-change
EVAL_CASES = [
    # --- Factuality: claim is directly supported by the chunk ---
    {
        "input_query": "What was Apple's total revenue for Q2-2023?",
        "input_document_ids": [],
        "expected_output": {"claim": "Net revenues were $94.8 billion", "verdict": "SUPPORTED"},
        "adversarial": False,
    },
    {
        "input_query": "What was Apple's iPhone net sales for Q2-2023?",
        "input_document_ids": [],
        "expected_output": {"claim": "iPhone net sales were $51.3 billion", "verdict": "SUPPORTED"},
        "adversarial": False,
    },
    {
        "input_query": "What was Apple's gross margin percentage in Q2-2023?",
        "input_document_ids": [],
        "expected_output": {"claim": "Gross margin percentage was 44.9%", "verdict": "SUPPORTED"},
        "adversarial": False,
    },
    {
        "input_query": "What was Apple's cash and equivalents as of April 1, 2023?",
        "input_document_ids": [],
        "expected_output": {"claim": "$55.2 billion in cash and marketable securities", "verdict": "SUPPORTED"},
        "adversarial": False,
    },
    {
        "input_query": "How much did Apple return to shareholders in Q2-2023?",
        "input_document_ids": [],
        "expected_output": {"claim": "$23.5 billion returned via dividends and buybacks", "verdict": "SUPPORTED"},
        "adversarial": False,
    },
    # --- Factuality negatives: plausible-but-false claims ---
    {
        "input_query": "What was Apple's Services gross margin percentage in Q2-2023?",
        "input_document_ids": [],
        "expected_output": {"claim": "Services gross margin was 85.0%", "verdict": "UNSUPPORTED"},
        "adversarial": False,
    },
    {
        "input_query": "What was Apple's R&D expense in Q2-2023?",
        "input_document_ids": [],
        "expected_output": {"claim": "R&D expense decreased 9% year-over-year", "verdict": "UNSUPPORTED"},
        "adversarial": False,
    },
    {
        "input_query": "What was Apple's Mac net sales change in Q2-2023?",
        "input_document_ids": [],
        "expected_output": {"claim": "Mac net sales increased 12% year-over-year", "verdict": "UNSUPPORTED"},
        "adversarial": False,
    },
    # --- Citation accuracy: chunk actually contains the cited information ---
    {
        "input_query": "Cite the source for Apple's operating cash flow claim",
        "input_document_ids": [],
        "expected_output": {"cited_section": "MD&A", "claim": "$28.6B operating cash flow", "citation_valid": True},
        "adversarial": False,
    },
    {
        "input_query": "Cite the source for iPad net sales claim",
        "input_document_ids": [],
        "expected_output": {"cited_section": "MD&A", "claim": "iPad net sales $6.7B", "citation_valid": True},
        "adversarial": False,
    },
    # --- Contradiction detection: genuine FACTUAL_CONTRADICTION ---
    {
        "input_query": "Is there a contradiction between Q2-2023 gross margin % and Q2-2022?",
        "input_document_ids": [],
        "expected_output": {
            "contradiction_type": "FACTUAL_CONTRADICTION",
            "claim_a": "Gross margin % Q2-2023 was 44.9%",
            "claim_b": "Gross margin % Q2-2022 was 43.8%",
            "verdict": "FACTUAL_CONTRADICTION",
        },
        "adversarial": False,
    },
    {
        "input_query": "Did iPhone sales increase or decrease in Q2-2023 vs Q2-2022?",
        "input_document_ids": [],
        "expected_output": {
            "contradiction_type": "EXPLAINED_CHANGE",
            "claim": "iPhone sales decreased due to unfavorable FX and lower demand",
            "stated_cause": "unfavorable foreign exchange rates and lower demand in certain markets",
        },
        "adversarial": False,
    },
    # --- EXPLAINED_CHANGE hard negatives: change with stated cause, must NOT be flagged ---
    {
        "input_query": "Why did Mac net sales decline in Q2-2023?",
        "input_document_ids": [],
        "expected_output": {
            "contradiction_type": "EXPLAINED_CHANGE",
            "stated_cause": "difficult year-ago comparison due to MacBook Pro M1 Pro/Max launch",
            "verdict": "EXPLAINED_CHANGE",
        },
        "adversarial": False,
    },
    {
        "input_query": "Why did Services gross margin decline from 98.9% to 98.2%?",
        "input_document_ids": [],
        "expected_output": {
            "contradiction_type": "EXPLAINED_CHANGE",
            "verdict": "EXPLAINED_CHANGE",
        },
        "adversarial": False,
    },
    {
        "input_query": "Why did iPad sales increase while iPhone sales declined?",
        "input_document_ids": [],
        "expected_output": {
            "explanation": "iPad driven by favorable FX and new launches; iPhone by unfavorable FX",
            "verdict": "EXPLAINED_CHANGE",
        },
        "adversarial": False,
    },
    # --- Risk signal extraction ---
    {
        "input_query": "What macro risks does Apple cite in Q2-2023?",
        "input_document_ids": [],
        "expected_output": {
            "risk_category": "Macro",
            "signals": ["high inflation", "rising interest rates", "FX fluctuations", "geopolitical tensions"],
        },
        "adversarial": False,
    },
    {
        "input_query": "What supply chain risks does Apple disclose?",
        "input_document_ids": [],
        "expected_output": {
            "risk_category": "Operational",
            "signals": ["single-source suppliers", "geopolitical disruptions", "natural disasters"],
        },
        "adversarial": False,
    },
    {
        "input_query": "What FX risk does Apple face?",
        "input_document_ids": [],
        "expected_output": {
            "risk_category": "Macro",
            "signals": ["revenues denominated in non-USD currencies", "exchange rate fluctuations"],
        },
        "adversarial": False,
    },
    # --- Calibration: confidence should be high for clear facts ---
    {
        "input_query": "With what confidence should the model state Apple's Q2-2023 revenue?",
        "input_document_ids": [],
        "expected_output": {
            "claim": "Net revenues $94.8B",
            "expected_confidence_min": 0.85,
            "rationale": "Exact figure stated in filing; high confidence warranted",
        },
        "adversarial": False,
    },
    {
        "input_query": "With what confidence should the model state the cause of iPhone decline?",
        "input_document_ids": [],
        "expected_output": {
            "claim": "iPhone decline due to FX and demand",
            "expected_confidence_min": 0.80,
            "rationale": "Cause explicitly stated in filing",
        },
        "adversarial": False,
    },
]


def main() -> None:
    url = os.environ.get("DATABASE_URL")
    if not url:
        raise RuntimeError("DATABASE_URL not set")

    engine = create_engine(url)
    test_set_id = "w1-manual"

    with engine.begin() as conn:
        existing = conn.execute(
            text("SELECT count(*) FROM eval_test_cases WHERE test_set_id = :ts"),
            {"ts": test_set_id},
        ).scalar()

        if existing >= 20:
            print(f"Test set '{test_set_id}' already has {existing} cases — skipping.")
            return

        now = datetime.now(timezone.utc)
        for case in EVAL_CASES:
            import json
            conn.execute(
                text(
                    "INSERT INTO eval_test_cases "
                    "(id, test_set_id, input_query, input_document_ids, expected_output, "
                    " adversarial, created_by, created_at) "
                    "VALUES (:id, :ts, :q, :doc_ids, :out, :adv, :by, :at)"
                ),
                {
                    "id": str(uuid.uuid4()),
                    "ts": test_set_id,
                    "q": case["input_query"],
                    "doc_ids": "{}",
                    "out": json.dumps(case["expected_output"]),
                    "adv": case["adversarial"],
                    "by": "human",
                    "at": now,
                },
            )

    print(f"Inserted {len(EVAL_CASES)} eval test cases (test_set_id='{test_set_id}').")


if __name__ == "__main__":
    main()
