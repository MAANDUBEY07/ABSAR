"""
Unit Tests for Trust & Credibility Checker Service
===================================================
Tests domain authenticity, official government recognition (.gov.in/.nic.in),
academic institution verification (.ac.in), and scam indicator detection.
"""

import os
import sys
import unittest

# Ensure backend directory is in sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.services.trust_checker import (
    TrustChecker,
    TrustReport,
    check_opportunity_trust,
    is_academic_domain,
    is_official_government_domain,
    is_recognized_platform,
)


class TestTrustCheckerService(unittest.TestCase):
    """Test suite for trust assessment, credibility scoring, and scam detection."""

    def test_official_government_domain_recognition(self):
        """Verify .gov.in and .nic.in domain identification."""
        self.assertTrue(is_official_government_domain("https://scholarships.gov.in/schemes"))
        self.assertTrue(is_official_government_domain("https://sub.portal.nic.in/notices"))
        self.assertTrue(is_official_government_domain("https://sih.gov.in"))
        self.assertTrue(is_official_government_domain("https://nats.education.gov.in"))
        self.assertTrue(is_official_government_domain("aicte-india.org"))

        # Phishing and non-gov domains must be rejected
        self.assertFalse(is_official_government_domain("https://fake-scholarships-gov.in.com"))
        self.assertFalse(is_official_government_domain("https://portal-gov.in.org"))
        self.assertFalse(is_official_government_domain("https://unknowncompany.com"))

    def test_academic_domain_recognition(self):
        """Verify .ac.in and .edu.in institution recognition."""
        self.assertTrue(is_academic_domain("https://home.iitd.ac.in/fellowships"))
        self.assertTrue(is_academic_domain("https://www.du.ac.in/research"))
        self.assertTrue(is_academic_domain("https://mit.edu.in"))
        self.assertFalse(is_academic_domain("https://coachingclass.com"))

    def test_recognized_platform_recognition(self):
        """Verify hackathon and competition platforms."""
        self.assertTrue(is_recognized_platform("https://devpost.com/hackathons"))
        self.assertTrue(is_recognized_platform("https://unstop.com/competitions"))
        self.assertTrue(is_recognized_platform("https://hackerearth.com/challenges"))
        self.assertFalse(is_recognized_platform("https://random-unverified-site.com"))

    def test_verified_government_scholarship_evaluation(self):
        """Government scheme hosted on .gov.in must achieve VERIFIED status."""
        opp = {
            "id": "gov-pmrf-2027",
            "title": "Prime Minister Research Fellowship",
            "category": "fellowship",
            "organization": "Ministry of Education",
            "description": "Prestigious research fellowship for doctoral scholars in India.",
            "source_url": "https://scholarships.gov.in/pmrf",
            "application_url": "https://scholarships.gov.in/apply",
            "stipend_or_benefit": "INR 70,000 to 80,000 monthly fellowship",
        }
        report = check_opportunity_trust(opp)

        self.assertEqual(report.status, "VERIFIED")
        self.assertGreaterEqual(report.trust_score, 80.0)
        self.assertTrue(report.official_domain_match)
        self.assertIn("Verified official government domain", report.signals[0])

        # Contract JSON serialization check
        data = report.to_dict()
        self.assertEqual(data["opportunity_id"], "gov-pmrf-2027")
        self.assertEqual(data["status"], "VERIFIED")
        self.assertTrue(data["official_domain_match"])

    def test_verified_academic_fellowship_evaluation(self):
        """Academic opportunities on .ac.in must achieve VERIFIED status."""
        opp = {
            "id": "iitb-postdoc",
            "title": "Postdoctoral Research Fellowship in AI",
            "category": "fellowship",
            "organization": "IIT Bombay",
            "description": "Fellowship in machine learning and data science.",
            "source_url": "https://www.iitb.ac.in/careers/postdoc",
            "application_url": "https://www.iitb.ac.in/apply",
        }
        report = check_opportunity_trust(opp)
        self.assertEqual(report.status, "VERIFIED")
        self.assertTrue(report.official_domain_match)
        self.assertGreaterEqual(report.trust_score, 80.0)

    def test_recognized_hackathon_platform_neutral_evaluation(self):
        """Devpost or Unstop opportunities should be UNVERIFIED but above 70 score."""
        opp = {
            "id": "hack-2026",
            "title": "National GenAI Buildathon",
            "category": "hackathon",
            "organization": "AI Community Group",
            "description": "48 hour virtual hackathon to build generative AI tools.",
            "source_url": "https://devpost.com/hackathons/genai-2026",
            "application_url": "https://devpost.com/register",
            "stipend_or_benefit": "USD 25,000 prize pool",
        }
        report = check_opportunity_trust(opp)
        self.assertEqual(report.status, "UNVERIFIED")
        self.assertGreaterEqual(report.trust_score, 70.0)
        self.assertFalse(report.official_domain_match)

    def test_scam_detection_upfront_fee_for_job(self):
        """Demanding security deposit or registration fee for employment must be flagged SUSPICIOUS."""
        opp = {
            "id": "job-scam-1",
            "title": "Data Entry Specialist with 100% Placement Guarantee",
            "category": "job",
            "organization": "Quick Careers Agency",
            "description": "Guaranteed job placement. Candidates must pay registration fees of Rs. 3500 for training kit.",
            "source_url": "https://unverified-jobs-portal.net/opp/123",
            "application_url": "http://unverified-jobs-portal.net/pay",
        }
        report = check_opportunity_trust(opp)
        self.assertEqual(report.status, "SUSPICIOUS")
        self.assertLess(report.trust_score, 50.0)
        self.assertTrue(
            any("Upfront fee requirement" in sig for sig in report.negative_indicators)
        )

    def test_scam_detection_public_email_for_government_scheme(self):
        """Claiming to be a government scheme while using @gmail.com must be flagged SUSPICIOUS."""
        opp = {
            "id": "fake-govt-scheme",
            "title": "Pradhan Mantri Student laptop Scheme",
            "category": "government_scheme",
            "organization": "Ministry of Electronics Information",
            "description": "Free laptop distribution for college students. Contact director.laptop.scheme@gmail.com to apply.",
            "source_url": "http://freelaptopscheme.xyz",
            "application_url": "http://freelaptopscheme.xyz/register",
        }
        report = check_opportunity_trust(opp)
        self.assertEqual(report.status, "SUSPICIOUS")
        self.assertLess(report.trust_score, 50.0)
        self.assertTrue(
            any("public free webmail" in sig for sig in report.negative_indicators)
        )

    def test_scam_detection_credential_phishing(self):
        """Demanding banking passwords, ATM PINs, or OTPs must immediately result in SUSPICIOUS status."""
        opp = {
            "id": "phishing-opp",
            "title": "Instant Scholarship Disbursement",
            "category": "scholarship",
            "organization": "Scholarship Direct Credit",
            "description": "Enter your bank account password and OTP to receive instant grant directly in your account.",
            "source_url": "http://instant-scholarship.ru/claim",
        }
        report = check_opportunity_trust(opp)
        self.assertEqual(report.status, "SUSPICIOUS")
        self.assertLess(report.trust_score, 30.0)
        self.assertTrue(
            any("Demands sensitive banking credentials" in sig for sig in report.negative_indicators)
        )

    def test_no_registration_fee_not_falsely_flagged(self):
        """Explicitly stating 'no registration fee' must NOT be flagged as a fee scam."""
        opp = {
            "id": "free-hackathon",
            "title": "Open Source Hackathon 2026",
            "category": "hackathon",
            "organization": "Developer Guild",
            "description": "Compete with teams globally. There is no registration fee or deposit required. Free participation.",
            "source_url": "https://devguild.org/hackathon",
            "application_url": "https://devguild.org/register",
        }
        report = check_opportunity_trust(opp)
        self.assertNotEqual(report.status, "SUSPICIOUS")
        self.assertFalse(
            any("Upfront fee requirement" in sig for sig in report.negative_indicators)
        )


if __name__ == "__main__":
    unittest.main()
