from __future__ import annotations

import io
import logging
import random
from datetime import date, timedelta
from decimal import Decimal
from pathlib import Path
from uuid import uuid4

import pytest
from PIL import Image, ImageDraw, ImageFilter, ImageFont
from reportlab.lib.pagesizes import letter
from reportlab.lib.utils import ImageReader
from reportlab.pdfgen import canvas
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.security import create_access_token
from app.main import app
from app.models.documents import Document, ExtractedField
from app.models.enums import (DocumentType, FDRRecordStatus, InstitutionStatus, ReviewStatus,
                              UserRole, VerificationStatus)
from app.models.fdr import FDRRecord
from app.models.institutions import Institution
from app.models.monitoring import Alert, AuditEvent
from app.models.users import User
from app.services import document_processing as processing
from app.services.document_processing import (CONFIGURED_FIELDS, Candidate, PageText, TextLine,
    extract_candidates, normalize_amount, normalize_date, normalize_interest, process_document, stale_processing_count)
from app.services.document_storage import LocalPrivateStorage, UploadValidationError


def pdf_bytes(lines: tuple[str, ...] = ("SYNTHETIC SAMPLE - NOT A REAL DOCUMENT", "FDR Number: SYN-TEST-1001"), *, pages: int = 1, password=None) -> bytes:
    stream = io.BytesIO()
    document = canvas.Canvas(stream, pagesize=letter, encrypt=password)
    for page in range(pages):
        for index, line in enumerate(lines):
            document.drawString(40, 750 - index * 20, line)
        document.showPage()
    document.save()
    return stream.getvalue()


def image_bytes(kind: str = "PNG", size=(500, 300), text_lines: tuple[str, ...] = ()) -> bytes:
    stream = io.BytesIO()
    image = Image.new("RGB", size, "white")
    draw = ImageDraw.Draw(image)
    draw.text((15, 15), "SYNTHETIC SAMPLE - NOT A REAL DOCUMENT", fill="black")
    for index, line in enumerate(text_lines):
        draw.text((15, 55 + index * 24), line, fill="black")
    image.save(stream, format=kind)
    return stream.getvalue()


def add_context(session: Session, role: str = UserRole.INSTITUTION_ADMIN.value, *, institution=None):
    if institution is None:
        institution = Institution(institution_code=f"DOC-{uuid4().hex[:8]}", institution_name="Synthetic Document Institution",
            status=InstitutionStatus.ACTIVE.value, is_synthetic=True)
        session.add(institution)
        session.flush()
    user = User(email=f"doc-{uuid4().hex}@synthetic.invalid", full_name="Synthetic Document User", role=role,
        institution_id=institution.id if role == UserRole.INSTITUTION_ADMIN.value else None,
        is_active=True, is_synthetic=True)
    session.add(user)
    session.flush()
    record = FDRRecord(institution_id=institution.id, internal_fdr_id=f"DOC-FDR-{uuid4().hex[:10]}",
        bank_name="Synthetic Community Bank 01", branch_name="Synthetic Branch 001", fdr_number="SYN-TEST-1001",
        amount=Decimal("500000.00"), currency="INR", issue_date=date(2024, 1, 1), maturity_date=date(2027, 1, 1),
        record_status=FDRRecordStatus.ACTIVE.value, verification_status=VerificationStatus.NOT_SUBMITTED.value,
        source_system="SYNTHETIC_TEST", is_synthetic=True)
    session.add(record)
    session.flush()
    session.commit()
    return institution, user, record


def auth(user: User):
    return {"Authorization": f"Bearer {create_access_token(user.id)}"}


def uploaded(client, headers, *, name="certificate.pdf", content=None, content_type="application/pdf"):
    return client.post("/api/v1/fdrs/current/documents", headers=headers,
        data={"document_type": "fdr_certificate"},
        files={"file": (name, content if content is not None else pdf_bytes(), content_type)})


