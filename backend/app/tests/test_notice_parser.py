import os
import sys
import unittest
import pymupdf

# Ensure backend directory is in sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.services.notice_parser import parse_pdf


class TestNoticeParser(unittest.TestCase):
    def create_test_pdf(self, text=None):
        """Create a PDF in memory for testing."""

        document = pymupdf.open()

        page = document.new_page()

        if text:
            page.insert_text((72, 72), text)

        pdf_bytes = document.tobytes()

        document.close()

        return pdf_bytes

    def test_extract_text_from_pdf(self):

        pdf = self.create_test_pdf("AVSAR Opportunity Discovery Test")

        result = parse_pdf(pdf)

        self.assertIn("AVSAR Opportunity Discovery Test", result.text)

        self.assertEqual(result.page_count, 1)
        self.assertTrue(result.has_extractable_text)
        self.assertFalse(result.likely_scanned)

    def test_empty_pdf_input(self):

        with self.assertRaises(ValueError):
            parse_pdf(b"")

    def test_invalid_pdf_input(self):

        with self.assertRaises(ValueError):
            parse_pdf(b"This is not a PDF")

    def test_scanned_pdf_detection(self):

        pdf = self.create_test_pdf()

        result = parse_pdf(pdf)

        self.assertFalse(result.has_extractable_text)
        self.assertTrue(result.likely_scanned)
        self.assertTrue(result.warnings)


if __name__ == "__main__":
    unittest.main()
