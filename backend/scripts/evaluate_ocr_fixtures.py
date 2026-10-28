"""Run configured extraction against the generated synthetic fixture set."""

from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.documents import _compare
from app.db.session import make_session_factory
from app.models.fdr import FDRRecord
from app.services.document_processing import CONFIGURED_FIELDS, OcrUnavailableError, TesseractOcrEngine, _extract, tesseract_available
from app.services.document_storage import LocalPrivateStorage


def main() -> None:
    root = LocalPrivateStorage().root / "generated-fixtures"
    if not root.is_dir():
        raise SystemExit("Generate fixtures first: python -m scripts.generate_ocr_fixtures")
    print(f"Tesseract available: {tesseract_available()}")
    fixture_records = {"text_layer.pdf": "SYN-FDR-0001", "clean.png": "SYN-FDR-0001",
                       "lightly_noisy.jpg": "SYN-FDR-0001",
                       "image_only.pdf": "SYN-FDR-0005", "noisy.jpg": "SYN-FDR-0007"}
    factory = make_session_factory()
    for path in sorted(root.iterdir()):
        if not path.is_file():
            continue
        content_type = "application/pdf" if path.suffix == ".pdf" else "image/png" if path.suffix == ".png" else "image/jpeg"
        try:
            candidates, pages, method, engine = _extract(path, content_type, TesseractOcrEngine())
            internal_id = fixture_records.get(path.name)
            with factory() as session:
                record = session.scalar(select(FDRRecord).where(FDRRecord.internal_fdr_id == internal_id)) if internal_id else None
            print(f"{path.name}: method={method}; pages={pages}; engine={engine}; record={internal_id or 'none'}")
            for field in CONFIGURED_FIELDS:
                candidate = candidates[field]
                if not candidate.value:
                    print(f"  {field}: not extracted; confidence=NULL; comparison=not_extracted")
                    continue
                stored = getattr(record, field, None) if record is not None and field != "interest_rate" else None
                stored_text = stored.isoformat() if hasattr(stored, "isoformat") else str(stored) if stored is not None else None
                comparison = _compare(field, candidate.value, stored_text)
                confidence = f"{candidate.confidence:.3f}" if candidate.confidence is not None else "NULL"
                print(f"  {field}: {candidate.value}; confidence={confidence}; comparison={comparison}")
        except OcrUnavailableError:
            print(f"{path.name}: OCR unavailable (Tesseract is not installed or OCR is disabled)")
        except Exception as exc:
            code = getattr(exc, "code", "unreadable_document")
            print(f"{path.name}: safe_error={code}")


if __name__ == "__main__":
    main()