def add_document(session: Session, record: FDRRecord, user: User, *, content=None, filename="stored.pdf", status="processed"):
    content = content or pdf_bytes()
    content_type="application/pdf"
    if content.startswith(b"\x89PNG"):
        content_type, filename="image/png", filename.replace(".pdf",".png")
    elif content.startswith(b"\xff\xd8\xff"):
        content_type, filename="image/jpeg", filename.replace(".pdf",".jpg")
    storage = LocalPrivateStorage()
    stored = storage.save(io.BytesIO(content), filename, content_type)
    row = Document(fdr_record_id=record.id, document_type=DocumentType.FDR_CERTIFICATE.value,
        private_storage_key=stored.key, original_filename=filename, content_type=stored.content_type,
        file_size=stored.size, checksum=stored.sha256, uploaded_by=user.id, processing_status=status,
        review_status=ReviewStatus.PENDING.value, page_count=stored.page_count)
    session.add(row)
    session.flush()
    return row


class FakeOcr:
    def __init__(self, lines=None):
        self.lines = tuple(lines or (TextLine("FDR Number: SYN-TEST-1001", ("FDR", "Number:", "SYN-TEST-1001"), (95, 90, 88)),
            TextLine("Bank Name: Synthetic Community Bank 01", ("Bank", "Name:", "Synthetic", "Community", "Bank", "01"), (95, 95, 90, 90, 90, 88)),
            TextLine("Amount: INR 5,00,000.00", ("Amount:", "INR", "5,00,000.00"), (95, 95, 90)),
            TextLine("Maturity Date: 01/01/2027", ("Maturity", "Date:", "01/01/2027"), (95, 95, 90))))

    def version(self):
        return "fake 1.0"

    def recognize(self, image):
        return self.lines


def test_storage_key_resolver_rejects_escape_paths(tmp_path):
    storage = LocalPrivateStorage(tmp_path)
    for key in ("../x.pdf", "aa/../../x.pdf", str(tmp_path / "x.pdf"), "aa/bb/not-an-id.pdf"):
        with pytest.raises(ValueError):
            storage.resolve(key)


@pytest.mark.parametrize("name,ctype,content", [
    ("a.png", "image/png", pdf_bytes()),
    ("a.pdf", "image/png", pdf_bytes()),
    ("a.pdf", "application/pdf", b"#!/bin/sh\necho bad"),
    ("a.exe.pdf", "application/pdf", b"MZ\x00\x00script"),
    ("a.txt", "text/plain", b"plain text"),
])
def test_upload_rejects_type_disagreement_and_scripts(api_client, db_session, monkeypatch, name, ctype, content):
    _, user, record = add_context(db_session)
    monkeypatch.setattr("app.api.documents.enqueue_document", lambda _id: None)
    response = api_client.post(f"/api/v1/fdrs/{record.id}/documents", headers=auth(user),
        data={"document_type": "fdr_certificate"}, files={"file": (name, content, ctype)})
    assert response.status_code in (415, 422)
    assert list(Path(__import__("os").environ["STORAGE_ROOT"]).rglob(".upload-*")) == []


@pytest.mark.parametrize("kind",["empty","oversize"])
def test_upload_empty_oversize_cleans_partial_file(api_client, db_session, monkeypatch, kind):
    _, user, record = add_context(db_session)
    monkeypatch.setattr("app.api.documents.enqueue_document", lambda _id: None)
    if kind == "oversize": monkeypatch.setattr("app.services.document_storage.max_upload_bytes", lambda: 100)
    payload=("empty.pdf",b"","application/pdf") if kind=="empty" else ("large.pdf",pdf_bytes(),"application/pdf")
    response = api_client.post(f"/api/v1/fdrs/{record.id}/documents", headers=auth(user), data={"document_type":"fdr_certificate"}, files={"file":payload})
    assert response.status_code == (422 if kind=="empty" else 413)
    root=Path(__import__("os").environ["STORAGE_ROOT"])
    assert not list(root.rglob(".upload-*")) and not [path for path in root.rglob("*.pdf")]


