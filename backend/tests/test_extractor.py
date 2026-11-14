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
            category_metadata={"duration_months": 24, "research_area": "Computer Science"},
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


if __name__ == "__main__":
    unittest.main()