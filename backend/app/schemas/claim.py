"""Pydantic schemas for extracted claims."""
from pydantic import BaseModel, Field


class Claim(BaseModel):
    claim: str = Field(..., description="The factual assertion extracted from the chunk.")
    subject: str = Field(..., description="Entity the claim is about (e.g. 'gross margin').")
    predicate: str = Field(..., description="Metric or relationship (e.g. 'expanded', 'was').")
    object: str = Field(..., description="Value or target (e.g. '200bps', '$4.2B').")
    period: str = Field(..., description="Fiscal period the claim applies to (e.g. 'Q2-2023').")
    stated_cause: str | None = Field(
        default=None,
        description="Reason given in the filing for a change, if any ('due to FX headwinds'). "
        "Crucial for distinguishing EXPLAINED_CHANGE from FACTUAL_CONTRADICTION.",
    )
    confidence: float = Field(..., ge=0.0, le=1.0, description="Extraction confidence 0–1.")


class ClaimExtraction(BaseModel):
    claims: list[Claim]