@pytest.mark.parametrize("kind",["encrypted","pages","pixels"])
def test_pdf_encryption_page_limit_and_image_pixel_limit_are_safe(api_client, db_session, monkeypatch, kind):
    _, user, record = add_context(db_session)
    monkeypatch.setattr("app.api.documents.enqueue_document", lambda _id: None)
    if kind=="encrypted":
        response=api_client.post(f"/api/v1/fdrs/{record.id}/documents",headers=auth(user),data={"document_type":"fdr_certificate"},files={"file":("e.pdf",pdf_bytes(password="secret"),"application/pdf")})
        assert response.status_code == 422 and response.json()["detail"] == "The PDF is encrypted or cannot be read."
    elif kind=="pages":
        monkeypatch.setenv("MAX_PDF_PAGES","1")
        response=api_client.post(f"/api/v1/fdrs/{record.id}/documents",headers=auth(user),data={"document_type":"fdr_certificate"},files={"file":("many.pdf",pdf_bytes(pages=2),"application/pdf")})
        assert response.status_code == 422 and "page limit" in response.json()["detail"]
    else:
        payload=image_bytes(size=(20,20))
        monkeypatch.setattr("app.services.document_storage.MAX_IMAGE_PIXELS",100)
        monkeypatch.setattr(Image,"MAX_IMAGE_PIXELS",100)
        response=api_client.post(f"/api/v1/fdrs/{record.id}/documents",headers=auth(user),data={"document_type":"fdr_certificate"},files={"file":("large.png",payload,"image/png")})
        assert response.status_code == 422 and "dimensions" in response.json()["detail"]


def test_upload_types_sanitization_duplicate_and_safe_response(api_client, db_session, monkeypatch):
    _, user, record = add_context(db_session)
    monkeypatch.setattr("app.api.documents.enqueue_document", lambda _id: None)
    api_url=f"/api/v1/fdrs/{record.id}/documents"
    content=pdf_bytes()
    response=api_client.post(api_url,headers=auth(user),data={"document_type":"fdr_certificate"},files={"file":("../../synthetic-certificate.pdf",content,"application/pdf")})
    assert response.status_code == 202
    body=response.json()
    assert body["original_filename"] == "synthetic-certificate.pdf"
    assert body["processing_status"] == "queued"
    assert "storage_key" not in str(body).lower() and "storage" not in str(body).lower()
    assert db_session.scalar(select(AuditEvent).where(AuditEvent.action=="document_uploaded")) is not None
    duplicate=api_client.post(api_url,headers=auth(user),data={"document_type":"fdr_certificate"},files={"file":("different.pdf",content,"application/pdf")})
    assert duplicate.status_code == 409


def test_long_filename_is_display_only(api_client,db_session,monkeypatch):
    _,user,record=add_context(db_session)
    monkeypatch.setattr("app.api.documents.enqueue_document",lambda _id:None)
    long_name="x"*500+".pdf"
    accepted=api_client.post(f"/api/v1/fdrs/{record.id}/documents",headers=auth(user),data={"document_type":"other"},files={"file":(long_name,pdf_bytes(("another unique sample",)),"application/pdf")})
    assert accepted.status_code == 202 and len(accepted.json()["original_filename"]) <= 255
    root=Path(__import__("os").environ["STORAGE_ROOT"]).resolve()
    assert all(path.resolve().is_relative_to(root) for path in root.rglob("*"))


@pytest.mark.parametrize("name,ctype,content",[
    ("valid.pdf","application/pdf",pdf_bytes()),
    ("valid.png","image/png",image_bytes()),
    ("valid.jpg","image/jpeg",image_bytes("JPEG")),
])
def test_valid_pdf_png_jpeg_uploads(api_client,db_session,monkeypatch,name,ctype,content):
    _,user,record=add_context(db_session)
    monkeypatch.setattr("app.api.documents.enqueue_document",lambda _id:None)
    response=api_client.post(f"/api/v1/fdrs/{record.id}/documents",headers=auth(user),data={"document_type":"other"},files={"file":(name,content,ctype)})
    assert response.status_code==202 and response.json()["processing_status"]=="queued"


