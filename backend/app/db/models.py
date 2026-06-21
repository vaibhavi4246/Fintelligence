import enum
import uuid
from datetime import datetime

from pgvector.sqlalchemy import Vector
from sqlalchemy import JSON, ARRAY, Boolean, DateTime, Enum, Float, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class ProcessingStatus(str, enum.Enum):
    pending = "pending"
    processing = "processing"
    completed = "completed"
    failed = "failed"


class ClaimType(str, enum.Enum):
    fact = "fact"
    risk = "risk"
    contradiction = "contradiction"


class ContradictionType(str, enum.Enum):
    factual_contradiction = "FACTUAL_CONTRADICTION"
    explained_change = "EXPLAINED_CHANGE"
    restatement = "RESTATEMENT"


class Severity(str, enum.Enum):
    low = "low"
    medium = "medium"
    high = "high"


class EdgeType(str, enum.Enum):
    same_metric = "SAME_METRIC"
    contradicts = "CONTRADICTS"
    explains = "EXPLAINS"
    restates = "RESTATES"
    alias_of = "ALIAS_OF"


class Document(Base):
    __tablename__ = "documents"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    ticker: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    filing_type: Mapped[str] = mapped_column(String(32), nullable=False)
    fiscal_period: Mapped[str] = mapped_column(String(16), nullable=False)
    fiscal_year: Mapped[int] = mapped_column(Integer, nullable=False)
    source_url: Mapped[str] = mapped_column(Text, nullable=False)
    ingested_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow, nullable=False)
    chunk_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    processing_status: Mapped[ProcessingStatus] = mapped_column(
        Enum(ProcessingStatus, name="processing_status_enum"), default=ProcessingStatus.pending, nullable=False
    )


class Chunk(Base):
    __tablename__ = "chunks"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    document_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("documents.id", ondelete="CASCADE"), nullable=False, index=True
    )
    chunk_index: Mapped[int] = mapped_column(Integer, nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    embedding = mapped_column(Vector(768), nullable=True)
    section_label: Mapped[str | None] = mapped_column(String(128), nullable=True)
    page_number: Mapped[int | None] = mapped_column(Integer, nullable=True)


class IntelligenceReport(Base):
    __tablename__ = "intelligence_reports"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    query_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    document_ids: Mapped[list[uuid.UUID]] = mapped_column(ARRAY(UUID(as_uuid=True)), nullable=False)
    model_version: Mapped[str] = mapped_column(String(64), nullable=False)
    generated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow, nullable=False)
    structured_output = mapped_column(JSON, nullable=False)
    overall_confidence: Mapped[float] = mapped_column(Float, nullable=False)
    contradiction_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    risk_signal_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)


class Claim(Base):
    __tablename__ = "claims"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    report_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("intelligence_reports.id", ondelete="CASCADE"), nullable=False, index=True
    )
    claim_text: Mapped[str] = mapped_column(Text, nullable=False)
    claim_type: Mapped[ClaimType] = mapped_column(Enum(ClaimType, name="claim_type_enum"), nullable=False)
    confidence_score: Mapped[float] = mapped_column(Float, nullable=False)
    supporting_chunk_ids: Mapped[list[uuid.UUID]] = mapped_column(ARRAY(UUID(as_uuid=True)), nullable=False)
    cited_document_ids: Mapped[list[uuid.UUID]] = mapped_column(ARRAY(UUID(as_uuid=True)), nullable=False)
    verified: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)


class Contradiction(Base):
    __tablename__ = "contradictions"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    report_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("intelligence_reports.id", ondelete="CASCADE"), nullable=False, index=True
    )
    claim_a_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("claims.id"), nullable=False)
    claim_b_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("claims.id"), nullable=False)
    document_a_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("documents.id"), nullable=False)
    document_b_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("documents.id"), nullable=False)
    period_a: Mapped[str] = mapped_column(String(16), nullable=False)
    period_b: Mapped[str] = mapped_column(String(16), nullable=False)
    contradiction_type: Mapped[ContradictionType] = mapped_column(
        Enum(ContradictionType, name="contradiction_type_enum"), nullable=False
    )
    stated_cause: Mapped[str | None] = mapped_column(Text, nullable=True)
    restatement_source: Mapped[str | None] = mapped_column(Text, nullable=True)
    severity: Mapped[Severity] = mapped_column(Enum(Severity, name="severity_enum"), nullable=False)
    explanation: Mapped[str] = mapped_column(Text, nullable=False)


