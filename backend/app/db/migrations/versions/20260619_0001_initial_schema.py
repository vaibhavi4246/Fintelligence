"""initial schema

Revision ID: 20260619_0001
Revises:
Create Date: 2026-06-19 00:00:00

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from pgvector.sqlalchemy import Vector
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "20260619_0001"
down_revision: Union[str, Sequence[str], None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


processing_status_enum = postgresql.ENUM(
    "pending", "processing", "completed", "failed", name="processing_status_enum", create_type=False
)
claim_type_enum = postgresql.ENUM("fact", "risk", "contradiction", name="claim_type_enum", create_type=False)
contradiction_type_enum = postgresql.ENUM(
    "FACTUAL_CONTRADICTION", "EXPLAINED_CHANGE", "RESTATEMENT", name="contradiction_type_enum", create_type=False
)
severity_enum = postgresql.ENUM("low", "medium", "high", name="severity_enum", create_type=False)
risk_severity_enum = postgresql.ENUM("low", "medium", "high", name="risk_severity_enum", create_type=False)
edge_type_enum = postgresql.ENUM(
    "SAME_METRIC", "CONTRADICTS", "EXPLAINS", "RESTATES", "ALIAS_OF", name="edge_type_enum", create_type=False
)


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")

    processing_status_enum.create(op.get_bind(), checkfirst=True)
    claim_type_enum.create(op.get_bind(), checkfirst=True)
    contradiction_type_enum.create(op.get_bind(), checkfirst=True)
    severity_enum.create(op.get_bind(), checkfirst=True)
    risk_severity_enum.create(op.get_bind(), checkfirst=True)
    edge_type_enum.create(op.get_bind(), checkfirst=True)

    op.create_table(
        "documents",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("ticker", sa.String(length=20), nullable=False),
        sa.Column("filing_type", sa.String(length=32), nullable=False),
        sa.Column("fiscal_period", sa.String(length=16), nullable=False),
        sa.Column("fiscal_year", sa.Integer(), nullable=False),
        sa.Column("source_url", sa.Text(), nullable=False),
        sa.Column("ingested_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("chunk_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("processing_status", processing_status_enum, nullable=False, server_default="pending"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_documents_ticker"), "documents", ["ticker"], unique=False)

    op.create_table(
        "chunks",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("document_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("chunk_index", sa.Integer(), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("embedding", Vector(dim=768), nullable=False),
        sa.Column("section_label", sa.String(length=128), nullable=True),
        sa.Column("page_number", sa.Integer(), nullable=True),
        sa.ForeignKeyConstraint(["document_id"], ["documents.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_chunks_document_id"), "chunks", ["document_id"], unique=False)

    op.create_table(
        "intelligence_reports",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("query_id", sa.String(length=128), nullable=False),
        sa.Column("document_ids", postgresql.ARRAY(postgresql.UUID(as_uuid=True)), nullable=False),
        sa.Column("model_version", sa.String(length=64), nullable=False),
        sa.Column("generated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("structured_output", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("overall_confidence", sa.Float(), nullable=False),
        sa.Column("contradiction_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("risk_signal_count", sa.Integer(), nullable=False, server_default="0"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_intelligence_reports_query_id"), "intelligence_reports", ["query_id"], unique=False)

    op.create_table(
        "claims",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("report_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("claim_text", sa.Text(), nullable=False),
        sa.Column("claim_type", claim_type_enum, nullable=False),
        sa.Column("confidence_score", sa.Float(), nullable=False),
        sa.Column("supporting_chunk_ids", postgresql.ARRAY(postgresql.UUID(as_uuid=True)), nullable=False),
        sa.Column("cited_document_ids", postgresql.ARRAY(postgresql.UUID(as_uuid=True)), nullable=False),
        sa.Column("verified", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.ForeignKeyConstraint(["report_id"], ["intelligence_reports.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_claims_report_id"), "claims", ["report_id"], unique=False)

    op.create_table(
        "contradictions",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("report_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("claim_a_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("claim_b_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("document_a_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("document_b_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("period_a", sa.String(length=16), nullable=False),
        sa.Column("period_b", sa.String(length=16), nullable=False),
        sa.Column("contradiction_type", contradiction_type_enum, nullable=False),
        sa.Column("stated_cause", sa.Text(), nullable=True),
        sa.Column("restatement_source", sa.Text(), nullable=True),
        sa.Column("severity", severity_enum, nullable=False),
        sa.Column("explanation", sa.Text(), nullable=False),
        sa.ForeignKeyConstraint(["claim_a_id"], ["claims.id"]),
        sa.ForeignKeyConstraint(["claim_b_id"], ["claims.id"]),
        sa.ForeignKeyConstraint(["document_a_id"], ["documents.id"]),
        sa.ForeignKeyConstraint(["document_b_id"], ["documents.id"]),
        sa.ForeignKeyConstraint(["report_id"], ["intelligence_reports.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_contradictions_report_id"), "contradictions", ["report_id"], unique=False)

    op.create_table(
        "risk_signals",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("report_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("signal_text", sa.Text(), nullable=False),
        sa.Column("taxonomy_category", sa.String(length=64), nullable=False),
        sa.Column("severity", risk_severity_enum, nullable=False),
        sa.Column("source_chunk_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("confidence_score", sa.Float(), nullable=False),
        sa.ForeignKeyConstraint(["report_id"], ["intelligence_reports.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["source_chunk_id"], ["chunks.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_risk_signals_report_id"), "risk_signals", ["report_id"], unique=False)

    op.create_table(
        "claim_nodes",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("ticker", sa.String(length=20), nullable=False),
        sa.Column("subject", sa.String(length=255), nullable=False),
        sa.Column("predicate", sa.String(length=255), nullable=False),
        sa.Column("object", sa.Text(), nullable=False),
        sa.Column("period", sa.String(length=16), nullable=False),
        sa.Column("claim_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("canonical_entity_id", sa.String(length=128), nullable=False),
        sa.ForeignKeyConstraint(["claim_id"], ["claims.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_claim_nodes_canonical_entity_id"), "claim_nodes", ["canonical_entity_id"], unique=False)
    op.create_index(op.f("ix_claim_nodes_ticker"), "claim_nodes", ["ticker"], unique=False)

    op.create_table(
        "claim_edges",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("source_node_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("target_node_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("edge_type", edge_type_enum, nullable=False),
        sa.Column("weight", sa.Float(), nullable=False, server_default="1.0"),
        sa.Column("period_delta", sa.Integer(), nullable=False, server_default="0"),
        sa.ForeignKeyConstraint(["source_node_id"], ["claim_nodes.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["target_node_id"], ["claim_nodes.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_table(
        "eval_runs",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("model_version", sa.String(length=64), nullable=False),
        sa.Column("run_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("test_set_id", sa.String(length=64), nullable=False),
        sa.Column("factuality_score", sa.Float(), nullable=False),
        sa.Column("citation_accuracy", sa.Float(), nullable=False),
        sa.Column("calibration_score", sa.Float(), nullable=False),
        sa.Column("contradiction_precision", sa.Float(), nullable=False),
        sa.Column("contradiction_recall", sa.Float(), nullable=False),
        sa.Column("precision_ci_low", sa.Float(), nullable=False),
        sa.Column("precision_ci_high", sa.Float(), nullable=False),
        sa.Column("extractor_model", sa.String(length=128), nullable=False),
        sa.Column("judge_model", sa.String(length=128), nullable=False),
        sa.Column("judge_agreement_rate", sa.Float(), nullable=False),
        sa.Column("inter_judge_kappa", sa.Float(), nullable=False),
        sa.Column("cost_usd", sa.Float(), nullable=False),
        sa.Column("gpu_seconds", sa.Float(), nullable=False),
        sa.Column("p50_latency_ms", sa.Float(), nullable=False),
        sa.Column("p95_latency_ms", sa.Float(), nullable=False),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_table(
        "eval_test_cases",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("test_set_id", sa.String(length=64), nullable=False),
        sa.Column("input_query", sa.Text(), nullable=False),
        sa.Column("input_document_ids", postgresql.ARRAY(postgresql.UUID(as_uuid=True)), nullable=False),
        sa.Column("expected_output", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("adversarial", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("created_by", sa.String(length=64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_eval_test_cases_test_set_id"), "eval_test_cases", ["test_set_id"], unique=False)

    op.create_table(
        "eval_results",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("eval_run_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("test_case_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("model_output", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("factuality_pass", sa.Boolean(), nullable=False),
        sa.Column("citation_pass", sa.Boolean(), nullable=False),
        sa.Column("llm_judge_score", sa.Float(), nullable=False),
        sa.Column("llm_judge_reasoning", sa.Text(), nullable=False),
        sa.ForeignKeyConstraint(["eval_run_id"], ["eval_runs.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["test_case_id"], ["eval_test_cases.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_eval_results_eval_run_id"), "eval_results", ["eval_run_id"], unique=False)
    op.create_index(op.f("ix_eval_results_test_case_id"), "eval_results", ["test_case_id"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_eval_results_test_case_id"), table_name="eval_results")
    op.drop_index(op.f("ix_eval_results_eval_run_id"), table_name="eval_results")
    op.drop_table("eval_results")

    op.drop_index(op.f("ix_eval_test_cases_test_set_id"), table_name="eval_test_cases")
    op.drop_table("eval_test_cases")

    op.drop_table("eval_runs")

    op.drop_table("claim_edges")

    op.drop_index(op.f("ix_claim_nodes_ticker"), table_name="claim_nodes")
    op.drop_index(op.f("ix_claim_nodes_canonical_entity_id"), table_name="claim_nodes")
    op.drop_table("claim_nodes")

    op.drop_index(op.f("ix_risk_signals_report_id"), table_name="risk_signals")
    op.drop_table("risk_signals")

    op.drop_index(op.f("ix_contradictions_report_id"), table_name="contradictions")
    op.drop_table("contradictions")

    op.drop_index(op.f("ix_claims_report_id"), table_name="claims")
    op.drop_table("claims")

    op.drop_index(op.f("ix_intelligence_reports_query_id"), table_name="intelligence_reports")
    op.drop_table("intelligence_reports")

    op.drop_index(op.f("ix_chunks_document_id"), table_name="chunks")
    op.drop_table("chunks")

    op.drop_index(op.f("ix_documents_ticker"), table_name="documents")
    op.drop_table("documents")

    edge_type_enum.drop(op.get_bind(), checkfirst=True)
    risk_severity_enum.drop(op.get_bind(), checkfirst=True)
    severity_enum.drop(op.get_bind(), checkfirst=True)
    contradiction_type_enum.drop(op.get_bind(), checkfirst=True)
    claim_type_enum.drop(op.get_bind(), checkfirst=True)
    processing_status_enum.drop(op.get_bind(), checkfirst=True)
