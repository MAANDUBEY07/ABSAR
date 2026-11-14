from app.models.trust_report import TrustReport
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
    return TrustReport(
        risk_score=score,
        risk_level="HIGH" if score >= 60 else "REVIEW" if score else "NO_SIGNALS_DETECTED",
        verification_status="EXPIRED" if expired else "UNKNOWN",
        evidence=evidence,
        disclaimer="Heuristic signals are not verified fraud classification. Reachability does not verify an employer.",
    ).model_dump(mode="json")
