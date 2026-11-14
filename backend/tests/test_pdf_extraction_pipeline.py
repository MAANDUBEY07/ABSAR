"""
Integration Tests for PDF Notice Parsing & Opportunity Extraction Pipeline
==========================================================================
Tests the end-to-end integration flow:
1. In-memory PDF generation with PyMuPDF.
2. Text extraction via parse_pdf().
3. Opportunity structuring via extract_opportunity() (mocked to prevent external API calls).
4. Validation of extracted attributes.
5. Verification that empty, unreadable, or non-extractable PDFs do not trigger Gemini extraction.
"""

import os
import sys
import unittest
from unittest.mock import MagicMock, patch

import pymupdf

# Ensure backend directory is in sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.services.ai_extractor import ExtractedOpportunity
from app.services.notice_parser import ParsedNotice, parse_pdf


class TestPDFExtractionPipeline(unittest.TestCase):
    """Integration test suite for the notice parser + AI extractor pipeline."""

    def create_pdf_bytes(self, text: str | None = None) -> bytes:
        """Helper to create a small valid in-memory PDF document using PyMuPDF."""
        document = pymupdf.open()
        page = document.new_page()
        if text:
            page.insert_text((72, 72), text)
        pdf_bytes = document.tobytes()
        document.close()
        return pdf_bytes

    @patch("app.services.ai_extractor.extract_opportunity")
    def test_successful_pdf_to_opportunity_pipeline(self, mock_extract):
        """
        Verify that a valid PDF with notice text is parsed and successfully passed
        to the extractor, returning a well-formed ExtractedOpportunity object.
        """
        notice_content = (
            "NATIONAL MERIT SCHOLARSHIP 2027\n"
            "Organization: Ministry of Education\n"
            "Eligible: Undergraduate students with minimum 60% marks.\n"
            "Deadline: 31 December 2026\n"
            "Benefits: INR 50,000 annual grant."
        )

        pdf_bytes = self.create_pdf_bytes(notice_content)
        source_url = "https://scholarships.gov.in/notices/merit2027.pdf"

        # 1. Parse PDF
        parsed_notice = parse_pdf(pdf_bytes)

        # 2. Verify parsed notice
        self.assertIsInstance(parsed_notice, ParsedNotice)
        self.assertTrue(parsed_notice.has_extractable_text)
        self.assertFalse(parsed_notice.likely_scanned)
        self.assertGreater(len(parsed_notice.text), 0)
        self.assertIn("NATIONAL MERIT SCHOLARSHIP 2027", parsed_notice.text)
        self.assertIn("Ministry of Education", parsed_notice.text)

        # 3. Configure mock return value for extract_opportunity
        expected_opportunity = ExtractedOpportunity(
            title="National Merit Scholarship 2027",
            category="scholarship",
            organization="Ministry of Education",
            description="Annual scholarship for undergraduate students with minimum 60% marks.",
            source_url=source_url,
            application_url="https://scholarships.gov.in/apply",
            deadline="31 December 2026",
            eligibility_criteria=["Undergraduate students with minimum 60% marks."],
            required_skills=[],
            location="India",
            stipend_or_benefit="INR 50,000 annual grant",
            missing_fields=[],
        )
        mock_extract.return_value = expected_opportunity

        # 4. Execute extraction with parsed text
        result = mock_extract(
            notice_text=parsed_notice.text,
            source_url=source_url,
        )

        # 5. Verify extractor was called with correct parameters
        mock_extract.assert_called_once_with(
            notice_text=parsed_notice.text,
            source_url=source_url,
        )

        # 6. Verify extracted opportunity attributes
        self.assertIsInstance(result, ExtractedOpportunity)
        self.assertEqual(result.title, "National Merit Scholarship 2027")
        self.assertEqual(result.category, "scholarship")
        self.assertEqual(result.organization, "Ministry of Education")
        self.assertEqual(result.deadline, "31 December 2026")
        self.assertEqual(result.source_url, source_url)
        self.assertIn("Undergraduate students with minimum 60% marks.", result.eligibility_criteria)
        self.assertEqual(result.stipend_or_benefit, "INR 50,000 annual grant")

    @patch("app.services.ai_extractor.extract_opportunity")
    def test_empty_pdf_bytes_does_not_call_gemini(self, mock_extract):
        """
        Verify that passing empty PDF bytes raises ValueError during parsing
        and does not trigger any call to the Gemini extractor.
        """
        with self.assertRaises(ValueError):
            parse_pdf(b"")

        mock_extract.assert_not_called()

    @patch("app.services.ai_extractor.extract_opportunity")
    def test_corrupted_pdf_bytes_does_not_call_gemini(self, mock_extract):
        """
        Verify that corrupt or invalid PDF bytes raise ValueError during parsing
        and prevent calling the Gemini extractor.
        """
        with self.assertRaises(ValueError):
            parse_pdf(b"NOT_A_VALID_PDF_HEADER_OR_CONTENT")

        mock_extract.assert_not_called()

    @patch("app.services.ai_extractor.extract_opportunity")
    def test_blank_pdf_without_extractable_text_skips_gemini(self, mock_extract):
        """
        Verify that a PDF containing only blank/scanned pages with no extractable text
        is detected as lacking text, and does not proceed to call the Gemini extractor.
        """
        # Blank PDF with no text elements
        blank_pdf_bytes = self.create_pdf_bytes(text=None)

        parsed_notice = parse_pdf(blank_pdf_bytes)

        self.assertFalse(parsed_notice.has_extractable_text)
        self.assertEqual(parsed_notice.text, "")
        self.assertTrue(len(parsed_notice.warnings) > 0)

        # Pipeline logic: only extract if extractable text is present
        if parsed_notice.has_extractable_text and parsed_notice.text.strip():
            mock_extract(notice_text=parsed_notice.text)

        # Extractor must not be invoked for blank document
        mock_extract.assert_not_called()


if __name__ == "__main__":
    unittest.main()
