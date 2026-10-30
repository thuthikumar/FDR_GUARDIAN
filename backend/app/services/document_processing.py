"""Bounded asynchronous document extraction with no full-text persistence."""

from __future__ import annotations

import logging
import re
import threading
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Protocol
from uuid import UUID

from PIL import Image
from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from app.core.config import (ocr_enabled, ocr_languages, ocr_timeout_seconds, processing_stale_minutes,
                             tesseract_command)
from app.models.documents import Document, ExtractedField
from app.models.fdr import FDRRecord
from app.services.document_storage import LocalPrivateStorage

logger = logging.getLogger("fdr_guardian.documents")
CONFIGURED_FIELDS = ("fdr_number", "bank_name", "branch_name", "amount", "interest_rate", "issue_date", "maturity_date")
IMAGE_DPI_SCALE = 2.0


@dataclass(frozen=True)
class TextLine:
    text: str
    words: tuple[str, ...] = ()
    confidences: tuple[float | None, ...] = ()


@dataclass(frozen=True)
class PageText:
    page_number: int
    lines: tuple[TextLine, ...]


@dataclass(frozen=True)
class Candidate:
    value: str | None
    confidence: Decimal | None
    page: int | None


class OcrUnavailableError(Exception):
    pass


class OcrEngine(Protocol):
    def version(self) -> str: ...
    def recognize(self, image: Image.Image) -> tuple[TextLine, ...]: ...


class TesseractOcrEngine:
    def version(self) -> str:
        import pytesseract
        command = tesseract_command()
        if command:
            pytesseract.pytesseract.tesseract_cmd = command
        try:
            return str(pytesseract.get_tesseract_version())
        except Exception:
            raise OcrUnavailableError from None

    def recognize(self, image: Image.Image) -> tuple[TextLine, ...]:
        import pytesseract
        from pytesseract import Output
        try:
            data = pytesseract.image_to_data(image, lang=ocr_languages(), output_type=Output.DICT,
                timeout=ocr_timeout_seconds())
        except pytesseract.TesseractNotFoundError:
            raise OcrUnavailableError from None
        except pytesseract.TesseractTimeoutError:
            raise ProcessingFailure("ocr_timeout") from None
        except Exception:
            raise ProcessingFailure("ocr_error") from None
        groups: dict[tuple[int, int, int], list[tuple[str, float | None]]] = {}
        for i, raw_word in enumerate(data.get("text", [])):
            word = str(raw_word).strip()
            if not word:
                continue
            try:
                score = float(data["conf"][i])
                confidence = score if score >= 0 else None
            except (ValueError, TypeError, KeyError):
                confidence = None
            key = (int(data["block_num"][i]), int(data["par_num"][i]), int(data["line_num"][i]))
            groups.setdefault(key, []).append((word, confidence))
        return tuple(TextLine(" ".join(word for word, _ in words), tuple(word for word, _ in words),
                              tuple(confidence for _, confidence in words)) for words in groups.values())


def tesseract_available() -> bool:
    try:
        TesseractOcrEngine().version()
        return True
    except OcrUnavailableError:
        return False


class ProcessingFailure(Exception):
    def __init__(self, code: str):
        self.code = code
        super().__init__(code)


FIELD_PATTERNS: dict[str, re.Pattern[str]] = {
    "fdr_number": re.compile(r"\b(?:fdr|deposit\s+receipt)\s*(?:number|no\.?|#)\s*[:\-]?\s*([A-Z0-9][A-Z0-9/\-]{2,})", re.I),
    "bank_name": re.compile(r"\b(?:bank\s+name|bank)\s*[:\-]\s*(.{2,100})", re.I),
    "branch_name": re.compile(r"\b(?:branch\s+name|branch)\s*[:\-]\s*(.{2,100})", re.I),
    "amount": re.compile(r"\b(?:principal\s+amount|deposit\s+amount|amount)\s*[:\-]?\s*((?:(?:INR|Rs\.?|₹)\s*)?[0-9][0-9,]*(?:\.[0-9]{1,2})?)", re.I),
    "interest_rate": re.compile(r"\b(?:rate\s+of\s+interest|interest\s+rate)\s*[:\-]?\s*([0-9]+(?:\.[0-9]+)?\s*%?)", re.I),
    "issue_date": re.compile(r"\b(?:issue\s+date|date\s+of\s+issue)\s*[:\-]?\s*([0-9]{1,2}[/-][0-9]{1,2}[/-][0-9]{4}|[0-9]{1,2}\s+[A-Za-z]{3,9}\s+[0-9]{4}|[0-9]{4}-[0-9]{2}-[0-9]{2})", re.I),
    "maturity_date": re.compile(r"\b(?:maturity\s+date|date\s+of\s+maturity|due\s+date)\s*[:\-]?\s*([0-9]{1,2}[/-][0-9]{1,2}[/-][0-9]{4}|[0-9]{1,2}\s+[A-Za-z]{3,9}\s+[0-9]{4}|[0-9]{4}-[0-9]{2}-[0-9]{2})", re.I),
}


