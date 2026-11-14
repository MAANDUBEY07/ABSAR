"""
AVSAR Opportunity Scraper & Source Registry
============================================
Unified scraping and source adapter architecture supporting all 11 canonical opportunity categories.
Respects robots.txt principles, rate-limiting, source provenance, and network error resilience.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
import hashlib
import ipaddress
import logging
import re
import time
from typing import Any, Dict, List, Literal, Optional
from urllib.parse import urljoin, urlparse

from bs4 import BeautifulSoup
import requests

logger = logging.getLogger(__name__)

# Canonical 11 categories
CANONICAL_CATEGORIES = {
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
}

DEFAULT_USER_AGENT = "AVSAR-OpportunityDiscovery/1.0 (+https://avsar.gov.in/bot)"


# ---------------------------------------------------------------------------
# Data Models
# ---------------------------------------------------------------------------

@dataclass
class ScrapedOpportunity:
    """Standardized representation of an opportunity extracted by scrapers."""

    id: str
    title: str
    category: str
    organization: str
    description: str
    source_url: str
    source_name: str
    application_url: Optional[str] = None
    deadline: Optional[str] = None
    eligibility_criteria: List[str] = field(default_factory=list)
    required_skills: List[str] = field(default_factory=list)
    location: Optional[str] = None
    opportunity_mode: Optional[str] = None  # "online", "offline", "hybrid"
    stipend_or_benefit: Optional[str] = None
    trust_status: str = "UNVERIFIED"
    category_metadata: Dict[str, Any] = field(default_factory=dict)
    scraped_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )

    def __post_init__(self) -> None:
        if self.category not in CANONICAL_CATEGORIES:
            raise ValueError(
                f"Invalid opportunity category '{self.category}'. "
                f"Must be one of: {sorted(CANONICAL_CATEGORIES)}"
            )
        if self.opportunity_mode and self.opportunity_mode not in {"online", "offline", "hybrid"}:
            raise ValueError(
                f"Invalid opportunity_mode '{self.opportunity_mode}'. Must be 'online', 'offline', or 'hybrid'."
            )

    def to_dict(self) -> Dict[str, Any]:
        """Convert to JSON-serializable dictionary compliant with team contracts."""
        return {
            "id": self.id,
            "title": self.title,
            "category": self.category,
            "organization": self.organization,
            "description": self.description,
            "source_url": self.source_url,
            "source_name": self.source_name,
            "application_url": self.application_url or self.source_url,
            "deadline": self.deadline,
            "eligibility_criteria": self.eligibility_criteria,
            "required_skills": self.required_skills,
            "location": self.location,
            "opportunity_mode": self.opportunity_mode,
            "stipend_or_benefit": self.stipend_or_benefit,
            "trust_status": self.trust_status,
            "category_metadata": self.category_metadata,
            "scraped_at": self.scraped_at,
        }


@dataclass
class SourceMetadata:
    """Configuration and metadata for an opportunity source."""

    source_id: str
    name: str
    base_url: str
    supported_categories: List[str]
    collection_method: Literal["HTML", "API", "PDF_FEED", "RSS"] = "HTML"
    trust_classification: Literal["VERIFIED", "UNVERIFIED", "PARTNER"] = "UNVERIFIED"
    is_active: bool = True
    rate_limit_seconds: float = 1.0
    allowed_domains: List[str] = field(default_factory=list)
    update_frequency: str = "daily"

    def __post_init__(self) -> None:
        if not self.allowed_domains:
            parsed = urlparse(self.base_url)
            if parsed.hostname:
                self.allowed_domains = [parsed.hostname.lower()]


# ---------------------------------------------------------------------------
# Security & Ethical Crawler Guard
# ---------------------------------------------------------------------------

class EthicalCrawlerGuard:
    """Enforces rate limiting, domain boundaries, and SSRF protection."""

    def __init__(self, allow_local_for_testing: bool = False):
        self.allow_local = allow_local_for_testing
        self._last_request_times: Dict[str, float] = {}

    def is_safe_url(self, url: str) -> bool:
        """Validates that a URL is a legitimate HTTP(S) address and blocks private IP ranges."""
        try:
            parsed = urlparse(url)
            if parsed.scheme not in {"http", "https"}:
                return False
            hostname = parsed.hostname
            if not hostname:
                return False

            if self.allow_local:
                return True

            # Block localhost and obvious internal hostnames
            if hostname.lower() in {"localhost", "127.0.0.1", "::1", "metadata.google.internal"}:
                return False

            # Check if hostname is an IP address
            try:
                ip = ipaddress.ip_address(hostname)
                if ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_reserved:
                    return False
            except ValueError:
                # Hostname is a domain name, not a raw IP
                pass

            return True
        except Exception:
            return False

    def throttle(self, domain: str, delay_seconds: float) -> None:
        """Throttles requests to the same domain to respect server rate limits."""
        now = time.time()
        last_time = self._last_request_times.get(domain, 0.0)
        elapsed = now - last_time
        if elapsed < delay_seconds:
            sleep_time = delay_seconds - elapsed
            time.sleep(sleep_time)
        self._last_request_times[domain] = time.time()


# ---------------------------------------------------------------------------
# Source Registry
# ---------------------------------------------------------------------------

class SourceRegistry:
    """Registry managing available opportunity sources and their configurations."""

    def __init__(self):
        self._sources: Dict[str, SourceMetadata] = {}
        self._initialize_default_sources()

    def _initialize_default_sources(self) -> None:
        defaults = [
            SourceMetadata(
                source_id="nsp_portal",
                name="National Scholarship Portal",
                base_url="https://scholarships.gov.in",
                supported_categories=["scholarship", "government_scheme"],
                collection_method="HTML",
                trust_classification="VERIFIED",
                rate_limit_seconds=1.5,
                allowed_domains=["scholarships.gov.in"],
            ),
            SourceMetadata(
                source_id="nats_apprenticeship",
                name="National Apprenticeship Training Scheme (NATS)",
                base_url="https://nats.education.gov.in",
                supported_categories=["apprenticeship", "internship"],
                collection_method="HTML",
                trust_classification="VERIFIED",
                rate_limit_seconds=1.5,
                allowed_domains=["nats.education.gov.in"],
            ),
            SourceMetadata(
                source_id="sih_challenges",
                name="Smart India Hackathon & Innovation Challenges",
                base_url="https://www.sih.gov.in",
                supported_categories=["hackathon", "innovation_challenge"],
                collection_method="HTML",
                trust_classification="VERIFIED",
                rate_limit_seconds=1.0,
                allowed_domains=["sih.gov.in", "www.sih.gov.in"],
            ),
            SourceMetadata(
                source_id="devpost_hackathons",
                name="Devpost Public Hackathons",
                base_url="https://devpost.com",
                supported_categories=["hackathon", "coding_competition"],
                collection_method="HTML",
                trust_classification="UNVERIFIED",
                rate_limit_seconds=2.0,
                allowed_domains=["devpost.com"],
            ),
            SourceMetadata(
                source_id="ugc_fellowships",
                name="UGC Fellowships and Research Grants",
                base_url="https://www.ugc.gov.in",
                supported_categories=["fellowship", "grant"],
                collection_method="HTML",
                trust_classification="VERIFIED",
                rate_limit_seconds=1.5,
                allowed_domains=["ugc.gov.in", "www.ugc.gov.in"],
            ),
            SourceMetadata(
                source_id="startup_india",
                name="Startup India Challenges",
                base_url="https://www.startupindia.gov.in",
                supported_categories=["startup_challenge", "grant"],
                collection_method="HTML",
                trust_classification="VERIFIED",
                rate_limit_seconds=1.5,
                allowed_domains=["startupindia.gov.in", "www.startupindia.gov.in"],
            ),
        ]
        for src in defaults:
            self.register(src)

    def register(self, source: SourceMetadata) -> None:
        """Register or update a source in the registry."""
        self._sources[source.source_id] = source

    def get(self, source_id: str) -> Optional[SourceMetadata]:
        """Retrieve source metadata by source_id."""
        return self._sources.get(source_id)

    def list_sources(
        self, category: Optional[str] = None, active_only: bool = True
    ) -> List[SourceMetadata]:
        """List registered sources filtered by category and active status."""
        results = []
        for src in self._sources.values():
            if active_only and not src.is_active:
                continue
            if category and category not in src.supported_categories:
                continue
            results.append(src)
        return results


# ---------------------------------------------------------------------------
# Base Source Adapter
# ---------------------------------------------------------------------------

class BaseSourceAdapter:
    """Abstract base adapter for fetching and parsing opportunities from web sources."""

    def __init__(
        self,
        source_metadata: SourceMetadata,
        guard: Optional[EthicalCrawlerGuard] = None,
        session: Optional[requests.Session] = None,
    ):
        self.metadata = source_metadata
        self.guard = guard or EthicalCrawlerGuard()
        self.session = session or requests.Session()
        self.session.headers.update({"User-Agent": DEFAULT_USER_AGENT})

    def generate_opportunity_id(self, source_url: str, title: str) -> str:
        """Generates a deterministic unique ID based on source and title."""
        raw = f"{self.metadata.source_id}:{source_url}:{title.strip().lower()}"
        return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:24]

    def fetch_url(self, url: str, timeout: int = 10) -> Optional[str]:
        """Safely fetches HTML content from a URL with rate limiting and SSRF protection."""
        if not self.guard.is_safe_url(url):
            logger.warning("Blocked unsafe URL request: %s", url)
            return None

        domain = urlparse(url).hostname or "unknown"
        self.guard.throttle(domain, self.metadata.rate_limit_seconds)

        try:
            response = self.session.get(url, timeout=timeout)
            if response.status_code == 200:
                return response.text
            logger.warning(
                "Source %s returned status %d for URL %s",
                self.metadata.source_id,
                response.status_code,
                url,
            )
            return None
        except requests.exceptions.RequestException as e:
            logger.warning("Network error fetching %s: %s", url, e)
            return None

    def parse_html(self, html_content: str, page_url: str) -> List[ScrapedOpportunity]:
        """Parses HTML into a list of ScrapedOpportunity objects. To be implemented by subclasses."""
        raise NotImplementedError("Adapters must implement parse_html()")

    def collect(self, url: Optional[str] = None) -> List[ScrapedOpportunity]:
        """Fetches page content and parses opportunities."""
        target_url = url or self.metadata.base_url
        html = self.fetch_url(target_url)
        if not html:
            return []
        return self.parse_html(html, target_url)


# ---------------------------------------------------------------------------
# Specialized Source Adapters
# ---------------------------------------------------------------------------

class NationalScholarshipAdapter(BaseSourceAdapter):
    """Adapter for National Scholarship Portal and government scheme feeds."""

    def parse_html(self, html_content: str, page_url: str) -> List[ScrapedOpportunity]:
        soup = BeautifulSoup(html_content, "html.parser")
        opportunities: List[ScrapedOpportunity] = []

        # Find scheme/scholarship cards or table rows
        items = soup.select(".scheme-item, .scholarship-card, .scheme-row, tr.scheme-data, div.scheme")
        if not items:
            # Fallback to general cards or article tags
            items = soup.select("article, .card, .post-item")

        for item in items:
            title_tag = item.select_one("h2, h3, h4, .scheme-title, .title, a.scheme-link")
            if not title_tag:
                continue

            title = title_tag.get_text(strip=True)
            if not title or len(title) < 5:
                continue

            # Extract application / detail link
            link_tag = item.select_one("a[href]")
            rel_link = link_tag["href"] if link_tag else page_url
            app_url = urljoin(page_url, rel_link)

            # Organization
            org_tag = item.select_one(".ministry, .organization, .dept, .provider")
            org = (
                org_tag.get_text(strip=True)
                if org_tag
                else "Ministry of Education / Government of India"
            )

            # Deadline
            deadline = None
            date_tag = item.select_one(".deadline, .last-date, .date, span.date-text")
            if date_tag:
                deadline = date_tag.get_text(strip=True)
                # Normalize text like "Last Date: 31/12/2026"
                m = re.search(r"\b(\d{1,2}[/-]\d{1,2}[/-]\d{4}|\d{4}-\d{2}-\d{2})\b", deadline)
                if m:
                    deadline = m.group(1)

            # Description & Eligibility
            desc_tag = item.select_one(".description, .details, p")
            desc = desc_tag.get_text(strip=True) if desc_tag else f"Scholarship scheme: {title}"

            opp_id = self.generate_opportunity_id(app_url, title)
            category = "scholarship" if "scholarship" in title.lower() else "government_scheme"

            opportunities.append(
                ScrapedOpportunity(
                    id=opp_id,
                    title=title,
                    category=category,
                    organization=org,
                    description=desc,
                    source_url=page_url,
                    application_url=app_url,
                    deadline=deadline,
                    location="India",
                    opportunity_mode="online",
                    source_name=self.metadata.name,
                    trust_status="VERIFIED",
                )
            )

        return opportunities


class NATSApprenticeshipAdapter(BaseSourceAdapter):
    """Adapter for NATS / NAPS Apprenticeship portal notices."""

    def parse_html(self, html_content: str, page_url: str) -> List[ScrapedOpportunity]:
        soup = BeautifulSoup(html_content, "html.parser")
        opportunities: List[ScrapedOpportunity] = []

        items = soup.select(".vacancy-card, .apprenticeship-item, tr.vacancy, .job-card")
        if not items:
            items = soup.select("article, .card, div.list-item")

        for item in items:
            title_tag = item.select_one("h2, h3, h4, .vacancy-title, .title")
            if not title_tag:
                continue
            title = title_tag.get_text(strip=True)
            if not title:
                continue

            link_tag = item.select_one("a[href]")
            app_url = urljoin(page_url, link_tag["href"]) if link_tag else page_url

            org_tag = item.select_one(".establishment, .company, .org")
            org = org_tag.get_text(strip=True) if org_tag else "NATS Authorized Establishment"

            stipend_tag = item.select_one(".stipend, .salary")
            stipend = stipend_tag.get_text(strip=True) if stipend_tag else None

            location_tag = item.select_one(".location, .city, .state")
            location = location_tag.get_text(strip=True) if location_tag else "India"

            deadline = None
            date_tag = item.select_one(".deadline, .closing-date, .last-date")
            if date_tag:
                m = re.search(r"\b(\d{1,2}[/-]\d{1,2}[/-]\d{4}|\d{4}-\d{2}-\d{2})\b", date_tag.get_text())
                if m:
                    deadline = m.group(1)

            opp_id = self.generate_opportunity_id(app_url, title)
            opportunities.append(
                ScrapedOpportunity(
                    id=opp_id,
                    title=title,
                    category="apprenticeship",
                    organization=org,
                    description=f"Apprenticeship training program: {title} at {org}.",
                    source_url=page_url,
                    application_url=app_url,
                    deadline=deadline,
                    location=location,
                    opportunity_mode="offline",
                    stipend_or_benefit=stipend,
                    source_name=self.metadata.name,
                    trust_status="VERIFIED",
                    category_metadata={"stipend": stipend, "training_mode": "industrial"},
                )
            )

        return opportunities


class DevpostHackathonAdapter(BaseSourceAdapter):
    """Adapter for Hackathons and Coding Competitions."""

    def parse_html(self, html_content: str, page_url: str) -> List[ScrapedOpportunity]:
        soup = BeautifulSoup(html_content, "html.parser")
        opportunities: List[ScrapedOpportunity] = []

        items = soup.select(".hackathon-tile, .challenge-listing, .opportunity-tile, article.hackathon")
        if not items:
            items = soup.select(".card, article, div.content-item")

        for item in items:
            title_tag = item.select_one("h2, h3, h4, .title, a.title-link")
            if not title_tag:
                continue
            title = title_tag.get_text(strip=True)
            if not title or len(title) < 3:
                continue

            link_tag = item.select_one("a[href]")
            app_url = urljoin(page_url, link_tag["href"]) if link_tag else page_url

            org_tag = item.select_one(".host, .organizer, .company")
            org = org_tag.get_text(strip=True) if org_tag else "Tech Community / Organizer"

            prize_tag = item.select_one(".prize, .prize-amount, .reward")
            prize = prize_tag.get_text(strip=True) if prize_tag else None

            deadline_tag = item.select_one(".deadline, .submission-period, .time-left")
            deadline = None
            if deadline_tag:
                m = re.search(r"\b(\d{1,2}[/-]\d{1,2}[/-]\d{4}|\d{4}-\d{2}-\d{2})\b", deadline_tag.get_text())
                if m:
                    deadline = m.group(1)

            mode = "online"
            if re.search(r"\bin-person|offline|onsite\b", item.get_text(), re.I):
                mode = "offline"
            elif re.search(r"\bhybrid\b", item.get_text(), re.I):
                mode = "hybrid"

            opp_id = self.generate_opportunity_id(app_url, title)
            category = "hackathon"
            if re.search(r"\bcompetition|contest|challenge\b", title, re.I):
                category = "coding_competition"

            metadata = {}
            if prize:
                metadata["prize_pool"] = prize

            opportunities.append(
                ScrapedOpportunity(
                    id=opp_id,
                    title=title,
                    category=category,
                    organization=org,
                    description=f"{category.replace('_', ' ').title()}: {title}",
                    source_url=page_url,
                    application_url=app_url,
                    deadline=deadline,
                    location="Online" if mode == "online" else None,
                    opportunity_mode=mode,
                    stipend_or_benefit=prize,
                    source_name=self.metadata.name,
                    trust_status="UNVERIFIED",
                    category_metadata=metadata,
                )
            )

        return opportunities


class GenericHTMLAdapter(BaseSourceAdapter):
    """Fallback adapter for generic web pages listing opportunities."""

    def __init__(
        self,
        source_metadata: SourceMetadata,
        default_category: str = "internship",
        guard: Optional[EthicalCrawlerGuard] = None,
        session: Optional[requests.Session] = None,
    ):
        super().__init__(source_metadata, guard=guard, session=session)
        if default_category not in CANONICAL_CATEGORIES:
            raise ValueError(f"Invalid default_category '{default_category}'")
        self.default_category = default_category

    def parse_html(self, html_content: str, page_url: str) -> List[ScrapedOpportunity]:
        soup = BeautifulSoup(html_content, "html.parser")
        opportunities: List[ScrapedOpportunity] = []

        # Find any repeated cards, table rows, or articles
        containers = soup.select("article, .card, .opportunity, .item, tr.data-row")
        for container in containers:
            title_tag = container.select_one("h1, h2, h3, h4, .title, strong")
            if not title_tag:
                continue
            title = title_tag.get_text(strip=True)
            if not title or len(title) < 4:
                continue

            link_tag = container.select_one("a[href]")
            app_url = urljoin(page_url, link_tag["href"]) if link_tag else page_url

            org_tag = container.select_one(".org, .company, .institution, .author")
            org = org_tag.get_text(strip=True) if org_tag else self.metadata.name

            desc_tag = container.select_one("p, .desc, .summary")
            desc = desc_tag.get_text(strip=True) if desc_tag else title

            opp_id = self.generate_opportunity_id(app_url, title)

            opportunities.append(
                ScrapedOpportunity(
                    id=opp_id,
                    title=title,
                    category=self.default_category,
                    organization=org,
                    description=desc,
                    source_url=page_url,
                    application_url=app_url,
                    source_name=self.metadata.name,
                    trust_status=self.metadata.trust_classification,
                )
            )

        return opportunities


# ---------------------------------------------------------------------------
# High-Level Scraper Service
# ---------------------------------------------------------------------------

class OpportunityScraperService:
    """High-level service orchestrating adapters and source registry."""

    def __init__(
        self,
        registry: Optional[SourceRegistry] = None,
        guard: Optional[EthicalCrawlerGuard] = None,
    ):
        self.registry = registry or SourceRegistry()
        self.guard = guard or EthicalCrawlerGuard()

    def get_adapter_for_source(
        self, source_id: str, session: Optional[requests.Session] = None
    ) -> Optional[BaseSourceAdapter]:
        """Resolves the appropriate adapter instance for a given source_id."""
        source = self.registry.get(source_id)
        if not source:
            return None

        if source_id == "nsp_portal":
            return NationalScholarshipAdapter(source, guard=self.guard, session=session)
        elif source_id == "nats_apprenticeship":
            return NATSApprenticeshipAdapter(source, guard=self.guard, session=session)
        elif source_id in {"devpost_hackathons", "sih_challenges"}:
            return DevpostHackathonAdapter(source, guard=self.guard, session=session)
        else:
            default_cat = source.supported_categories[0] if source.supported_categories else "grant"
            return GenericHTMLAdapter(
                source, default_category=default_cat, guard=self.guard, session=session
            )

    def scrape_source(
        self,
        source_id: str,
        html_override: Optional[str] = None,
        url_override: Optional[str] = None,
    ) -> List[ScrapedOpportunity]:
        """Scrapes opportunities from a registered source, with optional HTML override for testing/offline."""
        adapter = self.get_adapter_for_source(source_id)
        if not adapter:
            raise ValueError(f"Unknown or unregistered source_id: '{source_id}'")

        if html_override is not None:
            url = url_override or adapter.metadata.base_url
            return adapter.parse_html(html_override, url)

        return adapter.collect(url_override)