class RiskSignal(Base):
    __tablename__ = "risk_signals"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    report_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("intelligence_reports.id", ondelete="CASCADE"), nullable=False, index=True
    )
    signal_text: Mapped[str] = mapped_column(Text, nullable=False)
    taxonomy_category: Mapped[str] = mapped_column(String(64), nullable=False)
    severity: Mapped[Severity] = mapped_column(Enum(Severity, name="risk_severity_enum"), nullable=False)
    source_chunk_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("chunks.id"), nullable=False)
    confidence_score: Mapped[float] = mapped_column(Float, nullable=False)


class ClaimNode(Base):
    __tablename__ = "claim_nodes"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    ticker: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    subject: Mapped[str] = mapped_column(String(255), nullable=False)
    predicate: Mapped[str] = mapped_column(String(255), nullable=False)
    object: Mapped[str] = mapped_column(Text, nullable=False)
    period: Mapped[str] = mapped_column(String(16), nullable=False)
    claim_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("claims.id"), nullable=False)
    canonical_entity_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)


class ClaimEdge(Base):
    __tablename__ = "claim_edges"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    source_node_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("claim_nodes.id", ondelete="CASCADE"), nullable=False
    )
    target_node_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("claim_nodes.id", ondelete="CASCADE"), nullable=False
    )
    edge_type: Mapped[EdgeType] = mapped_column(Enum(EdgeType, name="edge_type_enum"), nullable=False)
    weight: Mapped[float] = mapped_column(Float, default=1.0, nullable=False)
    period_delta: Mapped[int] = mapped_column(Integer, default=0, nullable=False)


class EvalRun(Base):
    __tablename__ = "eval_runs"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    model_version: Mapped[str] = mapped_column(String(64), nullable=False)
    run_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow, nullable=False)
    test_set_id: Mapped[str] = mapped_column(String(64), nullable=False)
    factuality_score: Mapped[float] = mapped_column(Float, nullable=False)
    citation_accuracy: Mapped[float] = mapped_column(Float, nullable=False)
    calibration_score: Mapped[float] = mapped_column(Float, nullable=False)
    contradiction_precision: Mapped[float] = mapped_column(Float, nullable=False)
    contradiction_recall: Mapped[float] = mapped_column(Float, nullable=False)
    precision_ci_low: Mapped[float] = mapped_column(Float, nullable=False)
    precision_ci_high: Mapped[float] = mapped_column(Float, nullable=False)
    extractor_model: Mapped[str] = mapped_column(String(128), nullable=False)
    judge_model: Mapped[str] = mapped_column(String(128), nullable=False)
    judge_agreement_rate: Mapped[float] = mapped_column(Float, nullable=False)
    inter_judge_kappa: Mapped[float] = mapped_column(Float, nullable=False)
    cost_usd: Mapped[float] = mapped_column(Float, nullable=False)
    gpu_seconds: Mapped[float] = mapped_column(Float, nullable=False)
    p50_latency_ms: Mapped[float] = mapped_column(Float, nullable=False)
    p95_latency_ms: Mapped[float] = mapped_column(Float, nullable=False)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)


class EvalTestCase(Base):
    __tablename__ = "eval_test_cases"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    test_set_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    input_query: Mapped[str] = mapped_column(Text, nullable=False)
    input_document_ids: Mapped[list[uuid.UUID]] = mapped_column(ARRAY(UUID(as_uuid=True)), nullable=False)
    expected_output = mapped_column(JSON, nullable=False)
    adversarial: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    created_by: Mapped[str] = mapped_column(String(64), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow, nullable=False)


class EvalResult(Base):
    __tablename__ = "eval_results"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    eval_run_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("eval_runs.id", ondelete="CASCADE"), nullable=False, index=True
    )
    test_case_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("eval_test_cases.id", ondelete="CASCADE"), nullable=False, index=True
    )
    model_output = mapped_column(JSON, nullable=False)
    factuality_pass: Mapped[bool] = mapped_column(Boolean, nullable=False)
    citation_pass: Mapped[bool] = mapped_column(Boolean, nullable=False)
    llm_judge_score: Mapped[float] = mapped_column(Float, nullable=False)
    llm_judge_reasoning: Mapped[str] = mapped_column(Text, nullable=False)