def test_document_limit_is_enforced(api_client, db_session, monkeypatch):
    _, user, record=add_context(db_session)
    monkeypatch.setattr("app.api.documents.enqueue_document",lambda _id:None)
    monkeypatch.setattr("app.api.documents.max_documents_per_fdr",lambda:1)
    first=api_client.post(f"/api/v1/fdrs/{record.id}/documents",headers=auth(user),data={"document_type":"fdr_certificate"},files={"file":("one.pdf",pdf_bytes(),"application/pdf")})
    second=api_client.post(f"/api/v1/fdrs/{record.id}/documents",headers=auth(user),data={"document_type":"fdr_certificate"},files={"file":("two.pdf",pdf_bytes(("unique two",)),"application/pdf")})
    assert first.status_code == 202 and second.status_code == 409


def test_download_headers_audit_and_no_delete_routes(api_client, db_session, monkeypatch):
    _, user, record=add_context(db_session,UserRole.VERIFICATION_OFFICER.value)
    document=add_document(db_session,record,user,filename="synthetic.pdf")
    api_client.get("/api/v1/auth/me",headers=auth(user))
    response=api_client.get(f"/api/v1/documents/{document.id}/download",headers=auth(user))
    assert response.status_code == 200
    assert response.headers["content-disposition"].startswith("attachment;")
    assert response.headers["x-content-type-options"] == "nosniff"
    assert response.headers["cache-control"] == "private, no-store"
    assert response.content.startswith(b"%PDF-")
    assert db_session.scalar(select(AuditEvent).where(AuditEvent.action=="document_downloaded")) is not None
    paths=app.openapi()["paths"]
    assert not any(path.startswith("/api/v1/documents") and "delete" in methods for path,methods in paths.items())
    assert not any("storage" in path.lower() for path in paths)
    metadata=api_client.get(f"/api/v1/documents/{document.id}",headers=auth(user)).json()
    assert not any("storage" in str(value).lower() for value in metadata.values())


@pytest.mark.parametrize("operation", ["download", "extraction", "reprocess"])
def test_missing_private_file_returns_safe_gone_and_marks_document(api_client, db_session, monkeypatch, tmp_path, operation):
    monkeypatch.setenv("STORAGE_ROOT", str(tmp_path / "private"))
    _, user, record = add_context(db_session, UserRole.VERIFICATION_OFFICER.value)
    document = add_document(db_session, record, user)
    LocalPrivateStorage().resolve(document.private_storage_key).unlink()
    monkeypatch.setattr("app.api.documents.enqueue_document", lambda _id: None)
    if operation == "download":
        response = api_client.get(f"/api/v1/documents/{document.id}/download", headers=auth(user))
    elif operation == "extraction":
        response = api_client.get(f"/api/v1/documents/{document.id}/extraction", headers=auth(user))
    else:
        response = api_client.post(f"/api/v1/documents/{document.id}/reprocess", headers=auth(user))
    assert response.status_code == 410
    assert response.json() == {"detail": "The stored file is no longer available"}
    assert str(tmp_path) not in response.text
    db_session.refresh(document)
    assert document.processing_status == "failed"
    assert document.processing_error_code == "stored_file_missing"