def normalize_amount(value: str | None) -> Decimal | None:
    if not value:
        return None
    cleaned = re.sub(r"(?i)\bINR\b|Rs\.?|₹|\s", "", value).replace(",", "")
    try:
        return Decimal(cleaned).quantize(Decimal("0.01"))
    except InvalidOperation:
        return None


def normalize_interest(value: str | None) -> Decimal | None:
    if not value:
        return None
    try:
        return Decimal(value.replace("%", "").strip()).quantize(Decimal("0.01"))
    except InvalidOperation:
        return None


def normalize_date(value: str | None) -> date | None:
    if not value:
        return None
    for pattern in ("%d/%m/%Y", "%d-%m-%Y", "%d %b %Y", "%d %B %Y", "%Y-%m-%d"):
        try:
            return datetime.strptime(value.strip(), pattern).date()
        except ValueError:
            pass
    return None


def _clean_capture(value: str) -> str:
    # Preserve the captured document text; only discard whitespace around the match.
    return value.strip()


def extract_candidates(pages: tuple[PageText, ...]) -> dict[str, Candidate]:
    result = {field: Candidate(None, None, None) for field in CONFIGURED_FIELDS}
    for page in pages:
        for line in page.lines:
            for field, pattern in FIELD_PATTERNS.items():
                if result[field].value is not None:
                    continue
                match = pattern.search(line.text)
                if not match:
                    continue
                value = _clean_capture(match.group(1))
                confidence = None
                if line.words and line.confidences:
                    selected = [score for word, score in zip(line.words, line.confidences)
                                if score is not None and re.sub(r"\W", "", word).casefold() in
                                {re.sub(r"\W", "", part).casefold() for part in value.split()}]
                    if selected:
                        confidence = (Decimal(str(sum(selected) / len(selected))) / Decimal(100)).quantize(Decimal("0.001"))
                result[field] = Candidate(value or None, confidence, page.page_number)
    return result


def _pdf_pages(path: Path) -> tuple[PageText, ...]:
    import pypdfium2 as pdfium
    try:
        pdf = pdfium.PdfDocument(str(path), password="")
        pages = []
        for index in range(len(pdf)):
            page = pdf[index]
            text_page = page.get_textpage()
            text = text_page.get_text_range()
            lines = tuple(TextLine(line.strip()) for line in text.splitlines() if line.strip())
            pages.append(PageText(index + 1, lines))
        return tuple(pages)
    except Exception:
        raise ProcessingFailure("unreadable_pdf") from None


def _extract(path: Path, content_type: str, engine: OcrEngine) -> tuple[dict[str, Candidate], int, str, str]:
    if content_type == "application/pdf":
        pdf_pages = _pdf_pages(path)
        has_text = any(line.text.strip() for page in pdf_pages for line in page.lines)
        if has_text:
            from importlib.metadata import version
            return extract_candidates(pdf_pages), len(pdf_pages), "pdf_text_layer", f"pypdfium2 {version('pypdfium2')}"
        if not ocr_enabled():
            raise OcrUnavailableError
        version = engine.version()
        import pypdfium2 as pdfium
        output = []
        pdf = pdfium.PdfDocument(str(path), password="")
        for index in range(len(pdf)):
            image = pdf[index].render(scale=IMAGE_DPI_SCALE).to_pil()
            output.append(PageText(index + 1, engine.recognize(image)))
        return extract_candidates(tuple(output)), len(output), "ocr", f"Tesseract {version}"
    if not ocr_enabled():
        raise OcrUnavailableError
    version = engine.version()
    try:
        with Image.open(path) as image:
            image.load()
            lines = engine.recognize(image.convert("RGB"))
    except ProcessingFailure:
        raise
    except Exception:
        raise ProcessingFailure("unreadable_image") from None
    return extract_candidates((PageText(1, lines),)), 1, "ocr", f"Tesseract {version}"


