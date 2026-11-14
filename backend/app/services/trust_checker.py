"""
AVSAR Trust & Credibility Checker Service
==========================================
Analyzes opportunity authenticity, official domain verification (.gov.in/.nic.in/.ac.in),
and detects scam / fraud indicators (upfront fees, suspicious public emails, credential phishing).
"""

from __future__ import annotations

from dataclasses import dataclass, field
import logging
import re
from typing import Any, Dict, List, Literal, Optional, Tuple
from urllib.parse import urlparse

logger = logging.getLogger(__name__)

TrustStatus = Literal["VERIFIED", "UNVERIFIED", "SUSPICIOUS"]

# Official government domains & TLDs
GOVERNMENT_DOMAINS = {
    "gov.in",
    "nic.in",
    "digitalindia.gov.in",
    "mygov.in",
    "india.gov.in",
    "scholarships.gov.in",
    "sih.gov.in",
    "nats.education.gov.in",
    "aicte-india.org",
    "ugc.ac.in",
    "ncs.gov.in",
}

# Academic domains & TLDs
ACADEMIC_TLDS = {
    "ac.in",
    "edu.in",
    "res.in",
    "ernet.in",
}

# Recognized trusted student opportunity & hackathon platforms
RECOGNIZED_PLATFORMS = {
    "devpost.com",
    "unstop.com",
    "hackerearth.com",
    "codechef.com",
    "kaggle.com",
    "github.com",
    "internshala.com",
}

# Free public webmail providers suspicious when used by official government or enterprise programs
FREE_MAIL_PROVIDERS = {
    "gmail.com",
    "yahoo.com",
    "hotmail.com",
    "outlook.com",
    "rediffmail.com",
    "yopmail.com",
}