def test_extraction_response_has_all_fields_and_neutral_comparisons(api_client,db_session):
    _, user, record=add_context(db_session,UserRole.READ_ONLY_AUDITOR.value)
    document=add_document(db_session,record,user)
    db_session.add_all([ExtractedField(document_id=document.id,field_name="amount",extracted_value="Rs. 5,00,000.00",confidence_score=Decimal("0.970"),extraction_method="pdf_text_layer"),
        ExtractedField(document_id=document.id,field_name="maturity_date",extracted_value="01 Jan 2028",confidence_score=None,extraction_method="pdf_text_layer")])
    db_session.flush()
    response=api_client.get(f"/api/v1/documents/{document.id}/extraction",headers=auth(user))
    assert response.status_code == 200
    body=response.json()
    assert len(body["fields"]) == len(CONFIGURED_FIELDS)
    assert body["notice"] == "Machine-extracted and unreviewed. OCR output does not confirm that a document is genuine."
    by_name={row["field_name"]:row for row in body["fields"]}
    assert by_name["amount"]["comparison"] == "matches"
    assert by_name["maturity_date"]["comparison"] == "differs"
    assert by_name["fdr_number"]["comparison"] == "not_extracted"
    assert "private_storage_key" not in str(body) and "storage_key" not in str(body)


def test_institution_scope_hides_other_institutions(api_client,db_session,monkeypatch):
    inst_a,user_a,record_a=add_context(db_session)
    inst_b,user_b,record_b=add_context(db_session,UserRole.VERIFICATION_OFFICER.value)
    document=add_document(db_session,record_b,user_b)
    monkeypatch.setattr("app.api.documents.enqueue_document",lambda _id:None)
    base=f"/api/v1/documents/{document.id}"
    assert api_client.get(f"/api/v1/fdrs/{record_b.id}/documents",headers=auth(user_a)).status_code == 404
    assert api_client.get(base,headers=auth(user_a)).status_code == 404
    assert api_client.get(base+"/download",headers=auth(user_a)).status_code == 404
    assert api_client.get(base+"/extraction",headers=auth(user_a)).status_code == 404
    assert api_client.post(f"/api/v1/fdrs/{record_b.id}/documents",headers=auth(user_a),data={"document_type":"other"},files={"file":("x.pdf",pdf_bytes(),"application/pdf")}).status_code == 404
    assert inst_a.id != inst_b.id and record_a.id != record_b.id


@pytest.mark.parametrize("role,upload_status,read_status,reprocess_status",[
    (UserRole.SYSTEM_ADMIN.value,403,403,403),(UserRole.INSTITUTION_ADMIN.value,202,200,403),
    (UserRole.VERIFICATION_OFFICER.value,403,200,202),(UserRole.ACCOUNTS_OFFICER.value,403,403,403),
    (UserRole.FINAL_APPROVER.value,403,200,403),(UserRole.READ_ONLY_AUDITOR.value,403,200,403),
])
def test_document_endpoint_permission_matrix(api_client,db_session,monkeypatch,role,upload_status,read_status,reprocess_status):
    _, user, record=add_context(db_session,role)
    document=add_document(db_session,record,user)
    monkeypatch.setattr("app.api.documents.enqueue_document",lambda _id:None)
    headers=auth(user)
    read=api_client.get(f"/api/v1/documents/{document.id}",headers=headers)
    assert read.status_code==read_status
    extraction=api_client.get(f"/api/v1/documents/{document.id}/extraction",headers=headers)
    assert extraction.status_code==read_status
    download=api_client.get(f"/api/v1/documents/{document.id}/download",headers=headers)
    assert download.status_code==read_status
    upload=api_client.post(f"/api/v1/fdrs/{record.id}/documents",headers=headers,data={"document_type":"other"},files={"file":("upload.pdf",pdf_bytes((f"unique {uuid4()}",)),"application/pdf")})
    assert upload.status_code==upload_status
    listing=api_client.get(f"/api/v1/fdrs/{record.id}/documents",headers=headers)
    assert listing.status_code==read_status
    reprocess=api_client.post(f"/api/v1/documents/{document.id}/reprocess",headers=headers)
    assert reprocess.status_code==reprocess_status


