"""Private document upload, download, processing state, and extraction APIs."""

from __future__ import annotations

from pathlib import Path
from urllib.parse import quote
from uuid import UUID

from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, UploadFile, status
from fastapi.responses import StreamingResponse
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.api.dependencies import require_permission
from app.core.permissions import Permission
from app.core.config import max_documents_per_fdr
from app.db.session import get_session
from app.models.documents import Document, ExtractedField
from app.models.enums import DocumentType, ReviewStatus
from app.models.fdr import FDRRecord
from app.models.users import User
from app.schemas.documents import DocumentExtractionResponse, DocumentMetadata, DocumentPage, ExtractedFieldView
from app.services.audit import write_audit_event
from app.services.document_processing import CONFIGURED_FIELDS, enqueue_document, normalize_amount, normalize_date, normalize_interest
from app.services.document_storage import LocalPrivateStorage, UploadValidationError
from app.services.institution_access import get_accessible_fdr, scope_fdr_query

router = APIRouter(tags=["documents"])
CONTENT_TYPES = {".pdf": "application/pdf", ".png": "image/png", ".jpg": "image/jpeg"}


def _accessible_document(session: Session, user: User, document_id: UUID):
    statement = select(Document, FDRRecord, User).join(FDRRecord, FDRRecord.id == Document.fdr_record_id).join(
        User, User.id == Document.uploaded_by)
    row = session.execute(scope_fdr_query(statement, user).where(Document.id == document_id)).first()
    if row is None:
        raise HTTPException(status_code=404, detail="Document not found")
    return row


def _metadata(document: Document, uploader: User) -> DocumentMetadata:
    return DocumentMetadata(id=document.id, fdr_record_id=document.fdr_record_id,
        document_type=document.document_type, original_filename=document.original_filename,
        file_size=document.file_size, uploaded_by_name=uploader.full_name, uploaded_at=document.uploaded_at,
        processing_status=document.processing_status, processing_error_code=document.processing_error_code,
        processing_started_at=document.processing_started_at, processed_at=document.processed_at,
        page_count=document.page_count, ocr_engine=document.ocr_engine, extraction_method=document.extraction_method)


def _display_filename(value: str | None) -> str:
    import ntpath
    name = ntpath.basename((value or "document").replace("\x00", ""))
    name = "".join(char for char in name if ord(char) >= 32 and ord(char) != 127).strip()[:255]
    return name or "document"


@router.post("/fdrs/{fdr_id}/documents", response_model=DocumentMetadata, status_code=status.HTTP_202_ACCEPTED)
def upload_document(fdr_id: UUID, request: Request, file: UploadFile = File(...),
    document_type: DocumentType = Form(...), actor: User = Depends(require_permission(Permission.DOCUMENT_UPLOAD)),
    session: Session = Depends(get_session)) -> DocumentMetadata:
    record = get_accessible_fdr(session, actor, fdr_id)
    record = session.scalar(select(FDRRecord).where(FDRRecord.id == record.id).with_for_update())
    count = int(session.scalar(select(func.count()).select_from(Document).where(Document.fdr_record_id == record.id)) or 0)
    if count >= max_documents_per_fdr():
        raise HTTPException(status_code=409, detail="This FDR has reached its document limit.")
    storage, stored = LocalPrivateStorage(), None
    try:
        stored = storage.save(file.file, file.filename or "", file.content_type or "")
        duplicate = session.scalar(select(Document.id).where(Document.fdr_record_id == record.id,
            Document.checksum == stored.sha256).limit(1))
        if duplicate:
            storage._discard_uncommitted(stored.key)
            raise HTTPException(status_code=409, detail="An identical file is already attached to this FDR.")
        document = Document(fdr_record_id=record.id, document_type=document_type.value,
            private_storage_key=stored.key, original_filename=_display_filename(file.filename),
            content_type=stored.content_type, file_size=stored.size, checksum=stored.sha256,
            uploaded_by=actor.id, processing_status="queued", review_status=ReviewStatus.PENDING.value,
            page_count=stored.page_count)
        session.add(document)
        session.flush()
        write_audit_event(session, request, action="document_uploaded", entity_type="document", entity_id=document.id,
            actor_id=actor.id, change_summary={"fdr_record_id": str(record.id), "document_type": document_type.value,
                "file_size": stored.size, "sha256": stored.sha256, "status": "queued"})
        response = _metadata(document, actor)
        session.commit()
    except UploadValidationError as exc:
        session.rollback()
        if stored:
            storage._discard_uncommitted(stored.key)
        raise HTTPException(status_code=exc.status_code, detail=exc.message) from None
    except HTTPException:
        session.rollback()
        raise
    except Exception:
        session.rollback()
        if stored:
            storage._discard_uncommitted(stored.key)
        raise
    finally:
        file.file.close()
    enqueue_document(document.id)
    return response