@dataclass
class TrustReport:
    """Credibility assessment result conforming to AVSAR TrustReportResponse API contract."""

    opportunity_id: str
    trust_score: float
    status: TrustStatus
    signals: List[str]
    official_domain_match: bool
    positive_indicators: List[str] = field(default_factory=list)
    negative_indicators: List[str] = field(default_factory=list)
    domain: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert report to API-contract-compliant JSON dictionary."""
        return {
            "opportunity_id": self.opportunity_id,
            "trust_score": round(self.trust_score, 1),
            "status": self.status,
            "signals": self.signals,
            "official_domain_match": self.official_domain_match,
            "positive_indicators": self.positive_indicators,
            "negative_indicators": self.negative_indicators,
            "domain": self.domain,
        }


def extract_domain(url: Optional[str]) -> Optional[str]:
    """Extracts lowercase hostname from a URL."""
    if not url:
        return None
    try:
        if not re.match(r"^[a-zA-Z]+://", url):
            url = f"https://{url}"
        parsed = urlparse(url)
        return parsed.hostname.lower() if parsed.hostname else None
    except Exception:
        return None


def is_official_government_domain(domain_or_url: Optional[str]) -> bool:
    """Checks whether the domain is an official Indian government portal (.gov.in / .nic.in)."""
    domain = extract_domain(domain_or_url) if domain_or_url and "://" in domain_or_url else domain_or_url
    if not domain:
        return False
    domain = domain.lower().strip()
    if domain.endswith(".gov.in") or domain.endswith(".nic.in"):
        return True
    return domain in GOVERNMENT_DOMAINS


def is_academic_domain(domain_or_url: Optional[str]) -> bool:
    """Checks whether the domain is an accredited Indian academic / research institution."""
    domain = extract_domain(domain_or_url) if domain_or_url and "://" in domain_or_url else domain_or_url
    if not domain:
        return False
    domain = domain.lower().strip()
    for tld in ACADEMIC_TLDS:
        if domain.endswith(f".{tld}"):
            return True
    return False


def is_recognized_platform(domain_or_url: Optional[str]) -> bool:
    """Checks whether the domain is a recognized public competition/hackathon platform."""
    domain = extract_domain(domain_or_url) if domain_or_url and "://" in domain_or_url else domain_or_url
    if not domain:
        return False
    domain = domain.lower().strip()
    for plat in RECOGNIZED_PLATFORMS:
        if domain == plat or domain.endswith(f".{plat}"):
            return True
    return False


class TrustChecker:
    """Evaluates credibility, domain authenticity, and scam indicators of opportunities."""

    def __init__(
        self,
        verified_threshold: float = 80.0,
        unverified_threshold: float = 50.0,
    ):
        self.verified_threshold = verified_threshold
        self.unverified_threshold = unverified_threshold

    def evaluate(self, opportunity: Dict[str, Any]) -> TrustReport:
        """
        Evaluates an opportunity dictionary and produces a TrustReport.

        Args:
            opportunity: Dictionary representing an opportunity. Expected fields:
                         'id', 'title', 'category', 'organization', 'description',
                         'source_url', 'application_url', 'stipend_or_benefit'.

        Returns:
            TrustReport with score, status, and explainable signals.
        """
        opp_id = str(opportunity.get("id") or "unknown_opportunity")
        title = str(opportunity.get("title") or "")
        category = str(opportunity.get("category") or "").lower()
        organization = str(opportunity.get("organization") or "")
        source_url = opportunity.get("source_url")
        app_url = opportunity.get("application_url") or source_url
        description = str(opportunity.get("description") or "")
        combined_text = f"{title}\n{organization}\n{description}\n{opportunity.get('stipend_or_benefit') or ''}"

        source_domain = extract_domain(source_url)
        app_domain = extract_domain(app_url)
        primary_domain = app_domain or source_domain

        score = 50.0  # Base neutral score
        signals: List[str] = []
        positive_indicators: List[str] = []
        negative_indicators: List[str] = []
        has_critical_red_flag = False

        # -------------------------------------------------------------------
        # 1. Domain & Origin Verification
        # -------------------------------------------------------------------
        is_gov = is_official_government_domain(app_domain) or is_official_government_domain(source_domain)
        is_edu = is_academic_domain(app_domain) or is_academic_domain(source_domain)
        is_platform = is_recognized_platform(app_domain) or is_recognized_platform(source_domain)

        official_match = is_gov or is_edu

        if is_gov:
            score += 35.0
            sig = f"Verified official government domain ({primary_domain})"
            signals.append(sig)
            positive_indicators.append(sig)
        elif is_edu:
            score += 30.0
            sig = f"Verified academic/research institution domain ({primary_domain})"
            signals.append(sig)
            positive_indicators.append(sig)
        elif is_platform:
            score += 20.0
            sig = f"Hosted on recognized hackathon/student platform ({primary_domain})"
            signals.append(sig)
            positive_indicators.append(sig)
        elif primary_domain:
            signals.append(f"Standard public web domain ({primary_domain})")

        # HTTPS Check
        if app_url and app_url.startswith("https://"):
            score += 5.0
            positive_indicators.append("Secure HTTPS application channel")
        elif app_url and app_url.startswith("http://"):
            score -= 15.0
            sig = "Insecure HTTP application URL without encryption"
            signals.append(sig)
            negative_indicators.append(sig)

        # -------------------------------------------------------------------
        # 2. Scam & Fraud Indicators
        # -------------------------------------------------------------------

        # A. Upfront fee for employment, scholarship or selection
        # Note: Hackathons may have registration fees, but jobs/scholarships should not demand "placement fees"
        fee_match = re.search(
            r"\b(?:(?:security|processing|registration|joining|training)\s+fees?|deposit|charges?)\s*(?:of\s*)?(?:rs\.?|inr|₹)?\s*\d+\b",
            combined_text,
            re.I,
        )
        guarantee_match = re.search(
            r"\b(?:guaranteed?\s+(?:job|placement|selection|visa)|100%\s+placement)\b",
            combined_text,
            re.I,
        )
        # Avoid false positives where text says "no registration fee" or "free application"
        negated_fee = re.search(
            r"\b(?:no|zero|without|not\s+required|free)\s+(?:registration|application|security)?\s*(?:fee|deposit|charge)\b",
            combined_text,
            re.I,
        )

        if fee_match and not negated_fee and (guarantee_match or category in {"job", "internship", "scholarship"}):
            score -= 40.0
            has_critical_red_flag = True
            sig = f"Upfront fee requirement detected for opportunity ('{fee_match.group(0)}')"
            signals.append(sig)
            negative_indicators.append(sig)

        # B. Suspicious public webmail for official programs
        public_email_match = re.search(
            r"\b[A-Za-z0-9._%+-]+@(gmail|yahoo|hotmail|outlook|rediffmail)\.com\b",
            combined_text,
            re.I,
        )
        if public_email_match:
            email_addr = public_email_match.group(0)
            if is_gov or category == "government_scheme" or "ministry" in combined_text.lower():
                score -= 40.0
                has_critical_red_flag = True
                sig = f"Official government scheme/notice references public free webmail address ({email_addr})"
                signals.append(sig)
                negative_indicators.append(sig)
            else:
                score -= 10.0
                negative_indicators.append(f"Uses public email address ({email_addr}) rather than organizational domain")

        # C. Urgent financial transfer requests
        urgency_match = re.search(
            r"\b(?:pay\s+(?:within|in)\s+\d+\s+hours|urgent\s+fee|immediate\s+payment\s+required|transfer\s+via\s+(?:gpay|phonepe|paytm|upi))\b",
            combined_text,
            re.I,
        )
        if urgency_match:
            score -= 30.0
            has_critical_red_flag = True
            sig = f"High-pressure financial payment tactic detected ('{urgency_match.group(0)}')"
            signals.append(sig)
            negative_indicators.append(sig)

        # D. Sensitive credential phishing
        phishing_match = re.search(
            r"\b(?:OTP|bank\s+account\s+password|ATM\s+PIN|CVV|credit\s+card\s+number|net\s+banking\s+password)\b",
            combined_text,
            re.I,
        )
        if phishing_match:
            score -= 50.0
            has_critical_red_flag = True
            sig = f"Demands sensitive banking credentials or security codes ('{phishing_match.group(0)}')"
            signals.append(sig)
            negative_indicators.append(sig)

        # E. Unrealistic compensation / get-rich-quick
        unrealistic_match = re.search(
            r"\b(?:earn\s+(?:rs\.?|inr|₹)?\s*\d{5,}\s+(?:per|a)\s+day|earn\s+lakhs?\s+without\s+work|no\s+skills?\s+earn\s+money)\b",
            combined_text,
            re.I,
        )
        if unrealistic_match:
            score -= 25.0
            sig = "Unrealistic compensation promise detected without verifiable prerequisites"
            signals.append(sig)
            negative_indicators.append(sig)

        # -------------------------------------------------------------------
        # 3. Final Score Clamping & Classification
        # -------------------------------------------------------------------
        if has_critical_red_flag:
            score = min(score, 45.0)

        final_score = max(0.0, min(100.0, score))

        # Only opportunities from verified government or academic sources with score >= verified_threshold can be VERIFIED.
        if final_score >= self.verified_threshold and official_match and not has_critical_red_flag:
            status = "VERIFIED"
        elif final_score < self.unverified_threshold or has_critical_red_flag:
            status = "SUSPICIOUS"
        else:
            status = "UNVERIFIED"

        if not signals:
            signals.append(f"Opportunity assessed with neutral trust indicators ({status})")

        return TrustReport(
            opportunity_id=opp_id,
            trust_score=final_score,
            status=status,
            signals=signals,
            official_domain_match=official_match,
            positive_indicators=positive_indicators,
            negative_indicators=negative_indicators,
            domain=primary_domain,
        )


# Global helper instance
_checker_instance = TrustChecker()


def check_opportunity_trust(opportunity: Dict[str, Any]) -> TrustReport:
    """Convenience function evaluating trust for an opportunity dictionary."""
    return _checker_instance.evaluate(opportunity)


from app.models.trust_report import TrustReport as BackendTrustReport
import re
from datetime import date
from urllib.parse import urlsplit


def analyze(data):
    text = " ".join(str(data.get(k) or "") for k in ("title", "description", "benefit"))
    evidence = []

    def add(kind, points, quote):
        evidence.append(dict(signal=kind, points=points, quote=quote))

    # Remove explicitly negated fee clauses before detecting requests for payment.
    fee_text = re.sub(
        r"\b(?:no|without|zero)\s+(?:(?:registration|application|processing|upfront|security)\s+)?(?:fees?|deposits?)\b|\b(?:fees?|deposits?)\s+(?:is\s+|are\s+)?not\s+required\b|\bfree\s+(?:registration|application)\b",
        "",
        text,
        flags=re.I,
    )
    fee = re.search(
        r"\b(?:(?:registration|application|processing|upfront|security)\s+(?:fees?|deposits?)|pay.{0,20}(?:fee|deposit))\b",
        fee_text,
        re.I,
    )
    if fee:
        add("UPFRONT_PAYMENT", 40, fee.group())
    guarantee = re.search(r"\bguaranteed?\s+(?:job|placement|selection)\b", text, re.I)
    if guarantee:
        add("GUARANTEED_SELECTION", 20, guarantee.group())
    sensitive = re.search(r"\b(?:OTP|bank[ -]?password|credit[ -]?card)\b", text, re.I)
    if sensitive:
        add("SENSITIVE_INFORMATION", 50, sensitive.group())
    application, company = data.get("application_url"), data.get("company_url")
    if application and company and urlsplit(application).hostname != urlsplit(company).hostname:
        add(
            "DOMAIN_DIFFERENCE",
            10,
            "May be a legitimate third-party applicant tracking system; review required",
        )
    score = min(100, sum(e["points"] for e in evidence))
    deadline = data.get("deadline")
    expired = bool(deadline and date.fromisoformat(deadline) < date.today())
    return BackendTrustReport(
        risk_score=score,
        risk_level="HIGH" if score >= 60 else "REVIEW" if score else "NO_SIGNALS_DETECTED",
        verification_status="EXPIRED" if expired else "UNKNOWN",
        evidence=evidence,
        disclaimer="Heuristic signals are not verified fraud classification. Reachability does not verify an employer.",
    ).model_dump(mode="json")
