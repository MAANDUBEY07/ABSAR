import os
import sys
import unittest

# Ensure backend directory is in sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.services.ai_extractor import (
    ExtractedOpportunity,
    extract_opportunity,
)


class TestAIExtractor(unittest.TestCase):

    def test_empty_notice_is_rejected(self):
        with self.assertRaises(ValueError):
            extract_opportunity("")

    def test_whitespace_notice_is_rejected(self):
        with self.assertRaises(ValueError):
            extract_opportunity("   ")

    def test_oversized_notice_is_rejected(self):
        with self.assertRaises(ValueError):
            extract_opportunity("A" * 30001)

    def test_extracted_data_schema(self):
        opportunity = ExtractedOpportunity(
            title="Data Science Internship",
            category="internship",
            organization="Example Organization",
            deadline=None,
            eligibility_criteria=[
                "Must be an undergraduate student."
            ],
        )

        self.assertEqual(
            opportunity.title,
            "Data Science Internship",
        )

        self.assertIsNone(opportunity.deadline)

        self.assertEqual(
            opportunity.category,
            "internship",
        )

    def test_invalid_category_is_rejected(self):
        with self.assertRaises(ValueError):
            ExtractedOpportunity(
                title="Example Opportunity",
                category="random_category",
            )


if __name__ == "__main__":
    unittest.main()