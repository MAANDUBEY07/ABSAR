from app.services.resume_analyzer import claims as claims
import base64
import hashlib
import re
import zipfile
from io import BytesIO
from pathlib import Path
import pymupdf
from docx import Document as WordDocument
from PIL import Image
import pytesseract
from fastapi import HTTPException
from starlette.concurrency import run_in_threadpool
from sqlalchemy import select
from app.config import settings
from app.models.resume import Document


def extract(content, filename, resume=False):
    if not content or len(content) > settings.max_upload_bytes:
        raise ValueError("Upload must be nonempty and at most 5 MiB")
    suffix = Path(filename).suffix.lower()
    text, pages, warnings = "", None, []
    if suffix == ".pdf" and content.startswith(b"%PDF-"):
        with pymupdf.open(stream=content, filetype="pdf") as pdf:
            pages = len(pdf)
            if pdf.is_encrypted or not 0 < pages <= 30:
                raise ValueError("PDF must be unencrypted with 1 to 30 pages")
            parts = []
            for page in pdf:
                piece = page.get_text()
                if not piece.strip():
                    rect = page.rect
                    if rect.width * rect.height * 4 > 16000000:
                        raise ValueError("OCR page exceeds pixel limit")
                    pix = page.get_pixmap(matrix=pymupdf.Matrix(2, 2))
                    image = Image.open(BytesIO(pix.tobytes("png")))
                    piece = pytesseract.image_to_string(image, timeout=15)
                    warnings.append("OCR text requires human review")
                parts.append(piece)
                if sum(map(len, parts)) > 100000:
                    raise ValueError("Extracted text exceeds 100000 characters")
            text = "\n".join(parts)
    elif suffix == ".docx" and content.startswith(b"PK"):
        with zipfile.ZipFile(BytesIO(content)) as archive:
            members = archive.infolist()
            if (
                len(members) > 1000
                or sum(i.file_size for i in members) > 20 * 1024 * 1024
                or any(i.flag_bits & 1 for i in members)
            ):
                raise ValueError("DOCX archive expansion limit exceeded")
            if "word/document.xml" not in archive.namelist():
                raise ValueError("Not a Word document")
        doc = WordDocument(BytesIO(content))
        text = "\n".join(
            [p.text for p in doc.paragraphs]
            + [cell.text for t in doc.tables for row in t.rows for cell in row.cells]
        )
    elif not resume and suffix in {".png", ".jpg", ".jpeg"}:
        with Image.open(BytesIO(content)) as image:
            if image.format not in {"PNG", "JPEG"} or image.width * image.height > 16000000:
                raise ValueError("Image content or pixel limit invalid")
            image.load()
            text = pytesseract.image_to_string(image, timeout=15)
            warnings.append("OCR text requires human review")
    else:
        raise ValueError("Invalid file content/type")
    if len(text) > 100000:
        raise ValueError("Extracted text exceeds 100000 characters")
    return dict(text=text, page_count=pages, warnings=warnings)


def inspect_upload(content, filename, resume=False):
    """Cheap content/container validation; OCR/text extraction belongs to the worker."""
    if not content or len(content) > settings.max_upload_bytes:
        raise ValueError("Invalid upload size")
    suffix = Path(filename).suffix.lower()
    if suffix == ".pdf" and content.startswith(b"%PDF-"):
        with pymupdf.open(stream=content, filetype="pdf") as pdf:
            if pdf.is_encrypted or not 0 < len(pdf) <= 30:
                raise ValueError("Invalid PDF page count/encryption")
            return {"page_count": len(pdf)}
    if suffix == ".docx" and content.startswith(b"PK"):
        with zipfile.ZipFile(BytesIO(content)) as archive:
            members = archive.infolist()
            if (
                len(members) > 1000
                or sum(i.file_size for i in members) > 20 * 1024 * 1024
                or any(i.flag_bits & 1 for i in members)
                or "word/document.xml" not in archive.namelist()
            ):
                raise ValueError("Invalid Word archive")
        return {"page_count": None}
    if not resume and suffix in {".png", ".jpg", ".jpeg"}:
        with Image.open(BytesIO(content)) as image:
            if image.format not in {"PNG", "JPEG"} or image.width * image.height > 16000000:
                raise ValueError("Invalid image")
            image.verify()
        return {"page_count": None}
    raise ValueError("Invalid content/type")


async def upload(file, db, owner, kind):
    content = await file.read(settings.max_upload_bytes + 1)
    try:
        result = await run_in_threadpool(
            inspect_upload, content, file.filename or "", resume=kind == "resume"
        )
    except (
        ValueError,
        OSError,
        Image.DecompressionBombError,
        RuntimeError,
        zipfile.BadZipFile,
        pymupdf.FileDataError,
        pytesseract.TesseractNotFoundError,
    ):
        raise HTTPException(
            422, "Document could not be parsed within supported content and resource limits"
        ) from None
    checksum = hashlib.sha256(content).hexdigest()
    row = db.scalar(
        select(Document).where(Document.owner_id == owner, Document.content_hash == checksum)
    )
    if row is None:
        row = Document(
            owner_id=owner,
            content_hash=checksum,
            payload=dict(
                result,
                kind=kind,
                filename=Path(file.filename or "upload").name,
                size=len(content),
                content_base64=base64.b64encode(content).decode(),
            ),
        )
        db.add(row)
        db.commit()
    return row


def notice_draft(text):
    title = next((line.strip() for line in text.splitlines() if line.strip()), None)
    dates = re.findall(r"\b\d{4}-\d{2}-\d{2}\b", text)
    from datetime import date

    deadline = None
    for value in dates:
        try:
            date.fromisoformat(value)
        except ValueError:
            continue
        # Accept a date only when the source explicitly identifies it as a deadline.
        if re.search(r"(?:deadline|last date)\s*[:=-]?\s*" + value, text, re.I):
            deadline = value
    return dict(
        title=title[:300] if title else None,
        description=text[:30000],
        organization=None,
        category="other",
        deadline=deadline,
        application_url=None,
        requirements={"confirmed": False},
        provenance="DETERMINISTIC_TEXT_EXTRACTION",
        confidence={"title": "low", "deadline": "source_explicit" if deadline else "missing"},
        evidence={"title": title, "deadline": deadline},
        missing_fields=["organization", "application_url", "eligibility_requirements"],
    )
