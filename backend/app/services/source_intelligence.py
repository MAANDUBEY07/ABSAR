"""AVSAR Source Intelligence & Multilingual Requirement Extractor
============================================================
Responsible for fetching, analyzing, and extracting structured, evidence-backed
requirements and readable source summaries from original opportunity sources (English and German).

Supports:
- Pinned secure fetching with SSRF protection (safe_fetch).
- HTML and PDF source document parsing.
- Multilingual extraction (English and German).
- Fallback to catalog description and user-provided descriptions upon fetch failure.
- Evidence attribution for every extracted requirement.
- Deterministic canonical mapping to AVSAR requirements schema.
"""

from __future__ import annotations

import logging
import re
from typing import Any
from urllib.parse import urlsplit
from bs4 import BeautifulSoup

from app.models.opportunity import OpportunityDocument
from app.repositories import documents
from app.services.safe_fetch import fetch as safe_pinned_fetch, destination as validate_destination
from app.services import notice_parser

logger = logging.getLogger("opportunityos.source_intelligence")

GERMAN_INDICATORS = {
    "anforderungen", "voraussetzungen", "aufgaben", "bewerbung", "erfahrung",
    "standort", "deutsch", "vollzeit", "teilzeit", "kenntnisse", "abschluss",
    "studium", "wir suchen", "das bringst du mit", "ihr profil", "dein profil",
    "kontakt", "unternehmen", "arbeitszeit", "leistungen", "gehalt"
}

KNOWN_TECH_SKILLS = {
    "python", "java", "c++", "c#", "javascript", "typescript", "sql", "postgresql",
    "mysql", "mongodb", "docker", "kubernetes", "aws", "azure", "gcp", "git",
    "react", "angular", "vue", "next.js", "node.js", "fastapi", "django", "flask",
    "machine learning", "deep learning", "pytorch", "tensorflow", "scikit-learn",
    "data science", "nlp", "computer vision", "pandas", "numpy", "pyspark", "spark",
    "airflow", "dbt", "tableau", "power bi", "excel", "linux", "bash", "rest api",
    "graphql", "html", "css", "ci/cd", "terraform", "saas", "datev"
}


def detect_language(text: str) -> str:
    """Detect whether text is primarily German ('de') or English ('en')."""
    if not text:
        return "en"
    words = re.findall(r"\b[a-zA-ZäöüßÄÖÜ]+\b", text.casefold())
    german_hits = sum(1 for w in words if w in GERMAN_INDICATORS)
    return "de" if german_hits >= 3 else "en"


def fetch_source_document(url: str, timeout: int = 10) -> tuple[str | None, str | None, str]:
    """Safely fetch source text from a public URL with SSRF protection.

    Returns:
        (text, error_message, fetch_status)
        fetch_status is one of: 'SUCCESS', 'BLOCKED', 'INVALID_URL', 'NETWORK_ERROR'
    """
    if not url or not url.startswith(("http://", "https://")):
        return None, "Invalid or missing source URL", "INVALID_URL"

    # 1. SSRF validation
    try:
        validate_destination(url)
    except Exception as exc:
        logger.warning("SSRF or DNS protection rejected URL %s: %s", url, exc)
        return None, f"Destination security check failed: {exc}", "BLOCKED"

    # 2. PDF source handling
    if url.lower().endswith(".pdf") or ".pdf?" in url.lower():
        try:
            raw_bytes = safe_pinned_fetch(url, max_bytes=10 * 1024 * 1024)
            parsed = notice_parser.parse_pdf(raw_bytes)
            if parsed.text.strip():
                return parsed.text, None, "SUCCESS"
            return None, "PDF contained no readable text (scanned image)", "NETWORK_ERROR"
        except Exception as exc:
            logger.warning("Failed to fetch or parse PDF source %s: %s", url, exc)
            return None, f"PDF document fetch failed: {exc}", "NETWORK_ERROR"

    # 3. HTML source handling
    try:
        raw_bytes = safe_pinned_fetch(url, max_bytes=4 * 1024 * 1024)
        html_content = raw_bytes.decode("utf-8", errors="replace")
        soup = BeautifulSoup(html_content, "html.parser")

        # Strip unhelpful elements
        for tag in soup(["script", "style", "nav", "footer", "header", "aside", "noscript"]):
            tag.decompose()

        # Prioritize main content containers
        main_content = soup.find(["main", "article", "div[role='main']", "div.job-description", "div.description"])
        text = (main_content or soup.body or soup).get_text(separator="\n", strip=True)
        if len(text) > 80:
            return text, None, "SUCCESS"
        return None, "Page returned insufficient text content", "NETWORK_ERROR"
    except Exception as exc:
        logger.warning("Network or HTTP error fetching source %s: %s", url, exc)
        error_msg = str(exc)
        if "403" in error_msg or "blocked" in error_msg.lower() or "challenge" in error_msg.lower():
            return None, "Source website is protected by bot-check or requires login", "BLOCKED"
        return None, f"Could not reach source website: {exc}", "NETWORK_ERROR"