def test_reprocess_blocked_for_reviewed_and_replaces_machine_rows_atomically(api_client,db_session,monkeypatch):
    _, user, record=add_context(db_session,UserRole.VERIFICATION_OFFICER.value)
    document=add_document(db_session,record,user,content=image_bytes())
    field=ExtractedField(document_id=document.id,field_name="bank_name",extracted_value="Old machine value",extraction_method="ocr")
    reviewed=ExtractedField(document_id=document.id,field_name="fdr_number",extracted_value="SYN-TEST-1001",extraction_method="ocr",reviewer_confirmed_value="SYN-TEST-1001",reviewed_by=user.id)
    db_session.add_all([field,reviewed]);db_session.flush()
    blocked=api_client.post(f"/api/v1/documents/{document.id}/reprocess",headers=auth(user))
    assert blocked.status_code==409
    db_session.delete(reviewed);db_session.flush()
    monkeypatch.setattr("app.api.documents.enqueue_document",lambda _id:None)
    queued=api_client.post(f"/api/v1/documents/{document.id}/reprocess",headers=auth(user))
    assert queued.status_code==202 and queued.json()["processing_status"]=="queued"
    assert db_session.scalar(select(AuditEvent).where(AuditEvent.action=="document_reprocess_queued")) is not None
    process_document(document.id,engine=FakeOcr(),session_factory=lambda:Session(db_session.get_bind()),storage=LocalPrivateStorage())
    fields=list(db_session.scalars(select(ExtractedField).where(ExtractedField.document_id==document.id)))
    assert {row.field_name for row in fields}==set(CONFIGURED_FIELDS)
    assert next(row for row in fields if row.field_name=="bank_name").extracted_value=="Synthetic Community Bank 01"
    assert db_session.scalar(select(func.count()).select_from(Alert))==0


def test_pdf_text_layer_has_null_confidence_and_empty_fields_are_recorded(db_engine,caplog):
    with Session(db_engine) as setup:
        _,user,record=add_context(setup,UserRole.VERIFICATION_OFFICER.value)
        document=add_document(setup,record,user,content=pdf_bytes(("FDR Number: SYN-TEST-1001",)))
        setup.commit(); document_id=document.id; record_id=record.id; user_id=user.id
    caplog.set_level(logging.INFO)
    process_document(document_id,session_factory=lambda:Session(db_engine),storage=LocalPrivateStorage())
    with Session(db_engine) as check:
        document=check.get(Document,document_id)
        fields={row.field_name:row for row in check.scalars(select(ExtractedField).where(ExtractedField.document_id==document_id))}
    assert document.processing_status=="processed" and document.extraction_method=="pdf_text_layer"
    assert len(fields)==7 and fields["fdr_number"].confidence_score is None
    assert fields["fdr_number"].source_page==1 and fields["bank_name"].extracted_value is None
    assert "SYN-TEST-1001" not in caplog.text


def test_ocr_fake_engine_confidence_and_disabled_ocr_path(db_engine,monkeypatch):
    with Session(db_engine) as setup:
        _,user,record=add_context(setup,UserRole.VERIFICATION_OFFICER.value)
        document=add_document(setup,record, user,content=image_bytes(text_lines=("FDR Number: SYN-TEST-1001",)))
        setup.commit(); document_id=document.id; record_id=record.id; user_id=user.id
    process_document(document_id,engine=FakeOcr(),session_factory=lambda:Session(db_engine),storage=LocalPrivateStorage())
    with Session(db_engine) as check:
        document=check.get(Document,document_id)
        row=check.scalar(select(ExtractedField).where(ExtractedField.document_id==document.id,ExtractedField.field_name=="fdr_number"))
    assert document.processing_status=="processed" and row.extraction_method=="ocr" and row.confidence_score is not None
    monkeypatch.setenv("OCR_ENABLED","false")
    with Session(db_engine) as setup:
        other=add_document(setup,setup.get(FDRRecord,record_id),setup.get(User,user_id),filename="second.pdf",content=pdf_bytes(()))
        setup.commit(); other_id=other.id
    process_document(other_id,session_factory=lambda:Session(db_engine),storage=LocalPrivateStorage())
    with Session(db_engine) as check: other=check.get(Document,other_id)
    assert other.processing_status=="ocr_unavailable" and other.processing_error_code=="ocr_unavailable"
    with Session(db_engine) as check:
        missing={row.field_name:row for row in check.scalars(select(ExtractedField).where(ExtractedField.document_id==other_id))}
        assert set(missing)==set(CONFIGURED_FIELDS) and all(row.extracted_value is None for row in missing.values())