def process_document(document_id: UUID, *, engine: OcrEngine | None = None,
                     session_factory=None, storage: LocalPrivateStorage | None = None) -> None:
    if session_factory is None:
        from app.db.session import _default_session_factory
        factory = _default_session_factory()
    else:
        factory = session_factory
    selected_storage = storage or LocalPrivateStorage()
    selected_engine = engine or TesseractOcrEngine()
    with factory() as session:
        document = session.get(Document, document_id)
        if document is None:
            return
        document.processing_status = "processing"
        document.processing_error_code = None
        document.processing_started_at = datetime.now().astimezone()
        session.commit()
        key, content_type = document.private_storage_key, document.content_type

    try:
        path = selected_storage.resolve(key)
        if not path.is_file():
            _set_failed(factory, document_id, "stored_file_missing")
            return
        candidates, pages, method, engine_name = _extract(path, content_type, selected_engine)
    except FileNotFoundError:
        _set_failed(factory, document_id, "stored_file_missing")
        return
    except OcrUnavailableError:
        with factory() as session, session.begin():
            document = session.get(Document, document_id)
            if document:
                reviewed = session.scalar(select(func.count()).select_from(ExtractedField).where(
                    ExtractedField.document_id == document_id,
                    ExtractedField.reviewer_confirmed_value.is_not(None)))
                if not reviewed:
                    session.execute(delete(ExtractedField).where(ExtractedField.document_id == document_id))
                    session.add_all(ExtractedField(document_id=document_id, field_name=field,
                        extracted_value=None, confidence_score=None, extraction_method="ocr")
                        for field in CONFIGURED_FIELDS)
                document.processing_status = "ocr_unavailable"
                document.processing_error_code = "ocr_unavailable"
                document.processed_at = datetime.now().astimezone()
        logger.info("document_processing_finished", extra={"document_id": str(document_id), "status": "ocr_unavailable"})
        return
    except ProcessingFailure as exc:
        _set_failed(factory, document_id, "stored_file_missing" if "path" in locals() and not path.is_file() else exc.code)
        return
    except Exception:
        _set_failed(factory, document_id, "processing_error")
        return

    try:
        with factory() as session, session.begin():
            document = session.get(Document, document_id)
            if document is None:
                return
            if session.scalar(select(func.count()).select_from(ExtractedField).where(
                    ExtractedField.document_id == document_id, ExtractedField.reviewer_confirmed_value.is_not(None))):
                document.processing_status = "failed"
                document.processing_error_code = "reviewed_values_protected"
                document.processed_at = datetime.now().astimezone()
                return
            session.execute(delete(ExtractedField).where(ExtractedField.document_id == document_id))
            for field_name, value in candidates.items():
                session.add(ExtractedField(document_id=document_id, field_name=field_name,
                    extracted_value=value.value, confidence_score=value.confidence,
                    extraction_method=method, source_page=value.page))
            document.processing_status = "processed"
            document.processing_error_code = None
            document.processed_at = datetime.now().astimezone()
            document.page_count = pages
            document.extraction_method = method
            document.ocr_engine = engine_name
        logger.info("document_processing_finished", extra={"document_id": str(document_id), "status": "processed", "method": method})
    except Exception:
        _set_failed(factory, document_id, "processing_error")


def _set_failed(factory, document_id: UUID, code: str) -> None:
    with factory() as session, session.begin():
        document = session.get(Document, document_id)
        if document:
            document.processing_status = "failed"
            document.processing_error_code = code if re.fullmatch(r"[a-z0-9_]{1,40}", code) else "processing_error"
            document.processed_at = datetime.now().astimezone()
    logger.warning("document_processing_failed", extra={"document_id": str(document_id), "error_code": code})


_executor = ThreadPoolExecutor(max_workers=2, thread_name_prefix="fdr-document")
_queued: set[UUID] = set()
_queue_lock = threading.Lock()
_queue_capacity = threading.BoundedSemaphore(22)


def enqueue_document(document_id: UUID) -> None:
    with _queue_lock:
        if document_id in _queued:
            return
        if not _queue_capacity.acquire(blocking=False):
            raise RuntimeError("Document processing queue is full")
        _queued.add(document_id)

    def run() -> None:
        try:
            process_document(document_id)
        finally:
            with _queue_lock:
                _queued.discard(document_id)
            _queue_capacity.release()
    _executor.submit(run)


def stale_processing_count(session: Session) -> int:
    from datetime import timedelta
    from sqlalchemy import func
    threshold = datetime.now().astimezone() - timedelta(minutes=processing_stale_minutes())
    return int(session.scalar(select(func.count()).select_from(Document).where(
        Document.processing_status == "processing", Document.processing_started_at < threshold)) or 0)
