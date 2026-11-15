import os
import sys
import unittest

# Ensure backend directory is in sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.services.ai_extractor import (
    ExtractedOpportunity,
    clean_notice_text,
    extract_opportunity,
    extract_opportunity_heuristics,
    normalize_extracted_opportunity,
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
            eligibility_criteria=["Must be an undergraduate student."],
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

    def test_all_eleven_categories_accepted(self):
        """Verify that all 11 canonical categories are accepted by ExtractedOpportunity."""
        categories = [
            "scholarship",
            "internship",
            "job",
            "government_scheme",
            "fellowship",
            "apprenticeship",
            "hackathon",
            "coding_competition",
            "innovation_challenge",
            "startup_challenge",
            "grant",
        ]
        for cat in categories:
            opp = ExtractedOpportunity(
                title=f"Sample {cat.replace('_', ' ').title()}",
                category=cat,
                organization="Test Org",
            )
            self.assertEqual(opp.category, cat)

    def test_hackathon_with_category_metadata_and_mode(self):
        """Verify hackathon opportunity with participation mode and specific metadata."""
        opp = ExtractedOpportunity(
            title="AVSAR National Hackathon 2026",
            category="hackathon",
            organization="AVSAR Foundation",
            opportunity_mode="hybrid",
            category_metadata={
                "prize_pool": "INR 5,00,000",
                "team_size_min": 2,
                "team_size_max": 4,
                "themes": ["AI for Good", "Education", "Civic Tech"],
            },
            required_skills=["Python", "React", "Machine Learning"],
        )
        self.assertEqual(opp.category, "hackathon")
        self.assertEqual(opp.opportunity_mode, "hybrid")
        self.assertEqual(opp.category_metadata["prize_pool"], "INR 5,00,000")
        self.assertEqual(opp.category_metadata["team_size_max"], 4)
        self.assertIn("Python", opp.required_skills)

    def test_apprenticeship_and_fellowship_schemas(self):
        """Verify fellowship and apprenticeship schemas with specialized fields."""
        fellowship = ExtractedOpportunity(
            title="Prime Minister Research Fellowship",
            category="fellowship",
            organization="Ministry of Education",
            stipend_or_benefit="INR 70,000/month",
            category_metadata={
                "duration_months": 24,
                "research_area": "Computer Science",
            },
        )
        self.assertEqual(fellowship.category, "fellowship")
        self.assertEqual(fellowship.category_metadata["duration_months"], 24)

        apprenticeship = ExtractedOpportunity(
            title="NATS Graduate Apprentice",
            category="apprenticeship",
            organization="BHEL",
            opportunity_mode="offline",
            stipend_or_benefit="INR 9,000/month stipend",
        )
        self.assertEqual(apprenticeship.category, "apprenticeship")
        self.assertEqual(apprenticeship.opportunity_mode, "offline")

    def test_invalid_opportunity_mode_rejected(self):
        """Verify that an invalid opportunity_mode raises a validation error."""
        with self.assertRaises(ValueError):
            ExtractedOpportunity(
                title="Invalid Mode Opp",
                category="internship",
                opportunity_mode="telepathic",
            )

    def test_clean_notice_text(self):
        """Verify HTML entity decoding, whitespace normalization, and noise stripping."""
        raw = "Notification:&nbsp;Data&amp;AI&nbsp;Fellowship&nbsp;2026\n\nPage 1 of 4\n\nStipend: &#8377;50,000"
        cleaned = clean_notice_text(raw)
        self.assertIn("Notification: Data&AI Fellowship 2026", cleaned)
        self.assertNotIn("&nbsp;", cleaned)
        self.assertNotIn("Page 1 of 4", cleaned)
        self.assertIn("₹50,000", cleaned)

    def test_normalize_extracted_opportunity_urls_and_mode(self):
        """Verify that normalizer extracts URLs from text and infers online mode."""
        opp = ExtractedOpportunity(
            title="Remote AI Research Fellow",
            category="fellowship",
            location="Remote, India",
        )
        text = "Apply via Google Form: https://forms.gle/avsar123 for the fellowship. Deadline: 2026-12-31."
        normalized = normalize_extracted_opportunity(
            opp, text, source_url="https://source.org/notice"
        )
        self.assertEqual(normalized.source_url, "https://source.org/notice")
        self.assertEqual(normalized.application_url, "https://forms.gle/avsar123")
        self.assertEqual(normalized.opportunity_mode, "online")
        self.assertIn("organization", normalized.missing_fields)
        self.assertNotIn("application_url", normalized.missing_fields)

    def test_extract_opportunity_heuristics(self):
        """Verify heuristic fallback extraction for categories, deadlines, and eligibility."""
        notice = """
        SMART INDIA HACKATHON 2026

        Organization: Ministry of Education Innovation Cell
        Eligibility:
        - Undergraduate engineering students
        - Teams of 6 members with at least 1 female member
        - Must have valid college ID

        Deadline: 15/10/2026
        Prize Pool: ₹1,00,000 per problem statement
        Location: Virtual / Remote
        Application link: https://sih.gov.in/register
        """
        result = extract_opportunity_heuristics(notice)
        self.assertEqual(result.category, "innovation_challenge")
        self.assertIn("Smart India Hackathon", result.title)
        self.assertEqual(result.deadline, "15/10/2026")
        self.assertEqual(result.opportunity_mode, "online")
        self.assertEqual(result.application_url, "https://sih.gov.in/register")
        self.assertEqual(len(result.eligibility_criteria), 3)
        self.assertIn("Undergraduate engineering students", result.eligibility_criteria)

    def test_extract_opportunity_with_fallback_when_offline(self):
        """Verify extract_opportunity returns valid data when fallback_on_error is True and API key is missing."""
        old_key = os.environ.pop("GEMINI_API_KEY", None)
        try:
            sample = "NATS Apprenticeship 2026\nOrganization: BHEL\nDeadline: 2026-11-30\nLocation: Bhopal"
            res = extract_opportunity(sample, fallback_on_error=True)
            self.assertEqual(res.category, "apprenticeship")
            self.assertEqual(res.organization, "BHEL")
        finally:
            if old_key is not None:
                os.environ["GEMINI_API_KEY"] = old_key


if __name__ == "__main__":
    unittest.main()