@pytest.mark.parametrize("raw,expected",[("Rs. 5,00,000.00",Decimal("500000.00")),("INR 500000",Decimal("500000.00")),("₹ 1,25,500.50",Decimal("125500.50")),("garbage",None)])
def test_indian_amount_parser(raw,expected):
    assert normalize_amount(raw)==expected


@pytest.mark.parametrize("raw,expected",[("01/02/2027",date(2027,2,1)),("01-02-2027",date(2027,2,1)),("01 Feb 2027",date(2027,2,1)),("garbage",None)])
def test_tolerant_date_parser(raw,expected):
    assert normalize_date(raw)==expected


def test_interest_parser_and_candidate_extraction():
    assert normalize_interest("7.25 %")==Decimal("7.25") and normalize_interest("x") is None
    lines=(TextLine("Interest Rate: 7.25%"),TextLine("Issue Date: 01 Feb 2025"),TextLine("Maturity Date: 01 Jan 2027"))
    result=extract_candidates((PageText(1,lines),))
    assert result["interest_rate"].value=="7.25%" and result["issue_date"].value=="01 Feb 2025"
    assert result["fdr_number"]==Candidate(None,None,None)
    raw=extract_candidates((PageText(1,(TextLine("Bank Name: Synthetic   Community Bank 01"),)),))
    assert raw["bank_name"].value=="Synthetic   Community Bank 01"


def test_safe_failure_code_and_stale_processing_detection(db_engine):
    with Session(db_engine) as setup:
        _,user,record=add_context(setup,UserRole.VERIFICATION_OFFICER.value)
        document=add_document(setup,record,user,status="processing")
        document.processing_started_at=__import__("datetime").datetime.now().astimezone()-timedelta(minutes=50)
        setup.commit(); stale=document.id; record_id=record.id; user_id=user.id
        assert stale_processing_count(setup)==1

    class Broken(FakeOcr):
        def recognize(self,image):
            raise processing.ProcessingFailure("ocr_timeout")
    with Session(db_engine) as setup:
        image=add_document(setup,setup.get(FDRRecord,record_id),setup.get(User,user_id),filename="broken.png",content=image_bytes(),status="queued")
        setup.commit(); image_id=image.id
    process_document(image_id,engine=Broken(),session_factory=lambda:Session(db_engine),storage=LocalPrivateStorage())
    with Session(db_engine) as check: image=check.get(Document,image_id)
    assert image.processing_status=="failed" and image.processing_error_code=="ocr_timeout"
    assert "raw" not in str(image.processing_error_code)
    assert stale != image.id