def extract_source_intelligence(
    text: str,
    source_url: str | None = None,
    fallback_title: str | None = None,
    fallback_org: str | None = None,
    is_user_provided: bool = False,
    fetch_status: str = "SUCCESS",
    failure_reason: str | None = None,
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Extract structured, evidence-backed requirements and a readable source summary.

    Supports both English and German documents.
    Returns:
        (source_summary, requirements)
    """
    cleaned_text = re.sub(r"\r\n|\r", "\n", text or "").strip()
    lang = detect_language(cleaned_text)
    lower_text = cleaned_text.lower()

    evidence: dict[str, str] = {}
    key_requirements: list[str] = []
    degrees: list[str] = []
    branches: list[str] = []
    required_skills: list[str] = []
    preferred_skills: list[str] = []
    languages: list[str] = []
    locations: list[str] = []
    min_experience_months: int | None = None
    min_cgpa: float | None = None

    # 1. Degree & Qualification Extraction (Multilingual)
    degree_patterns = [
        (r"\bb\.?\s*tech\b", "B.Tech"),
        (r"\bm\.?\s*tech\b", "M.Tech"),
        (r"\bbachelor(?:'s)?(?:\s+(?:degree|of|in))?\b", "Bachelor"),
        (r"\bmaster(?:'s)?(?:\s+(?:degree|of|in))?\b", "Master"),
        (r"\bph\.?d\b|\bdoctoral\b|\bdoktorat\b", "PhD"),
        (r"\bdiplom(?:\s+ingenieur)?\b", "Diplom"),
        (r"\bhochschulabschluss\b|\babgeschlossenes?\s+studium\b", "Bachelor/Master Degree"),
    ]
    for pattern, label in degree_patterns:
        m = re.search(pattern, lower_text)
        if m:
            degrees.append(label.casefold())
            # Capture context sentence as evidence
            start = max(0, m.start() - 60)
            end = min(len(cleaned_text), m.end() + 60)
            snippet = cleaned_text[start:end].replace("\n", " ").strip()
            evidence["degree"] = f"Source specifies {label}: \"...{snippet}...\""
            key_requirements.append(f"Degree: {label} (or equivalent)")
            break

    # 2. Branch & Field Extraction
    branch_patterns = [
        (r"\b(?:computer\s+science|informatik)\b", "computer science"),
        (r"\b(?:data\s+science|datenwissenschaft)\b", "data science"),
        (r"\b(?:wirtschaftsinformatik|business\s+informatics)\b", "information technology"),
        (r"\b(?:information\s+technology|it)\b", "information technology"),
        (r"\b(?:software\s+engineering|softwaretechnik)\b", "computer science"),
        (r"\b(?:mathematik|mathematics|statistics|statistik)\b", "mathematics"),
        (r"\b(?:engineering|ingenieurwesen)\b", "engineering"),
    ]
    for pattern, label in branch_patterns:
        m = re.search(pattern, lower_text)
        if m:
            if label not in branches:
                branches.append(label)
                start = max(0, m.start() - 50)
                end = min(len(cleaned_text), m.end() + 50)
                snippet = cleaned_text[start:end].replace("\n", " ").strip()
                evidence["branch"] = f"Field mentioned: \"...{snippet}...\""
                key_requirements.append(f"Field of study: {label.title()}")

    # 3. Experience Requirements (Multilingual)
    # German patterns: "mindestens 2 Jahre Berufserfahrung", "2-3 Jahre Erfahrung", "Erste Erfahrung"
    exp_de = re.search(
        r"(?:mindestens|ab|ca\.?|mehrjährige)?\s*(\d+)\s*(?:[-–]|bis|\+)?\s*(\d+)?\s*Jahre?(?:n)?\s+(?:Berufserfahrung|Erfahrung)",
        cleaned_text,
        re.IGNORECASE,
    )
    if exp_de:
        years = int(exp_de.group(1))
        min_experience_months = years * 12
        evidence["experience"] = f"Experience required: \"{exp_de.group(0).strip()}\""
        key_requirements.append(f"Experience: Minimum {years} year(s) ({min_experience_months} months)")
    elif re.search(r"\berste\s+erfahrung\b", lower_text):
        min_experience_months = 6
        evidence["experience"] = "Initial practical experience desired (\"Erste Erfahrung\")"
        key_requirements.append("Experience: Initial practical experience (approx. 6 months)")
    else:
        # English pattern (supports e.g. '1 year of practical research experience')
        exp_en = re.search(
            r"(?:at least|minimum|min\.?)?\s*(\d+)\+?\s*(?:to\s*(\d+))?\s*(?:years?|yrs?)\s*(?:of)?\s*(?:[a-zA-Z\s]{0,25})?\s*experience",
            lower_text,
        )
        if exp_en:
            years = int(exp_en.group(1))
            min_experience_months = years * 12
            start = max(0, exp_en.start() - 30)
            end = min(len(cleaned_text), exp_en.end() + 30)
            snippet = cleaned_text[start:end].replace("\n", " ").strip()
            evidence["experience"] = f"Experience required: \"...{snippet}...\""
            key_requirements.append(f"Experience: Minimum {years} year(s)")

    # 4. GPA / Grades
    cgpa_match = re.search(
        r"(?:min(?:imum)?\.?\s*(?:cgpa|gpa|percentage)|cgpa|gpa)\s*[:=-]?\s*(\d+(?:\.\d+)?)(?:\s*(?:\/|\s*out of\s*)\s*(\d+(?:\.\d+)?))?",
        lower_text,
    )
    if cgpa_match:
        val = float(cgpa_match.group(1))
        if val <= 10.0:
            min_cgpa = val
            evidence["cgpa"] = f"Minimum CGPA: {val}"
            key_requirements.append(f"Minimum academic score: CGPA {val}")

    # 5. Language Requirements
    if re.search(r"\bdeutsch\b|\bgerman\b", lower_text):
        level = "German"
        if re.search(r"c1|c2|flie[ßs]end|verhandlungssicher|sehr\s+gut", lower_text):
            level = "German (Fluent / C1-C2)"
        languages.append("German")
        evidence["language_german"] = f"Language requirement: {level}"
        key_requirements.append(f"Language: {level}")

    if re.search(r"\benglisch\b|\benglish\b", lower_text):
        level = "English"
        if re.search(r"fluent english|flie[ßs]end englisch|verhandlungssicher(?:es)?\s+englisch", lower_text):
            level = "English (Fluent)"
        languages.append("English")
        evidence["language_english"] = f"Language requirement: {level}"
        key_requirements.append(f"Language: {level}")

    # 6. Technical & Professional Skills
    # Isolate requirement sections vs preferred sections
    req_section = ""
    pref_section = ""

    req_match = re.search(
        r"(?:requirements|qualifications|anforderungen|dein profil|ihr profil|das bringst du mit|voraussetzungen|what you bring|prerequisites):([\s\S]*?)(?:benefits|wir bieten|tasks|aufgaben|das bieten wir|how to apply|how to register|\Z)",
        cleaned_text,
        re.IGNORECASE,
    )
    if req_match:
        req_section = req_match.group(1).lower()

    pref_match = re.search(
        r"(?:preferred|nice to have|plus|ein plus|vorteil|bevorzugt|bonus):([\s\S]*?)(?:benefits|wir bieten|how to apply|\Z)",
        cleaned_text,
        re.IGNORECASE,
    )
    if pref_match:
        pref_section = pref_match.group(1).lower()

    search_target = req_section if len(req_section) > 50 else lower_text
    for skill in KNOWN_TECH_SKILLS:
        pattern = r"\b" + re.escape(skill) + r"\b"
        if pref_section and re.search(pattern, pref_section):
            if skill not in preferred_skills:
                preferred_skills.append(skill)
        elif re.search(pattern, search_target):
            if skill not in required_skills and len(required_skills) < 8:
                required_skills.append(skill)

    # 7. Location & Work Mode
    mode = "offline"
    if re.search(r"\b(?:remote|online|virtual|home[- ]office|wfh)\b", lower_text):
        mode = "online"
    elif re.search(r"\bhybrid\b", lower_text):
        mode = "hybrid"

    # Known cities
    for city in ["Berlin", "München", "Munich", "Hamburg", "Frankfurt", "Köln", "Bengaluru", "Bangalore", "Delhi", "Pune", "Hyderabad", "Mumbai"]:
        if re.search(r"\b" + re.escape(city) + r"\b", cleaned_text, re.IGNORECASE):
            if city not in locations:
                locations.append(city)

    # 8. Important Dates & Deadlines
    deadline_date = None
    deadline_match = re.search(
        r"(?:deadline|last date|apply by|closing date|submission deadline|bewerbungsfrist):\s*([0-9]{1,2}[/-][0-9]{1,2}[/-][0-9]{4}|[0-9]{4}-[0-9]{2}-[0-9]{2}|[0-9]{1,2}\s+[A-Za-z]+\s+[0-9]{4})",
        cleaned_text,
        re.IGNORECASE,
    )
    important_dates = []
    if deadline_match:
        deadline_date = deadline_match.group(1).strip()
        important_dates.append(f"Application deadline: {deadline_date}")
    else:
        # Check for standalone dates near closing keywords
        date_cand = re.search(r"\b(\d{4}-\d{2}-\d{2})\b", cleaned_text)
        if date_cand:
            important_dates.append(f"Key date: {date_cand.group(1)}")

    # 9. Application Instructions
    app_instr = "Apply directly through the official provider link or application portal."
    if "bewerben" in lower_text:
        app_instr = "Online-Bewerbung über das Unternehmensportal mit Lebenslauf und relevanten Zeugnissen."
    elif re.search(r"\bapply\s+online|submit\s+(?:your\s+)?application|cv|resume\b", lower_text):
        app_instr = "Submit your application online with your resume and relevant credentials."

    # 10. Overview & Who Should Apply
    # Synthesize clean, readable overview
    paragraphs = [p.strip() for p in cleaned_text.split("\n\n") if len(p.strip()) > 40]
    overview = paragraphs[0] if paragraphs else (cleaned_text[:300] + ("..." if len(cleaned_text) > 300 else ""))
    if len(overview) > 600:
        overview = overview[:600] + "..."

    who_should_apply = "Students, recent graduates, or candidates meeting the stated qualification requirements."
    if degrees:
        who_should_apply = f"Students or graduates holding or pursuing {' / '.join(d.title() for d in degrees)} degrees"
        if branches:
            who_should_apply += f" in {', '.join(b.title() for b in branches)}"
        who_should_apply += "."
    elif "werkstudent" in lower_text or "student" in lower_text:
        who_should_apply = "Enrolled undergraduate or graduate students looking for practical industry experience."

    # Decide if confirmed criteria exist
    has_confirmed = bool(degrees or branches or min_experience_months or min_cgpa or required_skills or languages)

    requirements_payload: dict[str, Any] = {
        "confirmed": has_confirmed,
        "graduation_years": [],
        "degrees": degrees,
        "branches": branches,
        "min_cgpa": min_cgpa,
        "min_experience_months": min_experience_months,
        "locations": locations,
        "required_skills": required_skills,
        "preferred_skills": preferred_skills,
        "languages": languages,
        "evidence": evidence,
    }

    source_summary_payload: dict[str, Any] = {
        "title": fallback_title or "Opportunity Details",
        "organization": fallback_org or "Opportunity Provider",
        "overview": overview,
        "who_should_apply": who_should_apply,
        "key_requirements": key_requirements if key_requirements else (
            ["General competencies as detailed in the listing"] if has_confirmed else []
        ),
        "important_dates": important_dates,
        "application_instructions": app_instr,
        "source_url": source_url,
        "source_language": lang,
        "location_mode": mode,
        "locations": locations,
        "evidence": evidence,
        "fetch_status": fetch_status,
        "failure_reason": failure_reason,
        "is_user_provided": is_user_provided,
    }

    return source_summary_payload, requirements_payload


def enrich_opportunity(
    opp: dict[str, Any],
    user_description: str | None = None,
    force_refresh: bool = False,
) -> dict[str, Any]:
    """Inspect and refresh opportunity criteria and readable source summary.

    1. Uses original source_url where available.
    2. Falls back safely to existing catalog description or user-provided description.
    3. Persists updated intelligence into document store.
    """
    record_id = opp.get("id")
    source_url = opp.get("source_url") or opp.get("application_url")
    title = opp.get("title")
    org = opp.get("organization") or opp.get("provider")

    # If already confirmed and not forcing refresh or providing custom text, return as-is
    if (
        not force_refresh
        and not user_description
        and opp.get("requirements", {}).get("confirmed")
        and opp.get("source_summary")
    ):
        return opp

    text_to_analyze: str | None = None
    fetch_status = "SUCCESS"
    failure_reason: str | None = None
    is_user_provided = False

    # 1. User-provided description takes precedence if supplied
    if user_description and user_description.strip():
        text_to_analyze = user_description.strip()
        fetch_status = "USER_PROVIDED"
        is_user_provided = True
    elif source_url:
        # 2. Safe fetch from original source
        fetched, err, status = fetch_source_document(source_url)
        if fetched and len(fetched) > 80:
            text_to_analyze = fetched
            fetch_status = "SUCCESS"
        else:
            fetch_status = status
            failure_reason = err
            # 3. Fall back to existing catalog description
            if opp.get("description") and len(opp["description"].strip()) > 30:
                text_to_analyze = opp["description"].strip()
                fetch_status = "FALLBACK_TO_CATALOG"
    else:
        # Fall back to catalog description directly
        if opp.get("description") and len(opp["description"].strip()) > 30:
            text_to_analyze = opp["description"].strip()
            fetch_status = "FALLBACK_TO_CATALOG"
        else:
            fetch_status = "FAILED"
            failure_reason = "No source URL or description available"

    if text_to_analyze:
        source_summary, reqs = extract_source_intelligence(
            text_to_analyze,
            source_url=source_url,
            fallback_title=title,
            fallback_org=org,
            is_user_provided=is_user_provided,
            fetch_status=fetch_status,
            failure_reason=failure_reason,
        )
        opp["requirements"] = reqs
        opp["source_summary"] = source_summary
    else:
        # Honest fallback when no text could be obtained
        opp["source_summary"] = {
            "title": title or "Opportunity Details",
            "organization": org or "Opportunity Provider",
            "overview": opp.get("description") or "Detailed requirements could not be fetched from the source website.",
            "who_should_apply": "Please review the source website directly for participation criteria.",
            "key_requirements": [],
            "important_dates": [f"Deadline: {opp['deadline']}"] if opp.get("deadline") else [],
            "application_instructions": "Visit the original source to review requirements and apply.",
            "source_url": source_url,
            "source_language": "en",
            "evidence": {},
            "fetch_status": fetch_status,
            "failure_reason": failure_reason or "Source website could not be retrieved",
            "is_user_provided": False,
        }
        if not opp.get("requirements"):
            opp["requirements"] = {"confirmed": False}

    # Persist in local document store
    if record_id:
        try:
            documents.put("opportunities", record_id, opp)
        except Exception as exc:
            logger.warning("Could not persist enriched opportunity %s: %s", record_id, exc)

    return opp
