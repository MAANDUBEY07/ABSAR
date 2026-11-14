"""
Notice Parser Service
=====================
Extracts text from PDF opportunity notices and circulars.

Uses PyMuPDF to extract text without requiring external OCR.
Detects PDFs that may contain scanned images.
"""

from io import BytesIO
from pydantic import BaseModel
import pymupdf


class ParsedNotice(BaseModel):
    """Standardized result returned by the notice parser."""

    text: str
    page_count: int
    has_extractable_text: bool
    likely_scanned: bool
    warnings: list[str]


def parse_pdf(pdf_bytes: bytes) -> ParsedNotice:
    """
    Extract text from PDF bytes.

    Args:
        pdf_bytes: Raw contents of a PDF file.

    Returns:
        ParsedNotice containing extracted text and metadata.

    Raises:
        ValueError: If the PDF is empty, invalid, or unreadable.
    """

    if not pdf_bytes:
        raise ValueError("The uploaded PDF is empty.")

    if len(pdf_bytes) > 15 * 1024 * 1024:
        raise ValueError("PDF exceeds the maximum allowed size of 15 MB.")

    try:
        with pymupdf.open(
            stream=BytesIO(pdf_bytes),
            filetype="pdf"
        ) as document:

            if document.page_count == 0:
                raise ValueError("The PDF contains no pages.")

            extracted_pages = []

            for page_number, page in enumerate(document, start=1):
                page_text = page.get_text("text").strip()

                if page_text:
                    extracted_pages.append(
                        f"--- Page {page_number} ---\n{page_text}"
                    )

            extracted_text = "\n\n".join(extracted_pages).strip()

            warnings = []

            has_text = bool(extracted_text)

            # Very little extracted text may indicate a scanned PDF.
            likely_scanned = len(extracted_text) < 40

            if not has_text:
                warnings.append(
                    "No extractable text found. This PDF may be scanned."
                )
            elif likely_scanned:
                warnings.append(
                    "Very little text extracted. OCR may be required."
                )

            return ParsedNotice(
                text=extracted_text,
                page_count=document.page_count,
                has_extractable_text=has_text,
                likely_scanned=likely_scanned,
                warnings=warnings
            )

    except ValueError:
        raise

    except Exception as error:
        raise ValueError(
            f"Unable to parse PDF: {error}"
        ) from error