@router.get("/fdrs/{fdr_id}/documents", response_model=DocumentPage)
def list_documents(fdr_id: UUID, actor: User = Depends(require_permission(Permission.DOCUMENT_READ)),
                   session: Session = Depends(get_session)) -> DocumentPage:
    get_accessible_fdr(session, actor, fdr_id)
    rows = session.execute(select(Document, User).join(User, User.id == Document.uploaded_by).where(
        Document.fdr_record_id == fdr_id).order_by(Document.uploaded_at.desc(), Document.id)).all()
    return DocumentPage(items=[_metadata(document, uploader) for document, uploader in rows])


@router.get("/documents/{document_id}", response_model=DocumentMetadata)
def get_document(document_id: UUID, actor: User = Depends(require_permission(Permission.DOCUMENT_READ)),
                 session: Session = Depends(get_session)) -> DocumentMetadata:
    document, _record, uploader = _accessible_document(session, actor, document_id)
    return _metadata(document, uploader)


@router.get("/documents/{document_id}/download")
def download_document(document_id: UUID, request: Request,
    actor: User = Depends(require_permission(Permission.DOCUMENT_READ)), session: Session = Depends(get_session)):
    document, _record, _uploader = _accessible_document(session, actor, document_id)
    storage = LocalPrivateStorage()
    if not storage.exists(document.private_storage_key):
        raise HTTPException(status_code=404, detail="Document file not found")
    write_audit_event(session, request, action="document_downloaded", entity_type="document", entity_id=document.id,
        actor_id=actor.id, change_summary={"document_type": document.document_type,
            "file_size": document.file_size, "sha256": document.checksum, "status": document.processing_status})
    session.commit()
    try:
        source = storage.open(document.private_storage_key)
    except (OSError, ValueError):
        raise HTTPException(status_code=404, detail="Document file not found") from None

    def stream_file():
        with source:
            while chunk := source.read(64 * 1024):
                yield chunk
    suffix = Path(document.private_storage_key).suffix.lower()
    return StreamingResponse(stream_file(), media_type=CONTENT_TYPES[suffix], headers={
        "Content-Disposition": f"attachment; filename*=UTF-8''{quote(document.original_filename, safe='')}",
        "X-Content-Type-Options": "nosniff", "Cache-Control": "private, no-store"})


def _stored_value(record: FDRRecord, field: str) -> str | None:
    if field == "interest_rate":
        return None
    value = getattr(record, field, None)
    if value is None:
        return None
    return value.isoformat() if hasattr(value, "isoformat") else str(value)


def _compare(field: str, extracted: str | None, stored: str | None) -> str:
    if extracted is None or not extracted.strip():
        return "not_extracted"
    if stored is None:
        return "not_comparable"
    if field == "amount":
        left, right = normalize_amount(extracted), normalize_amount(stored)
    elif field in {"issue_date", "maturity_date"}:
        left, right = normalize_date(extracted), normalize_date(stored)
    elif field == "interest_rate":
        left, right = normalize_interest(extracted), normalize_interest(stored)
    else:
        left, right = " ".join(extracted.casefold().split()), " ".join(stored.casefold().split())
    if left is None or right is None:
        return "not_comparable"
    return "matches" if left == right else "differs"


@router.get("/documents/{document_id}/extraction", response_model=DocumentExtractionResponse)
def get_extraction(document_id: UUID, actor: User = Depends(require_permission(Permission.DOCUMENT_READ)),
                   session: Session = Depends(get_session)) -> DocumentExtractionResponse:
    document, record, _uploader = _accessible_document(session, actor, document_id)
    rows = {row.field_name: row for row in session.scalars(select(ExtractedField).where(
        ExtractedField.document_id == document.id))}
    fields = []
    for name in CONFIGURED_FIELDS:
        row = rows.get(name)
        extracted = row.extracted_value if row else None
        stored = _stored_value(record, name)
        fields.append(ExtractedFieldView(field_name=name, extracted_value=extracted,
            confidence_score=row.confidence_score if row else None,
            extraction_method=row.extraction_method if row else None, source_page=row.source_page if row else None,
            stored_value=stored, comparison=_compare(name, extracted, stored)))
    return DocumentExtractionResponse(document_id=document.id, fields=fields)


@router.post("/documents/{document_id}/reprocess", response_model=DocumentMetadata, status_code=status.HTTP_202_ACCEPTED)
def reprocess_document(document_id: UUID, request: Request,
    actor: User = Depends(require_permission(Permission.DOCUMENT_REPROCESS)), session: Session = Depends(get_session)) -> DocumentMetadata:
    document, _record, uploader = _accessible_document(session, actor, document_id)
    reviewed = session.scalar(select(ExtractedField.id).where(ExtractedField.document_id == document.id,
        ExtractedField.reviewer_confirmed_value.is_not(None)).limit(1))
    if reviewed:
        raise HTTPException(status_code=409, detail="This document has reviewer-confirmed values and cannot be reprocessed.")
    document.processing_status = "queued"
    document.processing_error_code = None
    document.processing_started_at = None
    document.processed_at = None
    write_audit_event(session, request, action="document_reprocess_queued", entity_type="document", entity_id=document.id,
        actor_id=actor.id, change_summary={"status": "queued"})
    response = _metadata(document, uploader)
    session.commit()
    enqueue_document(document.id)
    return response
