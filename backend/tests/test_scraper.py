"""
Unit Tests for Scraper Service & Source Registry
=================================================
Tests source registry, adapter HTML parsing, rate limiting, SSRF guard,
and normalization across opportunity categories.
"""

import os
import sys
import unittest

# Ensure backend directory is in sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.services.scraper import (
    DevpostHackathonAdapter,
    EthicalCrawlerGuard,
    GenericHTMLAdapter,
    NationalScholarshipAdapter,
    NATSApprenticeshipAdapter,
    OpportunityScraperService,
    ScrapedOpportunity,
    SmartIndiaHackathonAdapter,
    SourceMetadata,
    SourceRegistry,
    UGCNoticeAdapter,
    is_valid_opportunity,
    parse_scraped_date,
)


class TestScraperService(unittest.TestCase):
    """Test suite for scraper models, source registry, and adapter parsing."""

    def test_scraped_opportunity_validation(self):
        """Verify ScrapedOpportunity validates canonical categories and serialization."""
        opp = ScrapedOpportunity(
            id="opp-123",
            title="National Post-Matric Scholarship",
            category="scholarship",
            organization="Ministry of Minority Affairs",
            description="Scholarship for minority students",
            source_url="https://scholarships.gov.in/notice",
            source_name="National Scholarship Portal",
            opportunity_mode="online",
            stipend_or_benefit="INR 12,000/year",
            trust_status="VERIFIED",
        )
        self.assertEqual(opp.category, "scholarship")
        self.assertEqual(opp.opportunity_mode, "online")

        d = opp.to_dict()
        self.assertIsInstance(d, dict)
        self.assertEqual(d["title"], "National Post-Matric Scholarship")
        self.assertEqual(d["trust_status"], "VERIFIED")

    def test_scraped_opportunity_invalid_category_rejected(self):
        """Invalid categories must raise ValueError."""
        with self.assertRaises(ValueError):
            ScrapedOpportunity(
                id="opp-inv",
                title="Invalid Scheme",
                category="bogus_category",
                organization="Unknown",
                description="Sample",
                source_url="https://example.com",
                source_name="Unknown",
            )

    def test_scraped_opportunity_invalid_mode_rejected(self):
        """Invalid opportunity_mode must raise ValueError."""
        with self.assertRaises(ValueError):
            ScrapedOpportunity(
                id="opp-inv",
                title="Invalid Mode Scheme",
                category="internship",
                organization="Unknown",
                description="Sample",
                source_url="https://example.com",
                source_name="Unknown",
                opportunity_mode="telepathic",
            )

    def test_source_registry_defaults_and_filtering(self):
        """Verify default sources are present and can be queried by category."""
        registry = SourceRegistry()
        all_sources = registry.list_sources()
        self.assertGreater(len(all_sources), 3)

        scholarship_sources = registry.list_sources(category="scholarship")
        source_ids = [s.source_id for s in scholarship_sources]
        self.assertIn("nsp_portal", source_ids)

        hackathon_sources = registry.list_sources(category="hackathon")
        h_ids = [s.source_id for s in hackathon_sources]
        self.assertIn("devpost_hackathons", h_ids)
        self.assertIn("sih_challenges", h_ids)

    def test_ethical_crawler_guard_ssrf_protection(self):
        """Guard must block loopback, internal IPs, and non-http protocols."""
        guard = EthicalCrawlerGuard(allow_local_for_testing=False)
        self.assertFalse(guard.is_safe_url("http://127.0.0.1/admin"))
        self.assertFalse(guard.is_safe_url("http://localhost:8000/api"))
        self.assertFalse(guard.is_safe_url("http://169.254.169.254/latest/meta-data/"))
        self.assertFalse(guard.is_safe_url("ftp://scholarships.gov.in/list.txt"))
        self.assertTrue(guard.is_safe_url("https://scholarships.gov.in/schemes"))
        self.assertTrue(guard.is_safe_url("https://devpost.com/hackathons"))

    def test_national_scholarship_adapter_parsing(self):
        """Verify parsing of scholarship portal HTML."""
        html = """
        <html>
            <body>
                <div class="scheme-item">
                    <h3 class="scheme-title">Post Matric Scholarship for SC Students</h3>
                    <div class="ministry">Ministry of Social Justice and Empowerment</div>
                    <p class="description">Centrally sponsored scheme for SC students studying in India.</p>
                    <span class="deadline">Last Date: 31/12/2026</span>
                    <a href="/scheme/post-matric-sc" class="scheme-link">Apply Now</a>
                </div>
            </body>
        </html>
        """
        registry = SourceRegistry()
        src = registry.get("nsp_portal")
        adapter = NationalScholarshipAdapter(src)
        opps = adapter.parse_html(html, "https://scholarships.gov.in/schemes")

        self.assertEqual(len(opps), 1)
        opp = opps[0]
        self.assertEqual(opp.title, "Post Matric Scholarship for SC Students")
        self.assertEqual(opp.category, "scholarship")
        self.assertEqual(opp.organization, "Ministry of Social Justice and Empowerment")
        self.assertEqual(opp.deadline, "31/12/2026")
        self.assertEqual(opp.application_url, "https://scholarships.gov.in/scheme/post-matric-sc")
        self.assertEqual(opp.trust_status, "VERIFIED")

    def test_nats_apprenticeship_adapter_parsing(self):
        """Verify parsing of NATS apprenticeship listings."""
        html = """
        <div class="vacancy-card">
            <h4 class="vacancy-title">Graduate Mechanical Apprentice</h4>
            <div class="establishment">Bharat Heavy Electricals Limited</div>
            <div class="stipend">INR 9,000/month</div>
            <div class="location">Bhopal, MP</div>
            <span class="deadline">Closing Date: 15/10/2026</span>
            <a href="/vacancies/bhel-2026">View Details</a>
        </div>
        """
        registry = SourceRegistry()
        src = registry.get("nats_apprenticeship")
        adapter = NATSApprenticeshipAdapter(src)
        opps = adapter.parse_html(html, "https://nats.education.gov.in/vacancies")

        self.assertEqual(len(opps), 1)
        opp = opps[0]
        self.assertEqual(opp.title, "Graduate Mechanical Apprentice")
        self.assertEqual(opp.category, "apprenticeship")
        self.assertEqual(opp.organization, "Bharat Heavy Electricals Limited")
        self.assertEqual(opp.stipend_or_benefit, "INR 9,000/month")
        self.assertEqual(opp.location, "Bhopal, MP")
        self.assertEqual(opp.opportunity_mode, "offline")

    def test_devpost_hackathon_adapter_parsing(self):
        """Verify parsing of hackathons and prize pools."""
        html = """
        <div class="hackathon-tile">
            <h3 class="title">Global AI for Climate Hackathon</h3>
            <div class="host">Tech Innovations Foundation</div>
            <div class="reward">USD 50,000 in Prizes</div>
            <div class="time-left">Deadline: 2026-11-30</div>
            <span>Online competition</span>
            <a href="/hackathons/climate-ai-2026">Register</a>
        </div>
        """
        registry = SourceRegistry()
        src = registry.get("devpost_hackathons")
        adapter = DevpostHackathonAdapter(src)
        opps = adapter.parse_html(html, "https://devpost.com/hackathons")

        self.assertEqual(len(opps), 1)
        opp = opps[0]
        self.assertEqual(opp.title, "Global AI for Climate Hackathon")
        self.assertEqual(opp.category, "hackathon")
        self.assertEqual(opp.stipend_or_benefit, "USD 50,000 in Prizes")
        self.assertEqual(opp.opportunity_mode, "online")
        self.assertEqual(opp.category_metadata.get("prize_pool"), "USD 50,000 in Prizes")

    def test_generic_adapter_handles_unstructured_cards(self):
        """Verify generic adapter safely extracts from cards."""
        html = """
        <div class="container">
            <div class="card">
                <h2>Summer Research Internship 2027</h2>
                <span class="org">National Research Lab</span>
                <p>Work on quantum computing simulations.</p>
                <a href="/internships/quantum">Apply</a>
            </div>
        </div>
        """
        meta = SourceMetadata(
            source_id="custom_lab",
            name="Research Lab",
            base_url="https://researchlab.org",
            supported_categories=["internship"],
        )
        adapter = GenericHTMLAdapter(meta, default_category="internship")
        opps = adapter.parse_html(html, "https://researchlab.org/openings")

        self.assertEqual(len(opps), 1)
        self.assertEqual(opps[0].title, "Summer Research Internship 2027")
        self.assertEqual(opps[0].category, "internship")
        self.assertEqual(opps[0].organization, "National Research Lab")

    def test_malformed_and_empty_html_handled_safely(self):
        """Empty or malformed HTML should return an empty list without raising exceptions."""
        registry = SourceRegistry()
        src = registry.get("nsp_portal")
        adapter = NationalScholarshipAdapter(src)

        self.assertEqual(adapter.parse_html("", "https://scholarships.gov.in"), [])
        self.assertEqual(
            adapter.parse_html("<<<invalid <> html>>>", "https://scholarships.gov.in"),
            [],
        )

    def test_scraper_service_scrape_source_with_override(self):
        """Verify high-level OpportunityScraperService orchestrates scraping."""
        service = OpportunityScraperService()
        html = """
        <div class="scheme-item">
            <h3>Prime Minister Research Fellowship</h3>
            <div class="ministry">Ministry of Education</div>
            <a href="/pmrf-2027">Details</a>
        </div>
        """
        opps = service.scrape_source("nsp_portal", html_override=html)
        self.assertEqual(len(opps), 1)
        self.assertEqual(opps[0].title, "Prime Minister Research Fellowship")

    def test_scraper_service_unknown_source_raises_value_error(self):
        """Scraping an unregistered source must raise ValueError."""
        service = OpportunityScraperService()
        with self.assertRaises(ValueError):
            service.scrape_source("non_existent_source")

    def test_parse_scraped_date_multiformat(self):
        """Verify robust date parsing across numeric and English textual date representations."""
        self.assertEqual(parse_scraped_date("Last Date: 31/12/2026"), "31/12/2026")
        self.assertEqual(parse_scraped_date("Deadline: 2026-11-30"), "2026-11-30")
        self.assertEqual(parse_scraped_date("Submission closing: 15 Oct 2026"), "15 Oct 2026")
        self.assertEqual(parse_scraped_date("Ends on 31st December 2026"), "31st December 2026")
        self.assertEqual(parse_scraped_date("October 15, 2026"), "October 15, 2026")
        self.assertIsNone(parse_scraped_date("Rolling admission without fixed deadline"))

    def test_smart_india_hackathon_adapter(self):
        """Verify SIH adapter parses problem statements, domain themes, and emits innovation_challenge."""
        meta = SourceMetadata(
            source_id="sih_challenges",
            name="Smart India Hackathon",
            base_url="https://sih.gov.in",
            supported_categories=["innovation_challenge", "hackathon"],
        )
        adapter = SmartIndiaHackathonAdapter(meta)
        html = """
        <div class="problem-statement">
            <h3 class="ps-title">AI Driven Traffic Optimization for Smart Cities</h3>
            <div class="ministry">Ministry of Housing and Urban Affairs</div>
            <div class="bucket">Smart Vehicles & Transportation</div>
            <div class="deadline">Last Date: 15/10/2026</div>
            <a href="/ps/view?id=SIH1234">View Problem</a>
        </div>
        """
        opps = adapter.parse_html(html, "https://sih.gov.in/problem-statements")
        self.assertEqual(len(opps), 1)
        opp = opps[0]
        self.assertEqual(opp.category, "innovation_challenge")
        self.assertEqual(opp.title, "AI Driven Traffic Optimization for Smart Cities")
        self.assertEqual(opp.organization, "Ministry of Housing and Urban Affairs")
        self.assertEqual(opp.deadline, "15/10/2026")
        self.assertEqual(opp.category_metadata["theme"], "Smart Vehicles & Transportation")
        self.assertEqual(opp.application_url, "https://sih.gov.in/ps/view?id=SIH1234")

    def test_ugc_notice_adapter(self):
        """Verify UGC adapter parses circulars and maps to fellowship or grant."""
        meta = SourceMetadata(
            source_id="ugc_fellowships",
            name="UGC Notices",
            base_url="https://www.ugc.gov.in",
            supported_categories=["fellowship", "grant"],
        )
        adapter = UGCNoticeAdapter(meta)
        html = """
        <tr class="circular-row">
            <td><a href="/notices/savs-fellowship.pdf" class="title">National Fellowship for Higher Education of ST Students 2026-27</a></td>
            <td><span class="circular-date">Deadline: 30 Nov 2026</span></td>
        </tr>
        <tr class="circular-row">
            <td><a href="/notices/minor-research-grant.pdf" class="title">Major and Minor Research Grant Scheme Guidelines</a></td>
            <td><span class="circular-date">Deadline: 15/12/2026</span></td>
        </tr>
        """
        opps = adapter.parse_html(html, "https://www.ugc.gov.in/notices")
        self.assertEqual(len(opps), 2)
        self.assertEqual(opps[0].category, "fellowship")
        self.assertEqual(opps[0].deadline, "30 Nov 2026")
        self.assertEqual(opps[1].category, "grant")
        self.assertEqual(opps[1].deadline, "15/12/2026")

    def test_sih_adapter_rejects_patron_dignitary_card(self):
        """SIH adapter must reject non-opportunity cards like 'Patron' and return 0 opportunities."""
        meta = SourceMetadata(
            source_id="sih_challenges",
            name="Smart India Hackathon",
            base_url="https://sih.gov.in",
            supported_categories=["innovation_challenge"],
        )
        adapter = SmartIndiaHackathonAdapter(meta)
        html = """
        <div class="card">
            <h3>Patron</h3>
            <p>Hon'ble Patron and Advisory Committee</p>
        </div>
        """
        opps = adapter.parse_html(html, "https://www.sih.gov.in")
        self.assertEqual(len(opps), 0)

    def test_quality_gate_rejects_navigation_and_administrative_elements(self):
        """Quality gate must reject navigation, login, boilerplate, and junk phrases."""
        self.assertFalse(is_valid_opportunity("Patron"))
        self.assertFalse(is_valid_opportunity("Chief Patron"))
        self.assertFalse(is_valid_opportunity("Student Login"))
        self.assertFalse(is_valid_opportunity("Home"))
        self.assertFalse(is_valid_opportunity("Navigation"))
        self.assertFalse(is_valid_opportunity("Privacy Policy"))
        self.assertFalse(is_valid_opportunity("123456"))
        self.assertFalse(is_valid_opportunity(""))
        # Valid opportunity titles
        self.assertTrue(is_valid_opportunity("Post Matric Scholarship for SC Students"))
        self.assertTrue(is_valid_opportunity("AI Climate Innovation Challenge 2026"))

    def test_devpost_jsonld_parsing(self):
        """Verify Devpost adapter correctly extracts from Schema.org ItemList JSON-LD."""
        meta = SourceMetadata(
            source_id="devpost_hackathons",
            name="Devpost",
            base_url="https://devpost.com/hackathons",
            supported_categories=["hackathon"],
        )
        adapter = DevpostHackathonAdapter(meta)
        html = """
        <html>
        <head>
        <script type="application/ld+json">
        {
          "@context": "http://schema.org",
          "@type": "ItemList",
          "itemListElement": [
            {
              "@type": "ListItem",
              "item": {
                "name": "Global AI Frontier Hackathon 2026",
                "description": "Build cutting-edge generative AI models for open science.",
                "url": "https://globalai.devpost.com/",
                "organizer": {"@type": "Organization", "name": "AI Frontier Labs"},
                "endDate": "2026-12-01T23:59:00Z",
                "eventAttendanceMode": "https://schema.org/OnlineEventAttendanceMode",
                "offers": {"url": "https://globalai.devpost.com/register"},
                "additionalProperty": [{"name": "Total prize pool", "value": "10000", "unitText": "USD"}]
              }
            }
          ]
        }
        </script>
        </head>
        <body></body>
        </html>
        """
        opps = adapter.parse_html(html, "https://devpost.com/hackathons")
        self.assertEqual(len(opps), 1)
        self.assertEqual(opps[0].title, "Global AI Frontier Hackathon 2026")
        self.assertEqual(opps[0].organization, "AI Frontier Labs")
        self.assertEqual(opps[0].deadline, "2026-12-01")
        self.assertEqual(opps[0].opportunity_mode, "online")
        self.assertEqual(opps[0].stipend_or_benefit, "10000 USD")
        self.assertEqual(opps[0].application_url, "https://globalai.devpost.com/register")

    def test_nsp_accordion_parsing(self):
        """Verify NSP adapter correctly extracts from live /All-Scholarships accordion structure."""
        meta = SourceMetadata(
            source_id="nsp_portal",
            name="National Scholarship Portal",
            base_url="https://scholarships.gov.in/All-Scholarships",
            supported_categories=["scholarship"],
        )
        adapter = NationalScholarshipAdapter(meta)
        html = """
        <div class="accordion-item">
            <h2><button class="accordion-button">Department of Higher Education</button></h2>
            <div class="accordion-collapse collapse">
                <div class="accordion-body">
                    <div class="row">
                        <h6>PM-USP Central Sector Scheme of Scholarship for College Students</h6>
                        <span>Student Application Open till : 30-11-2026</span>
                    </div>
                </div>
            </div>
        </div>
        """
        opps = adapter.parse_html(html, "https://scholarships.gov.in/All-Scholarships")
        self.assertEqual(len(opps), 1)
        self.assertEqual(opps[0].title, "PM-USP Central Sector Scheme of Scholarship for College Students")
        self.assertEqual(opps[0].organization, "Department of Higher Education")
        self.assertEqual(opps[0].deadline, "30-11-2026")
        self.assertEqual(opps[0].category, "scholarship")
        self.assertEqual(opps[0].trust_status, "VERIFIED")


if __name__ == "__main__":
    unittest.main()
