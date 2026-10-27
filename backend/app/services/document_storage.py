"""Private local file storage for validated document uploads."""

from __future__ import annotations

import hashlib
import os
import re
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import BinaryIO, Protocol
from uuid import uuid4

from PIL import Image, UnidentifiedImageError

from app.core.config import max_pdf_pages, max_upload_bytes, storage_root

Image.MAX_IMAGE_PIXELS = 40_000_000
CHUNK_SIZE = 64 * 1024
CONTENT_TYPES = {"pdf": "application/pdf", "png": "image/png", "jpg": "image/jpeg"}
EXTENSIONS = {".pdf": "pdf", ".png": "png", ".jpg": "jpg", ".jpeg": "jpg"}
KEY_RE = re.compile(r"^[0-9a-f]{2}/[0-9a-f]{2}/[0-9a-f]{32}\.(pdf|png|jpg)$")
MAX_IMAGE_PIXELS = 40_000_000


class UploadValidationError(Exception):
    def __init__(self, status_code: int, code: str, message: str):
        self.status_code = status_code
        self.code = code
        self.message = message
        super().__init__(message)


@dataclass(frozen=True)
class StoredFile:
    key: str
    size: int
    sha256: str
    content_type: str
    page_count: int | None


class DocumentStorage(Protocol):
    def save(self, stream: BinaryIO, filename: str, declared_content_type: str) -> StoredFile: ...
    def open(self, key: str) -> BinaryIO: ...
    def exists(self, key: str) -> bool: ...


class LocalPrivateStorage:
    def __init__(self, root: Path | None = None):
        self.root = (root or storage_root()).resolve()
        self.root.mkdir(parents=True, exist_ok=True)
        try:
            self.root.chmod(0o700)
        except OSError:
            pass

    def resolve(self, key: str) -> Path:
        if not KEY_RE.fullmatch(key):
            raise ValueError("Invalid private storage key")
        target = (self.root / key).resolve()
        if not target.is_relative_to(self.root):
            raise ValueError("Invalid private storage key")
        return target

    def open(self, key: str) -> BinaryIO:
        return self.resolve(key).open("rb")

    def exists(self, key: str) -> bool:
        try:
            return self.resolve(key).is_file()
        except ValueError:
            return False

    def save(self, stream: BinaryIO, filename: str, declared_content_type: str) -> StoredFile:
        extension = Path(filename.replace("\\", "/")).suffix.lower()
        declared = (declared_content_type or "").split(";", 1)[0].strip().lower()
        temp_fd, temp_name = tempfile.mkstemp(prefix=".upload-", dir=self.root)
        temp_path = Path(temp_name)
        size = 0
        digest = hashlib.sha256()
        try:
            with os.fdopen(temp_fd, "wb") as target:
                try:
                    os.chmod(temp_path, 0o600)
                except OSError:
                    pass
                while True:
                    chunk = stream.read(CHUNK_SIZE)
                    if not chunk:
                        break
                    size += len(chunk)
                    if size > max_upload_bytes():
                        raise UploadValidationError(413, "upload_too_large", "The file exceeds the configured upload limit.")
                    digest.update(chunk)
                    target.write(chunk)
                target.flush()
                os.fsync(target.fileno())
            if size == 0:
                raise UploadValidationError(422, "empty_file", "Empty files cannot be uploaded.")

            detected, pages = self._validate_content(temp_path)
            if EXTENSIONS.get(extension) != detected or declared != CONTENT_TYPES[detected]:
                raise UploadValidationError(415, "file_type_mismatch", "File extension, content type, and file contents must agree.")

            identifier = uuid4().hex
            key = f"{identifier[:2]}/{identifier[2:4]}/{identifier}.{detected}"
            final_path = self.resolve(key)
            final_path.parent.mkdir(parents=True, exist_ok=True)
            try:
                final_path.parent.chmod(0o700)
            except OSError:
                pass
            os.replace(temp_path, final_path)
            return StoredFile(key, size, digest.hexdigest(), CONTENT_TYPES[detected], pages)
        except Exception:
            try:
                temp_path.unlink(missing_ok=True)
            except OSError:
                pass
            raise

    def _validate_content(self, path: Path) -> tuple[str, int | None]:
        with path.open("rb") as source:
            header = source.read(16)
        if header.startswith(b"%PDF-"):
            try:
                import pypdfium2 as pdfium
                pdf = pdfium.PdfDocument(str(path), password="")
                pages = len(pdf)
                if pages < 1:
                    raise ValueError("empty PDF")
                if pages > max_pdf_pages():
                    raise UploadValidationError(422, "pdf_page_limit", "The PDF exceeds the configured page limit.")
                del pdf
                return "pdf", pages
            except UploadValidationError:
                raise
            except Exception:
                raise UploadValidationError(422, "unreadable_pdf", "The PDF is encrypted or cannot be read.") from None
        if header.startswith(b"\x89PNG\r\n\x1a\n"):
            expected = "png"
        elif header.startswith(b"\xff\xd8\xff"):
            expected = "jpg"
        else:
            raise UploadValidationError(415, "unsupported_file_type", "Only valid PDF, PNG, and JPEG files are accepted.")
        try:
            with Image.open(path) as image:
                if image.format != ("PNG" if expected == "png" else "JPEG"):
                    raise UploadValidationError(415, "unsupported_file_type", "Only valid PDF, PNG, and JPEG files are accepted.")
                if image.width * image.height > MAX_IMAGE_PIXELS:
                    raise UploadValidationError(422, "image_pixel_limit", "The image dimensions exceed the configured safety limit.")
                image.verify()
        except UploadValidationError:
            raise
        except (Image.DecompressionBombError, Image.DecompressionBombWarning):
            raise UploadValidationError(422, "image_pixel_limit", "The image dimensions exceed the configured safety limit.") from None
        except (UnidentifiedImageError, OSError, ValueError):
            raise UploadValidationError(422, "unreadable_image", "The image file cannot be read.") from None
        return expected, 1

    def _discard_uncommitted(self, key: str) -> None:
        """Remove a just-written file if its database transaction did not commit."""
        try:
            self.resolve(key).unlink(missing_ok=True)
        except (OSError, ValueError):
            pass
