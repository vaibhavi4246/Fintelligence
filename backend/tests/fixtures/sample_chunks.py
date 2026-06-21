"""Three hand-picked financial chunk excerpts used in unit tests.

Chosen to exercise the core extraction cases:
  1. A numerical fact with a stated cause (EXPLAINED_CHANGE scenario)
  2. A plain numerical claim with no stated cause (FACTUAL_CONTRADICTION candidate)
  3. A qualitative risk/litigation claim
"""

CHUNK_GROSS_MARGIN_EXPLAINED = {
    "id": "chunk-001",
    "content": (
        "Gross margin for the three months ended June 30, 2023 was 43.5%, compared to 45.7% "
        "in the prior-year period. The decrease of 220 basis points was primarily attributable "
        "to increased component costs and unfavorable foreign exchange movements in the yen and euro."
    ),
    "fiscal_period": "Q2-2023",
    "section_label": "MD&A",
}

CHUNK_REVENUE_PLAIN = {
    "id": "chunk-002",
    "content": (
        "Net revenues for the second quarter of fiscal 2023 were $4.2 billion, representing "
        "a 12% increase from $3.75 billion in the second quarter of fiscal 2022. "
        "Product revenues were $2.8 billion and service revenues were $1.4 billion."
    ),
    "fiscal_period": "Q2-2023",
    "section_label": "Financial Statements",
}

CHUNK_LITIGATION_RISK = {
    "id": "chunk-003",
    "content": (
        "As of June 30, 2023, the Company is not a party to any material legal proceedings. "
        "However, from time to time, we may become involved in litigation arising in the ordinary "
        "course of business. We maintain insurance coverage that management believes is adequate "
        "to cover potential liability."
    ),
    "fiscal_period": "Q2-2023",
    "section_label": "Risk Factors",
}

ALL_SAMPLE_CHUNKS = [CHUNK_GROSS_MARGIN_EXPLAINED, CHUNK_REVENUE_PLAIN, CHUNK_LITIGATION_RISK]
