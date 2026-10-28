"""Generate small, clearly synthetic OCR evaluation files (never real documents)."""

from __future__ import annotations

import io
import random
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter, ImageFont
from reportlab.lib.pagesizes import letter
from reportlab.lib.utils import ImageReader
from reportlab.pdfgen import canvas
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import storage_root
from app.db.session import make_engine
from app.models.fdr import FDRRecord

MARK = "SYNTHETIC SAMPLE - NOT A REAL DOCUMENT"


def _record(session: Session, internal_id: str) -> FDRRecord:
    row = session.scalar(select(FDRRecord).where(FDRRecord.internal_fdr_id == internal_id))
    if row is None:
        raise RuntimeError(f"Synthetic seed record {internal_id} is missing; seed the development database first")
    if not row.is_synthetic:
        raise RuntimeError("OCR fixture generation only accepts synthetic seed records")
    return row


def _lines(record: FDRRecord, *, amount=None, maturity=None, interest_rate: str | None = None) -> list[str]:
    lines = [MARK, f"Bank Name: {record.bank_name}", f"Branch Name: {record.branch_name}",
        f"FDR Number: {record.fdr_number}", f"Principal Amount: INR {amount if amount is not None else record.amount:,.2f}",
        f"Issue Date: {record.issue_date.strftime('%d %b %Y')}",
        f"Maturity Date: {(maturity or record.maturity_date).strftime('%d %b %Y')}"]
    if interest_rate is not None:
        lines.insert(5, f"Interest Rate: {interest_rate}")
    return lines


def _pdf(lines: list[str]) -> bytes:
    output = io.BytesIO()
    doc = canvas.Canvas(output, pagesize=letter)
    for index, line in enumerate(lines):
        doc.drawString(42, 750 - index * 24, line)
    doc.save()
    return output.getvalue()


def _image(lines: list[str], *, noisy=False, lightly_noisy=False) -> bytes:
    image = Image.new("RGB", (1500, 1100), "white")
    draw = ImageDraw.Draw(image)
    font = ImageFont.load_default(size=32)
    for index, line in enumerate(lines):
        draw.text((55, 55 + index * 105), line, fill="black", stroke_width=0, font=font)
    if noisy or lightly_noisy:
        rng = random.Random(26265 if noisy else 7182)
        pixels = image.load()
        for _ in range(19000 if noisy else 6500):
            x, y = rng.randrange(image.width), rng.randrange(image.height)
            shade = rng.randrange(150, 256)
            pixels[x, y] = (shade, shade, shade)
        if noisy:
            image = image.filter(ImageFilter.GaussianBlur(3.0))
        elif lightly_noisy:
            region = image.crop((35, 240, 1465, 360)).filter(ImageFilter.GaussianBlur(5.0))
            image.paste(region, (35, 240))
    output = io.BytesIO()
    image.save(output, format="JPEG" if noisy or lightly_noisy else "PNG",
               quality=8 if noisy else 35 if lightly_noisy else None)
    return output.getvalue()


def generate(output: Path | None = None) -> dict[str, Path]:
    target = output or storage_root() / "generated-fixtures"
    target.mkdir(parents=True, exist_ok=True)
    engine = make_engine()
    try:
        with Session(engine) as session:
            match = _record(session, "SYN-FDR-0001")
            amount_diff = _record(session, "SYN-FDR-0005")
            date_diff = _record(session, "SYN-FDR-0007")
            fixtures = {
                "text_layer.pdf": _pdf(_lines(match, interest_rate="7.25%")),
                "image_only.pdf": _pdf([MARK, "SYNTHETIC SCANNED STYLE - NOT A REAL DOCUMENT"]),
                "clean.png": _image(_lines(match, interest_rate="7.25%")),
                "lightly_noisy.jpg": _image(_lines(match, interest_rate="7.25%"), lightly_noisy=True),
                "noisy.jpg": _image(_lines(date_diff, maturity=date_diff.maturity_date.replace(day=2 if date_diff.maturity_date.day == 1 else 1)), noisy=True),
                "blank.png": _image([MARK, "INTENTIONALLY BLANK SYNTHETIC IMAGE"]),
            }
            image_only = _image(_lines(amount_diff, amount=amount_diff.amount + 1))
            overlay = io.BytesIO()
            image_pdf = canvas.Canvas(overlay, pagesize=letter)
            image_pdf.drawImage(ImageReader(io.BytesIO(image_only)), 0, 0, width=letter[0], height=letter[1])
            image_pdf.save()
            fixtures["image_only.pdf"] = overlay.getvalue()
            result = {}
            for filename, content in fixtures.items():
                path = target / filename
                path.write_bytes(content)
                result[filename] = path
            return result
    finally:
        engine.dispose()


if __name__ == "__main__":
    for name, path in generate().items():
        print(f"{name}: {path}")
