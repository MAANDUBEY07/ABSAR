"""
Unit Tests for Duplicate Detector Service
=========================================
Tests duplicate detection logic including:
- Exact duplicate detection via SHA-256 content hashing.
- Identical titles but different organizations (must not be duplicates).
- Similar titles from the same organization.
- Conflicting deadlines causing score penalty and review flagging.
- Missing optional fields handling and weight re-normalization.
- Empty and invalid inputs.
- Text normalization (case, whitespace, punctuation).
- Batch duplicate detection against multiple existing opportunities.
- Distinct non-duplicate opportunities.
"""

from datetime import date
import os
import sys
import unittest

# Ensure backend directory and project root are in sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))

try:
    from app.services.duplicate_detector import (
        DuplicateDetector,
        DuplicateDetectorConfig,
        compare_deadlines,
        generate_content_hash,
        normalize_deadline,
        normalize_text,
    )
except ImportError:
    from backend.app.services.duplicate_detector import (
        DuplicateDetector,
        DuplicateDetectorConfig,
        compare_deadlines,
        generate_content_hash,
        normalize_deadline,
        normalize_text,
    )


class TestDuplicateDetector(unittest.TestCase):
    """Test suite for duplicate opportunity detection."""

    def setUp(self):
        self.detector = DuplicateDetector()
        self.config = DuplicateDetectorConfig()

    def test_exact_duplicate_detection(self):
        """Identical opportunities must be flagged as exact duplicates with 100% confidence."""
        opp1 = {
            "id": "opp-001",
            "title": "Data Science Summer Internship 2027",
            "organization": "ABC Research Foundation",
            "deadline": "2026-12-30",
            "category": "internship",
            "description": "Eight-week intensive summer data science internship.",
        }
        opp2 = {
            "id": "opp-002",
            "title": "Data Science Summer Internship 2027",
            "organization": "ABC Research Foundation",
            "deadline": "2026-12-30",
            "category": "internship",
            "description": "Eight-week intensive summer data science internship.",
        }

        # Check hash equality
        hash1 = generate_content_hash(opp1)
        hash2 = generate_content_hash(opp2)
        self.assertEqual(hash1, hash2)
        self.assertGreater(len(hash1), 0)

        # Check comparison verdict
        result = self.detector.compare(opp1, opp2)
        self.assertTrue(result.is_duplicate)
        self.assertTrue(result.is_exact_match)
        self.assertEqual(result.confidence_score, 1.0)
        self.assertIn("Exact duplicate detected", result.explanation)

    def test_identical_titles_different_organizations_not_duplicate(self):
        """Identical titles from different organizations must NOT be classified as duplicates."""
        opp1 = {
            "title": "Software Engineering Internship",
            "organization": "Google",
            "deadline": "2026-12-31",
            "category": "internship",
        }
        opp2 = {
            "title": "Software Engineering Internship",
            "organization": "Microsoft",
            "deadline": "2026-12-31",
            "category": "internship",
        }

        result = self.detector.compare(opp1, opp2)
        self.assertFalse(result.is_duplicate)
        self.assertFalse(result.is_exact_match)
        self.assertLess(result.confidence_score, 0.50)
        self.assertIn("organizations differ", result.explanation.lower())

    def test_similar_titles_same_organization_is_duplicate(self):
        """Similar titles with reordered words from the same organization should match."""
        opp1 = {
            "title": "Data Science Summer Internship 2027",
            "organization": "ABC Research Foundation",
            "deadline": "30 December 2026",
            "description": "Undergraduate data science internship programme.",
        }
        opp2 = {
            "title": "Summer Data Science Internship 2027",
            "organization": "ABC Research Foundation",
            "deadline": "2026-12-30",
            "description": "Undergraduate data science internship programme.",
        }

        result = self.detector.compare(opp1, opp2)
        self.assertTrue(result.is_duplicate)
        self.assertGreaterEqual(result.confidence_score, 0.80)
        self.assertIn("title", result.field_scores)
        self.assertGreaterEqual(result.field_scores["title"], 0.85)
        self.assertEqual(result.field_scores["organization"], 1.0)

    def test_conflicting_deadlines_reduces_confidence_and_flags_review(self):
        """Conflicting deadlines must penalize the confidence score and flag for review."""
        opp1 = {
            "title": "Graduate Fellowship 2026",
            "organization": "National Science Foundation",
            "deadline": "2026-06-30",
            "description": "Fellowship for postgraduate scholars.",
        }
        opp2 = {
            "title": "Graduate Fellowship 2026",
            "organization": "National Science Foundation",
            "deadline": "2026-12-31",  # 6 months later
            "description": "Fellowship for postgraduate scholars.",
        }

        result = self.detector.compare(opp1, opp2)
        self.assertTrue(result.deadline_conflict)
        self.assertTrue(result.requires_review)
        self.assertEqual(result.field_scores["deadline"], 0.0)

        # Confirm score penalty was applied
        reasons_text = " ".join(result.reasons)
        self.assertIn("Deadline conflict detected", reasons_text)

    def test_missing_optional_fields_handled_safely(self):
        """Missing optional fields (e.g. description or deadline) should re-normalize weights without crashing."""
        opp1 = {
            "title": "Young Artisan Grant",
            "organization": "Khadi & Village Industries",
        }
        opp2 = {
            "title": "Young Artisan Grant",
            "organization": "Khadi & Village Industries",
        }

        result = self.detector.compare(opp1, opp2)
        self.assertTrue(result.is_duplicate)
        self.assertEqual(result.confidence_score, 1.0)
        self.assertNotIn("description", result.field_scores)
        self.assertNotIn("deadline", result.field_scores)

    def test_empty_input_handled_safely(self):
        """Empty dictionaries or opportunities without titles must return non-duplicate safely."""
        res1 = self.detector.compare({}, {})
        self.assertFalse(res1.is_duplicate)
        self.assertEqual(res1.confidence_score, 0.0)

        res2 = self.detector.compare({"title": ""}, {"organization": "Test Org"})
        self.assertFalse(res2.is_duplicate)
        self.assertEqual(res2.confidence_score, 0.0)

    def test_case_and_whitespace_normalization(self):
        """Variations in case, punctuation, and extra whitespace must be normalized."""
        opp1 = {
            "title": "  NATIONAL  MERIT  SCHOLARSHIP (2027)! ",
            "organization": "Ministry of Education -- GOI",
            "deadline": "31/12/2026",
        }
        opp2 = {
            "title": "national merit scholarship 2027",
            "organization": "ministry of education goi",
            "deadline": "2026-12-31",
        }

        # Text normalization tests
        self.assertEqual(
            normalize_text(opp1["title"]),
            normalize_text(opp2["title"]),
        )
        self.assertEqual(
            normalize_deadline(opp1["deadline"]),
            normalize_deadline(opp2["deadline"]),
        )

        result = self.detector.compare(opp1, opp2)
        self.assertTrue(result.is_duplicate)
        self.assertGreaterEqual(result.confidence_score, 0.95)

    def test_find_duplicates_in_collection(self):
        """find_duplicates must identify matches from a collection and sort by confidence descending."""
        new_opp = {
            "id": "new-01",
            "title": "AI Research Residency 2027",
            "organization": "DeepTech Institute",
            "deadline": "2026-11-30",
        }

        existing_opportunities = [
            {
                "id": "exist-01",
                "title": "Completely Unrelated Civil Job",
                "organization": "L&T Construction",
                "deadline": "2026-05-01",
            },
            {
                "id": "exist-02",
                "title": "2027 AI Research Residency",
                "organization": "DeepTech Institute",
                "deadline": "2026-11-30",
            },
            {
                "id": "exist-03",
                "title": "AI Research Residency 2027",
                "organization": "DeepTech Institute",
                "deadline": "2026-11-30",
            },
            {
                "id": "exist-04",
                "title": "AI Residency Program",
                "organization": "Different University",
                "deadline": "2026-11-30",
            },
        ]

        matches = self.detector.find_duplicates(new_opp, existing_opportunities)
        self.assertGreaterEqual(len(matches), 2)

        # First match should be the exact/highest scoring match
        top_match = matches[0]
        self.assertEqual(top_match.existing_id, "exist-03")
        self.assertTrue(top_match.is_exact_match)
        self.assertEqual(top_match.confidence_score, 1.0)

        # Verify results are sorted descending
        for i in range(len(matches) - 1):
            self.assertGreaterEqual(matches[i].confidence_score, matches[i + 1].confidence_score)

    def test_non_duplicate_opportunities(self):
        """Distinct opportunities with different titles and organizations must score low."""
        opp1 = {
            "title": "Rural Artisan Handloom Fellowship",
            "organization": "National Craft Council",
            "deadline": "2026-08-15",
            "category": "grant",
        }
        opp2 = {
            "title": "Cloud Computing Apprenticeship",
            "organization": "TechCorp Global",
            "deadline": "2026-10-31",
            "category": "internship",
        }

        result = self.detector.compare(opp1, opp2)
        self.assertFalse(result.is_duplicate)
        self.assertFalse(result.requires_review)
        self.assertLess(result.confidence_score, 0.30)
        self.assertTrue(
            "not a duplicate" in result.explanation.lower()
            or "distinct opportunity" in result.explanation.lower()
        )

    def test_result_to_dict_serialization(self):
        """DuplicateComparisonResult.to_dict() must return standard JSON-compatible dict."""
        opp1 = {"title": "Test Title", "organization": "Test Org"}
        opp2 = {"title": "Test Title", "organization": "Test Org"}

        result = self.detector.compare(opp1, opp2)
        data = result.to_dict()

        self.assertIsInstance(data, dict)
        self.assertIn("is_duplicate", data)
        self.assertIn("confidence_score", data)
        self.assertIn("field_scores", data)
        self.assertIn("explanation", data)
        self.assertIn("reasons", data)

    def test_first_opportunity_missing_title_rejected(self):
        """If first opportunity has missing/empty title, comparison must be rejected."""
        opp1 = {"organization": "National Foundation", "deadline": "2026-12-30"}
        opp2 = {"title": "Data Science Fellowship", "organization": "National Foundation"}

        result = self.detector.compare(opp1, opp2)
        self.assertFalse(result.is_duplicate)
        self.assertFalse(result.is_exact_match)
        self.assertEqual(result.confidence_score, 0.0)
        self.assertIn("First opportunity has missing or empty title.", result.reasons)
        self.assertIn("both opportunities must have a valid title", result.explanation)

    def test_second_opportunity_missing_title_rejected(self):
        """If second opportunity has missing/empty title, comparison must be rejected."""
        opp1 = {"title": "Data Science Fellowship", "organization": "National Foundation"}
        opp2 = {"organization": "National Foundation", "deadline": "2026-12-30"}

        result = self.detector.compare(opp1, opp2)
        self.assertFalse(result.is_duplicate)
        self.assertFalse(result.is_exact_match)
        self.assertEqual(result.confidence_score, 0.0)
        self.assertIn("Second opportunity has missing or empty title.", result.reasons)
        self.assertIn("both opportunities must have a valid title", result.explanation)

    def test_both_opportunities_missing_titles_rejected(self):
        """If both opportunities have missing/empty titles, comparison must be rejected."""
        opp1 = {"organization": "ABC Foundation", "deadline": "2026-12-30"}
        opp2 = {"organization": "ABC Foundation", "deadline": "2026-12-30"}

        result = self.detector.compare(opp1, opp2)
        self.assertFalse(result.is_duplicate)
        self.assertFalse(result.is_exact_match)
        self.assertEqual(result.confidence_score, 0.0)
        self.assertIn("Both opportunities have missing or empty titles.", result.reasons)
        self.assertIn("both opportunities must have a valid title", result.explanation)

    def test_whitespace_only_title_rejected(self):
        """Whitespace-only titles must be treated as empty and rejected."""
        opp1 = {"title": "   ", "organization": "ABC"}
        opp2 = {"title": "Valid Opportunity", "organization": "ABC"}

        result = self.detector.compare(opp1, opp2)
        self.assertFalse(result.is_duplicate)
        self.assertEqual(result.confidence_score, 0.0)
        self.assertIn("First opportunity has missing or empty title.", result.reasons)

    def test_indian_date_convention_ambiguous_slash_dates(self):
        """
        Verify that ambiguous dates follow Indian DD/MM/YYYY convention:
        '05/06/2026' must be parsed as 5 June 2026 (NOT 6 May 2026).
        """
        parsed_june = normalize_deadline("05/06/2026")
        self.assertIsNotNone(parsed_june)
        self.assertEqual(parsed_june, date(2026, 6, 5))
        self.assertEqual(parsed_june.day, 5)
        self.assertEqual(parsed_june.month, 6)
        self.assertEqual(parsed_june.year, 2026)

        parsed_feb = normalize_deadline("01/02/2027")
        self.assertIsNotNone(parsed_feb)
        self.assertEqual(parsed_feb, date(2027, 2, 1))
        self.assertEqual(parsed_feb.day, 1)
        self.assertEqual(parsed_feb.month, 2)

        # Unambiguous date where day > 12
        parsed_aug = normalize_deadline("25/08/2026")
        self.assertEqual(parsed_aug, date(2026, 8, 25))

        # Indian hyphenated format DD-MM-YYYY
        parsed_hyphen = normalize_deadline("05-06-2026")
        self.assertEqual(parsed_hyphen, date(2026, 6, 5))

        # Cross-comparison between Indian format and ISO format
        score, conflict, _ = compare_deadlines("05/06/2026", "2026-06-05")
        self.assertEqual(score, 1.0)
        self.assertFalse(conflict)

    def test_configuration_validation_thresholds(self):
        """Thresholds outside [0.0, 1.0] must raise ValueError."""
        with self.assertRaises(ValueError):
            DuplicateDetectorConfig(duplicate_threshold=-0.1)

        with self.assertRaises(ValueError):
            DuplicateDetectorConfig(duplicate_threshold=1.1)

        with self.assertRaises(ValueError):
            DuplicateDetectorConfig(suspected_threshold=-0.05)

        with self.assertRaises(ValueError):
            DuplicateDetectorConfig(suspected_threshold=1.5)

        with self.assertRaises(ValueError):
            DuplicateDetectorConfig(min_org_similarity=-0.01)

        with self.assertRaises(ValueError):
            DuplicateDetectorConfig(min_org_similarity=1.01)

        with self.assertRaises(ValueError):
            DuplicateDetectorConfig(min_title_similarity_guard=2.0)

    def test_configuration_validation_weights(self):
        """Negative weights or weights not summing to 1.0 must raise ValueError."""
        # Negative weight
        with self.assertRaises(ValueError):
            DuplicateDetectorConfig(
                title_weight=-0.10,
                organization_weight=0.50,
                description_weight=0.30,
                deadline_weight=0.30,
            )

        # Weights sum to 1.2 instead of 1.0
        with self.assertRaises(ValueError):
            DuplicateDetectorConfig(
                title_weight=0.60,
                organization_weight=0.30,
                description_weight=0.20,
                deadline_weight=0.10,
            )

        # Weights sum to 0.8 instead of 1.0
        with self.assertRaises(ValueError):
            DuplicateDetectorConfig(
                title_weight=0.40,
                organization_weight=0.20,
                description_weight=0.10,
                deadline_weight=0.10,
            )

        # Valid custom weights summing to 1.0 must succeed
        valid_cfg = DuplicateDetectorConfig(
            title_weight=0.60,
            organization_weight=0.20,
            description_weight=0.10,
            deadline_weight=0.10,
            duplicate_threshold=0.85,
        )
        self.assertEqual(valid_cfg.title_weight, 0.60)
        self.assertEqual(valid_cfg.duplicate_threshold, 0.85)

    def test_configuration_validation_penalty(self):
        """Deadline conflict penalty outside [0.0, 1.0] must raise ValueError."""
        with self.assertRaises(ValueError):
            DuplicateDetectorConfig(deadline_conflict_penalty=-0.1)

        with self.assertRaises(ValueError):
            DuplicateDetectorConfig(deadline_conflict_penalty=1.2)


if __name__ == "__main__":
    unittest.main()