def real_ocr_fixture(tmp_path: Path, fixture_kind: str) -> tuple[Path, str]:
    lines=["SYNTHETIC SAMPLE - NOT A REAL DOCUMENT", "FDR Number: SYNTH-FDR-0001",
           "Bank Name: Synthetic Community Bank 01", "Amount: INR 2,35,357.00",
           "Interest Rate: 7.25%", "Maturity Date: 24 Oct 2027"]
    image=Image.new("RGB",(1700,1100),"white")
    draw=ImageDraw.Draw(image);font=ImageFont.load_default(size=40)
    for index,line in enumerate(lines):draw.text((55,50+index*150),line,fill="black",font=font)
    if fixture_kind in {"noisy_jpeg", "lightly_noisy_jpeg"}:
        rng=random.Random(26265);pixels=image.load()
        for _ in range(25000 if fixture_kind=="noisy_jpeg" else 8500):
            x,y=rng.randrange(image.width),rng.randrange(image.height);shade=rng.randrange(160,256);pixels[x,y]=(shade,shade,shade)
        if fixture_kind=="noisy_jpeg":
            image=image.filter(ImageFilter.GaussianBlur(3.0))
        else:
            region=image.crop((40,330,1660,470)).filter(ImageFilter.GaussianBlur(5.0))
            image.paste(region,(40,330))
    if fixture_kind=="blank_image":
        image=Image.new("RGB",(1700,1100),"white");ImageDraw.Draw(image).text((55,50),"SYNTHETIC SAMPLE - NOT A REAL DOCUMENT",fill="black",font=font)
    is_jpeg=fixture_kind in {"noisy_jpeg", "lightly_noisy_jpeg"}
    image_path=tmp_path/("fixture.jpg" if is_jpeg else "fixture.png")
    image.save(image_path,format="JPEG" if is_jpeg else "PNG",quality=8 if fixture_kind=="noisy_jpeg" else 35 if is_jpeg else None)
    if fixture_kind=="image_pdf":
        output=io.BytesIO();doc=canvas.Canvas(output,pagesize=letter);doc.drawImage(ImageReader(image),0,0,width=letter[0],height=letter[1]);doc.save()
        path=tmp_path/"fixture.pdf";path.write_bytes(output.getvalue());return path,"application/pdf"
    return image_path,"image/jpeg" if is_jpeg else "image/png"


@pytest.mark.parametrize("fixture_kind",["image_pdf","png","lightly_noisy_jpeg","noisy_jpeg","blank_image"])
@pytest.mark.skipif(not processing.tesseract_available(),reason="Tesseract binary not installed or unavailable on PATH")
def test_real_tesseract_synthetic_fixture_smoke(fixture_kind,tmp_path):
    path,content_type=real_ocr_fixture(tmp_path,fixture_kind)
    candidates,pages,method,engine=processing._extract(path,content_type,processing.TesseractOcrEngine())
    assert pages==1 and method=="ocr" and engine.startswith("Tesseract ")
    if fixture_kind in {"image_pdf", "png", "lightly_noisy_jpeg"}:
        assert candidates["interest_rate"].value == "7.25%"
    if fixture_kind=="blank_image":
        assert candidates["fdr_number"].value is None
    elif fixture_kind=="noisy_jpeg":
        expected = {"fdr_number": "SYNTH-FDR-0001", "bank_name": "Synthetic Community Bank 01",
                    "branch_name": "Synthetic Branch 001", "amount": "INR 2,35,357.00",
                    "interest_rate": "7.25%", "issue_date": "05 Mar 2024", "maturity_date": "24 Oct 2027"}
        assert any(candidates[field].value is None or candidates[field].confidence is None
                   or candidates[field].confidence < 0.85 for field in expected)
        assert all(candidate.value == expected[field] for field, candidate in candidates.items()
                   if candidate.value and candidate.confidence is not None and candidate.confidence >= 0.85)
    elif fixture_kind=="lightly_noisy_jpeg":
        expected = {"fdr_number": "SYNTH-FDR-0001", "bank_name": "Synthetic Community Bank 01",
                    "branch_name": "Synthetic Branch 001", "amount": "INR 2,35,357.00",
                    "interest_rate": "7.25%", "issue_date": "05 Mar 2024", "maturity_date": "24 Oct 2027"}
        assert any(candidates[field].value for field in expected)
        assert any(candidates[field].value is None or candidates[field].confidence is None
                   or candidates[field].confidence < 0.85 for field in expected)
        assert all(candidate.value == expected[field] for field, candidate in candidates.items()
                   if candidate.value and candidate.confidence is not None and candidate.confidence >= 0.85)
    else:
        assert candidates["fdr_number"].value=="SYNTH-FDR-0001"
