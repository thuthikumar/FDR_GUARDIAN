"""Run configured extraction against the generated synthetic fixture set."""

from pathlib import Path

from app.services.document_processing import OcrUnavailableError, TesseractOcrEngine, _extract, tesseract_available
from app.services.document_storage import LocalPrivateStorage


def main() -> None:
    root = LocalPrivateStorage().root / "generated-fixtures"
    if not root.is_dir():
        raise SystemExit("Generate fixtures first: python -m scripts.generate_ocr_fixtures")
    print(f"Tesseract available: {tesseract_available()}")
    for path in sorted(root.iterdir()):
        if not path.is_file():
            continue
        content_type = "application/pdf" if path.suffix == ".pdf" else "image/png" if path.suffix == ".png" else "image/jpeg"
        try:
            candidates, pages, method, engine = _extract(path, content_type, TesseractOcrEngine())
            values = ", ".join(f"{name}={candidate.value or 'not found'}"
                for name, candidate in candidates.items() if candidate.value)
            print(f"{path.name}: method={method}; pages={pages}; engine={engine}; {values or 'no configured fields found'}")
        except OcrUnavailableError:
            print(f"{path.name}: OCR unavailable (Tesseract is not installed or OCR is disabled)")
        except Exception as exc:
            code = getattr(exc, "code", "unreadable_document")
            print(f"{path.name}: safe_error={code}")


if __name__ == "__main__":
    main()
