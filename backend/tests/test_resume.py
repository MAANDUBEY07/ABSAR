"""
Unit Tests for Resume Analyzer Service
======================================
Tests resume PDF extraction, skill parsing, education identification,
experience estimation, gap analysis, and opportunity matching.
"""

import os
import sys
import unittest

import pymupdf

# Ensure backend directory is in sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.models.resume import ResumeAnalysis, SkillClaim
from app.services.resume_analyzer import (
    ResumeAnalysisResult,
    analyze_resume,
    estimate_experience_years,
    extract_education,
    extract_skills,
)


class TestResumeAnalyzerService(unittest.TestCase):
    """Test suite for resume parsing, credential extraction, and match scoring."""

    def create_sample_resume_pdf(self, content: str) -> bytes:
        """Helper to create an in-memory PDF using PyMuPDF."""
        doc = pymupdf.open()
        page = doc.new_page()
        page.insert_text((72, 72), content)
        pdf_bytes = doc.tobytes()
        doc.close()
        return pdf_bytes

    def test_extract_skills_positive_and_aliases(self):
        """Verify extraction and canonicalization of skills."""
        text = (
            "Experienced software engineer proficient in Python3, React.js, and TypeScript. "
            "Built containerized services using Docker and deployed on AWS EC2. "
            "Strong foundation in PostgreSQL, Redis, and REST API development."
        )
        skills = extract_skills(text)

        self.assertIn("python", skills)
        self.assertIn("react", skills)
        self.assertIn("typescript", skills)
        self.assertIn("docker", skills)
        self.assertIn("aws", skills)
        self.assertIn("postgresql", skills)
        self.assertIn("redis", skills)
        self.assertIn("rest api", skills)

    def test_extract_skills_negative_context_excluded(self):
        """Negative mentions like 'no experience with Docker' must not be extracted."""
        text = "Familiar with Python and React. However, have no knowledge of Docker and never used Kubernetes."
        skills = extract_skills(text)

        self.assertIn("python", skills)
        self.assertIn("react", skills)
        self.assertNotIn("docker", skills)
        self.assertNotIn("kubernetes", skills)

    def test_extract_education_details(self):
        """Verify degree, branch, institution, and graduation year extraction."""
        text = (
            "EDUCATION\n"
            "Bachelor of Technology in Computer Science\n"
            "Indian Institute of Technology Delhi, 2025\n"
            "CGPA: 8.9 / 10"
        )
        edu = extract_education(text)

        self.assertGreaterEqual(len(edu), 1)
        record = edu[0]
        self.assertEqual(record["degree"], "B.Tech")
        self.assertIn("Computer Science", record["field"])
        self.assertEqual(record["graduation_year"], 2025)

    def test_estimate_experience_years_explicit(self):
        """Explicit experience phrases must be parsed correctly."""
        text1 = "Senior Developer with 3.5 years of professional experience in cloud architectures."
        self.assertEqual(estimate_experience_years(text1), 3.5)

        text2 = "Entry-level graduate eager to learn."
        self.assertEqual(estimate_experience_years(text2), 0.0)

    def test_estimate_experience_years_date_ranges(self):
        """Date ranges in experience section must compute estimated tenure."""
        text = "Software Intern at TechCorp (Jan 2022 - Dec 2023)"
        years = estimate_experience_years(text)
        self.assertGreaterEqual(years, 1.0)
        self.assertLessEqual(years, 3.0)

    def test_analyze_resume_text_contract(self):
        """Verify plain text resume analysis matches API contract."""
        text = (
            "Aarav Sharma\n"
            "Skills: Python, FastAPI, Docker, SQL, Git, Machine Learning\n"
            "Education: B.Tech in Information Technology from Delhi University (2024)\n"
            "Experience: 1 year of experience as a Backend Intern."
        )
        result = analyze_resume(text)

        self.assertIsInstance(result, ResumeAnalysisResult)
        self.assertIn("python", result.parsed_skills)
        self.assertIn("fastapi", result.parsed_skills)
        self.assertGreaterEqual(result.experience_years, 1.0)
        self.assertGreaterEqual(result.readiness_score, 50.0)

        # JSON serialization contract check
        d = result.to_dict()
        self.assertIn("parsed_skills", d)
        self.assertIn("experience_years", d)
        self.assertIn("education", d)
        self.assertIn("readiness_score", d)
        self.assertIn("recommendations", d)

    def test_analyze_resume_pdf_bytes(self):
        """Verify PDF bytes parsing using in-memory PyMuPDF document."""
        content = (
            "Priya Patel\n"
            "Technical Skills: Java, Spring Boot, React, MySQL, AWS\n"
            "Education: Master of Computer Applications (MCA), 2026\n"
            "2 years of experience developing enterprise microservices."
        )
        pdf_bytes = self.create_sample_resume_pdf(content)
        result = analyze_resume(pdf_bytes)

        self.assertIn("java", result.parsed_skills)
        self.assertIn("spring boot", result.parsed_skills)
        self.assertIn("react", result.parsed_skills)
        self.assertEqual(result.experience_years, 2.0)
        self.assertGreaterEqual(len(result.education), 1)

    def test_match_against_opportunity_and_recommendations(self):
        """Verify opportunity gap analysis and customized recommendations."""
        resume = (
            "Candidate with Python, SQL, Git, and Pandas experience. "
            "B.Tech Computer Science graduate."
        )
        opp = {
            "title": "Machine Learning Engineer Intern",
            "category": "internship",
            "required_skills": ["python", "pandas", "pytorch", "docker"],
        }
        result = analyze_resume(resume, opportunity=opp)

        self.assertIn("python", result.matched_skills)
        self.assertIn("pandas", result.matched_skills)
        self.assertIn("pytorch", result.missing_skills)
        self.assertIn("docker", result.missing_skills)
        self.assertGreater(result.readiness_score, 30.0)

        # Recommendations must mention missing skills
        recs_text = " ".join(result.recommendations)
        self.assertIn("pytorch", recs_text.lower())
        self.assertIn("docker", recs_text.lower())

    def test_empty_or_malformed_resume_handled_safely(self):
        """Empty input or corrupted bytes must not raise unhandled exceptions."""
        empty_res = analyze_resume("")
        self.assertEqual(empty_res.parsed_skills, [])
        self.assertEqual(empty_res.experience_years, 0.0)

        corrupt_bytes_res = analyze_resume(b"not a valid pdf document")
        self.assertEqual(corrupt_bytes_res.parsed_skills, [])
        self.assertEqual(corrupt_bytes_res.experience_years, 0.0)

    def test_extended_skill_taxonomy_and_benign_negations(self):
        """Verify newly added modern skills and ensure benign 'do not' in preceding sentences does not exclude skills."""
        text = (
            "Do not hesitate to reach out via email. "
            "Technical Skills: Python, Docker, Tailwind CSS, LangChain, Terraform, Postman."
        )
        skills = extract_skills(text)
        self.assertIn("python", skills)
        self.assertIn("docker", skills)
        self.assertIn("tailwind css", skills)
        self.assertIn("langchain", skills)
        self.assertIn("terraform", skills)
        self.assertIn("postman", skills)

    def test_analyze_resume_additional_args_compatibility(self):
        """Verify analyze_resume accepts positional and keyword owner/document metadata without crashing or discarding."""
        text = "Experienced software engineer with Python and React."
        # Test keyword arguments
        res_kw = analyze_resume(text, owner_id="student_456", document_id="doc_789")
        self.assertIn("python", res_kw.parsed_skills)
        self.assertIn("react", res_kw.parsed_skills)
        self.assertEqual(res_kw.owner_id, "student_456")
        self.assertEqual(res_kw.document_id, "doc_789")
        self.assertEqual(res_kw.skills, res_kw.parsed_skills)
        self.assertEqual(res_kw.to_dict()["owner_id"], "student_456")

        # Test positional arguments as invoked by Member 2 jobs.py
        res_pos = analyze_resume(text, "student_456", "doc_789")
        self.assertEqual(res_pos.owner_id, "student_456")
        self.assertEqual(res_pos.document_id, "doc_789")

    def test_member2_backend_schema_validation_regression(self):
        """Regression test: Serialized result must validate strictly against

        Member 2's ResumeAnalysis schema with extra='forbid'.
        Exercises both positional (jobs.py / member1.py adapter) and keyword calls.
        """
        resume_text = (
            "Aarav Sharma\n"
            "Backend Engineer proficient in Python, Docker, and PostgreSQL.\n"
            "Education: B.Tech Computer Science, 2024.\n"
            "2 years of experience building microservices."
        )

        # 1. Positional invocation path: analyze_resume(text, owner_id, document_id)
        # Matches Member 2's backend/app/integrations/member1.py line:
        # _invoke("app.services.resume_analyzer", "analyze_resume", text, owner_id, document_id)
        raw_result_pos = analyze_resume(resume_text, "user_alpha_123", "doc_beta_456")

        # Must satisfy Member 2's _payload() expectation: isinstance(raw_result, dict)
        self.assertIsInstance(raw_result_pos, dict)

        # Must validate against Member 2's ResumeAnalysis without extra field errors
        validated_pos = ResumeAnalysis.model_validate(raw_result_pos)
        self.assertEqual(validated_pos.owner_id, "user_alpha_123")
        self.assertEqual(validated_pos.document_id, "doc_beta_456")
        self.assertIn("python", validated_pos.skills)
        self.assertIn("docker", validated_pos.skills)
        self.assertIn("postgresql", validated_pos.skills)
        self.assertGreaterEqual(len(validated_pos.evidence), 3)

        # Verify evidence item schema and claims
        for claim in validated_pos.evidence:
            self.assertIsInstance(claim, SkillClaim)
            self.assertEqual(claim.source, "RESUME_CLAIM")
            self.assertGreaterEqual(claim.start, 0)
            self.assertGreater(claim.end, claim.start)
            self.assertEqual(resume_text[claim.start : claim.end].lower(), claim.quote.lower())

        self.assertEqual(
            validated_pos.disclaimer,
            "Resume claims; confirm explicitly through profile updates",
        )

        # Frontend attributes must still be accessible on the result object
        self.assertIn("python", raw_result_pos.parsed_skills)
        self.assertGreaterEqual(raw_result_pos.experience_years, 2.0)
        self.assertGreaterEqual(raw_result_pos.readiness_score, 50.0)

        # 2. Keyword invocation path: analyze_resume(text, owner_id=..., document_id=...)
        raw_result_kw = analyze_resume(
            resume_text, owner_id="user_kw_789", document_id="doc_kw_101"
        )
        validated_kw = ResumeAnalysis.model_validate(raw_result_kw)
        self.assertEqual(validated_kw.owner_id, "user_kw_789")
        self.assertEqual(validated_kw.document_id, "doc_kw_101")
        self.assertIn("python", validated_kw.skills)


if __name__ == "__main__":
    unittest.main()
