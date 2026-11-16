"""Targeted regression tests for Source Intelligence, Multilingual Extraction, and Complete Eligibility Workflow."""

import unittest
from app.services.source_intelligence import (
    detect_language,
    extract_source_intelligence,
    enrich_opportunity,
)
from app.services.eligibility_adapter import evaluate_opportunity


class TestSourceIntelligence(unittest.TestCase):
    def test_german_text_detection_and_extraction(self):
        german_job_text = (
            "Taxmaro ist die KI-Plattform für HR und Payroll.\n\n"
            "Aufgaben:\n"
            "Du beantwortest Kundenanfragen über Chat und E-Mail. Du analysierst Probleme rund um DATEV.\n\n"
            "Requirements:\n"
            "Erste Erfahrung im Customer Support oder einer vergleichbaren Rolle.\n"
            "Sehr gutes Deutsch (C1/C2) in Wort und Schrift; gutes Englisch von Vorteil.\n"
            "Technisches Verständnis für SaaS, Python und JavaScript.\n"
            "Ein Plus: Vorkenntnisse in HR oder DATEV.\n\n"
            "Standort: Berlin\n"
            "Bewerbungsfrist: 2027-04-30\n"
        )
        self.assertEqual(detect_language(german_job_text), "de")

        summary, reqs = extract_source_intelligence(
            german_job_text,
            source_url="https://www.arbeitnow.com/jobs/taxmaro-customer-support-berlin",
            fallback_title="Customer Support Specialist",
            fallback_org="Taxmaro",
        )

        self.assertEqual(summary["source_language"], "de")
        self.assertTrue(reqs["confirmed"])
        self.assertIn("German", reqs["languages"])
        self.assertIn("English", reqs["languages"])
        self.assertEqual(reqs["min_experience_months"], 6)  # Erste Erfahrung
        self.assertIn("saas", reqs["required_skills"])
        self.assertIn("python", reqs["required_skills"])
        self.assertIn("datev", reqs["preferred_skills"])
        self.assertIn("Berlin", summary["locations"])
        self.assertIn("language_german", summary["evidence"])

    def test_english_scholarship_extraction(self):
        english_notice = (
            "National Science Innovation Fellowship 2027\n"
            "Issued by: National Research Foundation\n\n"
            "Overview:\n"
            "Fellowship supporting graduate engineering research in artificial intelligence.\n\n"
            "Eligibility Criteria:\n"
            "- Must hold a B.Tech or M.Tech degree in Computer Science or Data Science.\n"
            "- Minimum academic score: CGPA 8.0 out of 10.0.\n"
            "- At least 1 year of practical research experience.\n"
            "- Proficient in Python and Machine Learning.\n\n"
            "Deadline: 2027-06-15\n"
            "Location: Bengaluru, Karnataka (Hybrid mode)\n"
        )
        self.assertEqual(detect_language(english_notice), "en")

        summary, reqs = extract_source_intelligence(
            english_notice,
            source_url="https://research.example.org/fellowship-2027",
            fallback_title="National Science Fellowship",
            fallback_org="National Research Foundation",
        )

        self.assertEqual(summary["source_language"], "en")
        self.assertTrue(reqs["confirmed"])
        self.assertIn("b.tech", reqs["degrees"])
        self.assertIn("computer science", reqs["branches"])
        self.assertEqual(reqs["min_cgpa"], 8.0)
        self.assertEqual(reqs["min_experience_months"], 12)
        self.assertIn("python", reqs["required_skills"])
        self.assertIn("cgpa", summary["evidence"])
        self.assertIn("degree", summary["evidence"])

    def test_complete_eligibility_workflow_evaluates_profile(self):
        opp = {
            "id": "opp_test_full_workflow",
            "title": "Junior Python Developer",
            "organization": "OpenTech Labs",
            "source_url": "https://opentech.example.com/jobs/python-jr",
            "description": (
                "We are hiring a Junior Python Developer.\n"
                "Requirements:\n"
                "- Bachelor's degree in Computer Science.\n"
                "- 6 months experience in software engineering.\n"
                "- Required skills: Python, SQL.\n"
                "- Preferred: Docker.\n"
                "- Fluent in English."
            ),
            "requirements": {"confirmed": False},
        }

        # Candidate profile meeting all criteria
        candidate_eligible = {
            "degree": "Bachelor",
            "branch": "Computer Science",
            "experience_months": 12,
            "skills": ["python", "sql", "git"],
            "languages": ["English"],
        }

        # 1. Enrich opportunity
        enriched = enrich_opportunity(opp)
        self.assertTrue(enriched["requirements"]["confirmed"])
        self.assertIsNotNone(enriched.get("source_summary"))

        # 2. Evaluate candidate
        result = evaluate_opportunity(candidate_eligible, enriched)
        self.assertEqual(result["api_status"], "ELIGIBLE")
        self.assertTrue(result["is_eligible"])
        self.assertGreater(result["score"], 80.0)
        self.assertGreaterEqual(result["passed_count"], 3)
        self.assertEqual(result["failed_count"], 0)

    def test_candidate_missing_requirements_returns_not_eligible(self):
        opp = {
            "id": "opp_senior_lead",
            "title": "Lead ML Engineer",
            "description": "Requirements: Minimum 5 years experience (60 months) and Master's degree.",
            "requirements": {
                "confirmed": True,
                "min_experience_months": 60,
                "degrees": ["master"],
            },
        }
        candidate_fresher = {
            "degree": "bachelor",
            "experience_months": 6,
        }
        result = evaluate_opportunity(candidate_fresher, opp)
        self.assertEqual(result["api_status"], "NOT_ELIGIBLE")
        self.assertFalse(result["is_eligible"])
        self.assertGreaterEqual(result["failed_count"], 1)

    def test_unconfirmed_criteria_returns_cannot_determine(self):
        opp_empty = {
            "id": "opp_empty_unconfirmed",
            "title": "Generic Unconfirmed Posting",
            "description": "",
            "requirements": {"confirmed": False},
        }
        candidate = {"skills": ["python"]}
        result = evaluate_opportunity(candidate, opp_empty)
        self.assertEqual(result["api_status"], "CANNOT_DETERMINE")
        self.assertFalse(result["is_eligible"])
        self.assertTrue(result["has_missing_opportunity_criteria"])


if __name__ == "__main__":
    unittest.main()
