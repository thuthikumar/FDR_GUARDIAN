"""Safe document metadata and read-only extraction response schemas."""

from datetime import datetime
from decimal import Decimal
from typing import Literal
from uuid import UUID

from pydantic import BaseModel


class DocumentMetadata(BaseModel):
    id: UUID
    fdr_record_id: UUID
    document_type: str
    original_filename: str
    file_size: int
    uploaded_by_name: str
    uploaded_at: datetime
    processing_status: str
    processing_error_code: str | None
    processing_started_at: datetime | None
    processed_at: datetime | None
    page_count: int | None
    ocr_engine: str | None
    extraction_method: str | None


class DocumentPage(BaseModel):
    items: list[DocumentMetadata]


class ExtractedFieldView(BaseModel):
    field_name: str
    extracted_value: str | None
    confidence_score: Decimal | None
    extraction_method: str | None
    source_page: int | None
    stored_value: str | None
    comparison: Literal["matches", "differs", "not_comparable", "not_extracted"]


class DocumentExtractionResponse(BaseModel):
    document_id: UUID
    notice: str = "Machine-extracted and unreviewed. OCR output does not confirm that a document is genuine."
    fields: list[ExtractedFieldView]
