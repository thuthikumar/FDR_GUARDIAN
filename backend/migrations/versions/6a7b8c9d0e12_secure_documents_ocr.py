"""Add private document processing metadata and extraction provenance."""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "6a7b8c9d0e12"
down_revision: Union[str, Sequence[str], None] = "5d6e7f8a9b10"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.drop_constraint(op.f("ck_documents_document_type_valid"), "documents", type_="check")
    op.drop_constraint(op.f("ck_documents_processing_status_valid"), "documents", type_="check")
    op.execute("UPDATE documents SET document_type='bank_confirmation_letter' WHERE document_type='bank_confirmation'")
    op.execute("UPDATE documents SET document_type='other' WHERE document_type='supporting_document'")
    op.execute("UPDATE documents SET processing_status='uploaded' WHERE processing_status='pending'")
    op.execute("UPDATE documents SET processing_status='processed' WHERE processing_status='completed'")
    op.create_check_constraint("document_type_valid", "documents",
        "document_type IN ('fdr_certificate', 'bank_confirmation_letter', 'institution_request_letter', 'other')")
    op.create_check_constraint("processing_status_valid", "documents",
        "processing_status IN ('uploaded', 'queued', 'processing', 'processed', 'failed', 'ocr_unavailable')")
    op.add_column("documents", sa.Column("processing_error_code", sa.String(40), nullable=True))
    op.add_column("documents", sa.Column("processing_started_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("documents", sa.Column("processed_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("documents", sa.Column("page_count", sa.Integer(), nullable=True))
    op.add_column("documents", sa.Column("ocr_engine", sa.String(120), nullable=True))
    op.add_column("documents", sa.Column("extraction_method", sa.String(32), nullable=True))
    op.create_check_constraint("processing_error_code_safe", "documents",
        "processing_error_code IS NULL OR processing_error_code ~ '^[a-z0-9_]{1,40}$'")
    op.create_check_constraint("page_count_positive", "documents", "page_count IS NULL OR page_count >= 1")

    op.add_column("extracted_fields", sa.Column("source_page", sa.Integer(), nullable=True))
    op.create_check_constraint("extraction_method_valid", "extracted_fields",
        "extraction_method IN ('ocr', 'pdf_text_layer', 'synthetic_fixture')")
    op.create_check_constraint("source_page_positive", "extracted_fields", "source_page IS NULL OR source_page >= 1")


def downgrade() -> None:
    op.drop_constraint(op.f("ck_extracted_fields_source_page_positive"), "extracted_fields", type_="check")
    op.drop_constraint(op.f("ck_extracted_fields_extraction_method_valid"), "extracted_fields", type_="check")
    op.drop_column("extracted_fields", "source_page")
    op.drop_constraint(op.f("ck_documents_page_count_positive"), "documents", type_="check")
    op.drop_constraint(op.f("ck_documents_processing_error_code_safe"), "documents", type_="check")
    for column in ("extraction_method", "ocr_engine", "page_count", "processed_at", "processing_started_at", "processing_error_code"):
        op.drop_column("documents", column)
    op.drop_constraint(op.f("ck_documents_processing_status_valid"), "documents", type_="check")
    op.drop_constraint(op.f("ck_documents_document_type_valid"), "documents", type_="check")
    op.execute("UPDATE documents SET document_type='bank_confirmation' WHERE document_type='bank_confirmation_letter'")
    op.execute("UPDATE documents SET document_type='supporting_document' WHERE document_type IN ('institution_request_letter', 'other')")
    op.execute("UPDATE documents SET processing_status='failed' WHERE processing_status='ocr_unavailable'")
    op.execute("UPDATE documents SET processing_status='completed' WHERE processing_status='processed'")
    op.execute("UPDATE documents SET processing_status='pending' WHERE processing_status='uploaded'")
    op.create_check_constraint("document_type_valid", "documents",
        "document_type IN ('fdr_certificate', 'bank_confirmation', 'supporting_document')")
    op.create_check_constraint("processing_status_valid", "documents",
        "processing_status IN ('pending', 'queued', 'processing', 'completed', 'failed')")
