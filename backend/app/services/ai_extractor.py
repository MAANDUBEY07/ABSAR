"""
AI Opportunity Extractor
========================
Uses Gemini to extract structured opportunity information
from text obtained from notices, circulars, and PDFs.

Important:
- The model must not invent missing information.
- Unknown fields must remain None or empty.
- Extracted data is validated using Pydantic.
"""

import html
import json
import logging
import os
import re
from typing import Any, Literal

from dotenv import load_dotenv
from google import genai
from google.genai import types
from pydantic import BaseModel, Field, ValidationError

logger = logging.getLogger(__name__)

load_dotenv()

# Currently verified, supported, low-latency Gemini model in Google GenAI API
DEFAULT_GEMINI_MODEL = "gemini-3.5-flash-lite"

# Request timeout in milliseconds (30 seconds)
DEFAULT_TIMEOUT_MS = 30000

OpportunityCategory = Literal[
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

OpportunityMode = Literal["online", "offline", "hybrid"]


class ExtractedOpportunity(BaseModel):
    """Structured information extracted from an opportunity notice."""

    title: str | None = None
    category: OpportunityCategory | None = None

    organization: str | None = None
    description: str | None = None

    source_url: str | None = None
    application_url: str | None = None

    # Keep dates as strings because notices may use different formats.
    deadline: str | None = None

    eligibility_criteria: list[str] = Field(default_factory=list)
    required_skills: list[str] = Field(default_factory=list)

    location: str | None = None
    opportunity_mode: OpportunityMode | None = None
    stipend_or_benefit: str | None = None

    category_metadata: dict[str, Any] = Field(default_factory=dict)
    missing_fields: list[str] = Field(default_factory=list)


def _sanitize_error_message(error: Exception, api_key: str | None, model_name: str) -> str:
    """Removes sensitive credentials and generates actionable error descriptions."""
    raw = str(error)
    if api_key and len(api_key) > 5 and api_key in raw:
        raw = raw.replace(api_key, "[REDACTED_API_KEY]")

    if "504" in raw or "DEADLINE_EXCEEDED" in raw:
        return (
            f"Gemini API request timed out (504 DEADLINE_EXCEEDED). "
            f"The model '{model_name}' may be experiencing high latency or upstream queuing. "
            f"Details: {raw}"
        )
    if "404" in raw or "NOT_FOUND" in raw:
        return (
            f"Gemini model '{model_name}' was not found or is no longer available (404 NOT_FOUND). "
            f"Please update GEMINI_MODEL in .env to a supported model such as '{DEFAULT_GEMINI_MODEL}'. "
            f"Details: {raw}"
        )
    if "429" in raw or "RESOURCE_EXHAUSTED" in raw:
        return (
            f"Gemini API rate limit or quota exceeded (429 RESOURCE_EXHAUSTED). "
            f"Please wait before retrying. Details: {raw}"
        )
    if "401" in raw or "403" in raw or "API_KEY_INVALID" in raw or "PERMISSION_DENIED" in raw:
        return (
            f"Gemini API authentication failed. "
            f"Please verify that GEMINI_API_KEY in .env is valid and active. Details: {raw}"
        )
    return raw


def get_gemini_client(api_key: str, timeout_ms: int = DEFAULT_TIMEOUT_MS) -> genai.Client:
    """
    Creates a configured Gemini API client with exponential backoff retry handling
    for transient errors (408, 429, 500, 502, 503, 504).
    """
    retry_options = types.HttpRetryOptions(
        attempts=3,
        initial_delay=1.0,
        max_delay=10.0,
        exp_base=2.0,
        http_status_codes=[408, 429, 500, 502, 503, 504],
    )

    http_options = types.HttpOptions(
        timeout=timeout_ms,
        retry_options=retry_options,
    )

    return genai.Client(
        api_key=api_key,
        http_options=http_options,
    )


def clean_notice_text(raw_text: str) -> str:
    """
    Cleans noisy input text extracted from web pages or PDFs:
    - Decodes HTML entities (&amp;, &nbsp;, &#39;, etc.)
    - Normalizes unicode whitespace and non-breaking spaces
    - Cleans up common header/footer page artifacts (e.g. 'Page 1 of 5')
    - Collapses excessive blank lines while preserving paragraph structure
    """
    if not raw_text:
        return ""

    text = html.unescape(raw_text)
    # Replace non-breaking spaces and zero-width spaces
    text = text.replace("\u00a0", " ").replace("\u200b", "")

    # Strip page number artifacts
    text = re.sub(r"(?im)^\s*Page\s+\d+\s+(?:of|/)\s+\d+\s*$", "", text)
    text = re.sub(r"(?im)^\s*Downloaded\s+from\s+.*$", "", text)

    # Collapse horizontal whitespace
    text = re.sub(r"[ \t]+", " ", text)
    # Collapse 3+ newlines into 2
    text = re.sub(r"\n\s*\n\s*\n+", "\n\n", text)
    return text.strip()


def normalize_extracted_opportunity(
    opp: ExtractedOpportunity,
    notice_text: str,
    source_url: str | None = None,
) -> ExtractedOpportunity:
    """
    Normalizes and enriches extracted opportunity data:
    - Populates source_url if missing
    - Extracts application/registration link from text if missing or invalid
    - Infers opportunity_mode from location or notice text
    - Identifies essential missing fields and populates missing_fields
    """
    if source_url and not opp.source_url:
        opp.source_url = source_url

    # 1. URL resolution: if application_url is missing or invalid, search notice text
    if not opp.application_url or not opp.application_url.startswith(("http://", "https://")):
        url_matches = re.findall(
            r"https?://(?:www\.)?[-a-zA-Z0-9@:%._+~#=]{1,256}\.[a-zA-Z0-9()]{1,6}\b[-a-zA-Z0-9()@:%_+.~#?&/=]*",
            notice_text,
        )
        if url_matches:
            # Prefer links mentioning apply, register, forms, or portal
            preferred = [
                u
                for u in url_matches
                if re.search(r"apply|register|form|portal|join|scholarship", u, re.IGNORECASE)
            ]
            opp.application_url = preferred[0] if preferred else url_matches[0]
        elif source_url:
            opp.application_url = source_url

    # 2. Opportunity mode inference
    if not opp.opportunity_mode:
        loc_and_desc = f"{opp.location or ''} {opp.description or ''} {notice_text[:500]}".lower()
        if re.search(r"\b(?:remote|virtual|online|work\s+from\s+home|wfh)\b", loc_and_desc):
            opp.opportunity_mode = "online"
        elif re.search(r"\bhybrid\b", loc_and_desc):
            opp.opportunity_mode = "hybrid"
        elif opp.location and re.search(r"\b[a-zA-Z]{3,}\b", opp.location):
            opp.opportunity_mode = "offline"

    # 3. Missing fields audit
    missing: set[str] = set(opp.missing_fields)
    field_checks = [
        ("title", opp.title),
        ("organization", opp.organization),
        ("deadline", opp.deadline),
        ("application_url", opp.application_url),
        ("location", opp.location),
        ("stipend_or_benefit", opp.stipend_or_benefit),
    ]
    for name, val in field_checks:
        if not val and name not in missing:
            missing.add(name)
        elif val and name in missing:
            missing.discard(name)

    opp.missing_fields = sorted(missing)
    return opp


def extract_opportunity_heuristics(
    notice_text: str,
    source_url: str | None = None,
) -> ExtractedOpportunity:
    """
    Rule-based and regex heuristic extractor that functions offline or as a fallback
    when LLM access is unavailable. Identifies categories, deadlines, organizations,
    stipends, and eligibility requirements.
    """
    cleaned = clean_notice_text(notice_text)
    lower = cleaned.lower()

    # 1. Category Detection across all 11 canonical categories
    category: OpportunityCategory = "job"
    if re.search(r"\binnovation\s+challenge|smart\s+india\s+hackathon|sih\b", lower):
        category = "innovation_challenge"
    elif re.search(r"\bcoding\s+competition|competitive\s+programming|codechef|leetcode\b", lower):
        category = "coding_competition"
    elif re.search(r"\bhackathon|buildathon\b", lower):
        category = "hackathon"
    elif re.search(r"\bfellow(?:ship)?|pmrf|post-?doctoral\b", lower):
        category = "fellowship"
    elif re.search(r"\bapprentice(?:ship)?|nats|naps|vocational\s+training\b", lower):
        category = "apprenticeship"
    elif re.search(r"\bstartup|pitch\s+deck|seed\s+fund|accelerator|incubat(?:ion|or)\b", lower):
        category = "startup_challenge"
    elif re.search(r"\bgrant|research\s+fund|financial\s+grant\b", lower):
        category = "grant"
    elif re.search(r"\bscholarship|merit-cum-means|tuition\s+waiver\b", lower):
        category = "scholarship"
    elif re.search(r"\bgovernment\s+scheme|yojana|pradhan\s+mantri|kalyan\b", lower):
        category = "government_scheme"
    elif re.search(r"\bintern(?:ship)?|summer\s+intern|industrial\s+trainee\b", lower):
        category = "internship"

    # 2. Title Extraction
    lines = [line.strip() for line in cleaned.splitlines() if line.strip()]
    title = lines[0] if lines else "Extracted Opportunity"
    # If first line looks like a header or date, look at second line
    if (len(title) > 120 or re.match(r"^date:|^notice\s+no", title, re.IGNORECASE)) and len(
        lines
    ) > 1:
        title = lines[1]
    if title.isupper() and len(title) > 3:
        title = title.title()

    # 3. Organization Extraction
    org = None
    org_match = re.search(
        r"(?:Organization|Company|Ministry|Establishment|Institution|University|Hosted by|Issued by):\s*([^\n\r]+)",
        cleaned,
        re.IGNORECASE,
    )
    if org_match:
        org = org_match.group(1).strip()
    else:
        # Common entity pattern
        entity_match = re.search(
            r"\b([A-Z][A-Za-z0-9\s,&.-]+(?:Foundation|Ministry|Department|University|Institute|Corporation|Ltd|LLP|Inc))\b",
            cleaned,
        )
        if entity_match:
            org = entity_match.group(1).strip()

    # 4. Deadline Extraction
    deadline = None
    deadline_match = re.search(
        r"(?:Deadline|Last\s+Date|Apply\s+by|Closing\s+Date|Submission\s+Deadline):\s*([0-9]{1,2}[/-][0-9]{1,2}[/-][0-9]{4}|[0-9]{4}-[0-9]{2}-[0-9]{2}|[0-9]{1,2}\s+[A-Za-z]+\s+[0-9]{4})",
        cleaned,
        re.IGNORECASE,
    )
    if deadline_match:
        deadline = deadline_match.group(1).strip()
    else:
        # Standalone date near deadline keywords
        date_match = re.search(
            r"\b([0-9]{1,2}[/-][0-9]{1,2}[/-][0-9]{4}|[0-9]{4}-[0-9]{2}-[0-9]{2})\b",
            cleaned,
        )
        if date_match:
            deadline = date_match.group(1).strip()

    # 5. Eligibility Criteria
    eligibility_list: list[str] = []
    elig_section = re.search(
        r"(?:Eligibility|Requirements|Who can apply|Prerequisites):([\s\S]*?)(?:Duration|Location|Stipend|Reward|Deadline|How to apply|\Z)",
        cleaned,
        re.IGNORECASE,
    )
    if elig_section:
        sec_text = elig_section.group(1).strip()
        bullet_items = re.findall(r"^[ \t]*[-*•\d.]+[ \t]+([^\n\r]+)", sec_text, re.MULTILINE)
        if bullet_items:
            eligibility_list = [b.strip() for b in bullet_items if len(b.strip()) > 3]
        elif sec_text:
            eligibility_list = [
                line.strip() for line in sec_text.splitlines() if len(line.strip()) > 5
            ]

    # 6. Rewards / Stipend
    stipend = None
    stipend_match = re.search(
        r"(?:Stipend|Salary|Prize\s+Pool|Reward|Financial\s+Support|Grant\s+Amount):\s*([^\n\r]+)",
        cleaned,
        re.IGNORECASE,
    )
    if stipend_match:
        stipend = stipend_match.group(1).strip()
    else:
        money_match = re.search(
            r"\b(?:Rs\.?|INR|₹)\s*[0-9,]+(?:\s*(?:per|/)\s*month)?\b",
            cleaned,
            re.IGNORECASE,
        )
        if money_match:
            stipend = money_match.group(0).strip()

    # 7. Location & Mode
    location = None
    loc_match = re.search(r"(?:Location|Venue|City):\s*([^\n\r]+)", cleaned, re.IGNORECASE)
    if loc_match:
        location = loc_match.group(1).strip()
    elif re.search(r"\bpan-?india\b", lower):
        location = "Pan-India"

    mode: OpportunityMode = "offline"
    if re.search(r"\b(?:remote|online|virtual|work\s+from\s+home)\b", lower):
        mode = "online"
    elif re.search(r"\bhybrid\b", lower):
        mode = "hybrid"

    # 8. Category Metadata
    metadata: dict[str, Any] = {}
    if category == "hackathon":
        metadata["mode"] = mode
        if stipend:
            metadata["prize_pool"] = stipend
    elif category == "fellowship":
        metadata["research_focused"] = True
    elif category == "apprenticeship":
        metadata["scheme_type"] = "NATS/NAPS"

    opp = ExtractedOpportunity(
        title=title,
        category=category,
        organization=org,
        description=cleaned[:400] + ("..." if len(cleaned) > 400 else ""),
        source_url=source_url,
        deadline=deadline,
        eligibility_criteria=eligibility_list,
        location=location,
        opportunity_mode=mode,
        stipend_or_benefit=stipend,
        category_metadata=metadata,
    )
    return normalize_extracted_opportunity(opp, cleaned, source_url)


def extract_opportunity(
    notice_text: str,
    source_url: str | None = None,
    fallback_on_error: bool = False,
) -> ExtractedOpportunity:
    """
    Extract opportunity information from notice text using Gemini with heuristic fallback support.

    Args:
        notice_text: Text extracted from a PDF or webpage.
        source_url: Original URL of the notice, if available.
        fallback_on_error: If True, uses rule-based heuristic extraction when LLM fails.

    Returns:
        Validated ExtractedOpportunity object.

    Raises:
        ValueError: If input is empty or extraction fails.
        RuntimeError: If Gemini configuration or API access fails and fallback is disabled.
    """

    if not notice_text or not notice_text.strip():
        raise ValueError("Notice text cannot be empty.")

    cleaned_notice = clean_notice_text(notice_text)

    if len(cleaned_notice) > 30000:
        raise ValueError("Notice text exceeds the maximum limit of 30,000 characters.")

    api_key = os.getenv("GEMINI_API_KEY")

    if not api_key:
        if fallback_on_error:
            logger.info("GEMINI_API_KEY missing; using heuristic fallback extractor.")
            return extract_opportunity_heuristics(cleaned_notice, source_url)
        raise RuntimeError("GEMINI_API_KEY is missing from the environment.")

    model_name = os.getenv("GEMINI_MODEL") or DEFAULT_GEMINI_MODEL

    prompt = f"""
You are AVSAR's opportunity information extraction system.

Extract factual information from the notice provided below.

STRICT RULES:
1. Only extract information explicitly supported by the notice.
2. Never invent an organization, deadline, skill, benefit, or eligibility rule.
3. If a field is not mentioned, return null.
4. If eligibility criteria are not mentioned, return an empty list.
5. If required skills are not mentioned, return an empty list.
6. Classify the opportunity accurately into one of the 11 supported categories:
   - scholarship: Government, private, or merit scholarships
   - internship: Technical, corporate, or research internships
   - job: Graduate, fresher, and entry-level jobs
   - government_scheme: Central and state public schemes
   - fellowship: Academic, research, and professional fellowships
   - apprenticeship: NATS, NAPS, and industrial apprenticeships
   - hackathon: Technical hackathons and buildathons
   - coding_competition: Algorithmic and competitive programming contests
   - innovation_challenge: Student innovation, hardware, and design challenges
   - startup_challenge: Incubation, pitch competitions, and startup grants
   - grant: Research, student, and academic innovation grants
   Do not guess or assume a category unless the notice text provides clear evidence.
7. Preserve the original meaning of eligibility conditions (age, percentage/CGPA, branch, domicile).
8. Distinguish application deadlines from notice publication dates.
9. Extract rewards/stipends: cash prizes, monthly stipends, tuition waivers into stipend_or_benefit.
10. Extract participation mode (online, offline, hybrid) if mentioned into opportunity_mode.
11. If an application URL or portal link is given, extract it into application_url.
12. Capture category-specific metadata (e.g. prize_pool, team_size, duration, stipend) into category_metadata where present.
13. Add important unavailable fields to missing_fields.
14. Return data matching the provided structured schema.

Original source URL:
{source_url or "Not provided"}

NOTICE TEXT:
{cleaned_notice}
"""

    try:
        client = get_gemini_client(api_key=api_key, timeout_ms=DEFAULT_TIMEOUT_MS)
        response = client.models.generate_content(
            model=model_name,
            contents=prompt,
            config={
                "response_mime_type": "application/json",
                "response_schema": ExtractedOpportunity,
                "temperature": 0,
            },
        )

        if response.parsed is not None:
            if isinstance(response.parsed, ExtractedOpportunity):
                return normalize_extracted_opportunity(response.parsed, cleaned_notice, source_url)

            validated = ExtractedOpportunity.model_validate(response.parsed)
            return normalize_extracted_opportunity(validated, cleaned_notice, source_url)

        if not response.text:
            raise ValueError("Gemini returned an empty response.")

        extracted_data = json.loads(response.text)
        validated = ExtractedOpportunity.model_validate(extracted_data)
        return normalize_extracted_opportunity(validated, cleaned_notice, source_url)

    except ValidationError as error:
        if fallback_on_error:
            logger.warning(
                "Validation failed for Gemini output; using heuristic fallback: %s",
                error,
            )
            return extract_opportunity_heuristics(cleaned_notice, source_url)
        raise ValueError(f"Extracted opportunity data failed validation: {error}") from error

    except json.JSONDecodeError as error:
        if fallback_on_error:
            logger.warning("Invalid JSON from Gemini; using heuristic fallback: %s", error)
            return extract_opportunity_heuristics(cleaned_notice, source_url)
        raise ValueError("Gemini returned invalid JSON.") from error

    except Exception as error:
        if fallback_on_error:
            logger.warning("Gemini extraction error; using heuristic fallback: %s", error)
            return extract_opportunity_heuristics(cleaned_notice, source_url)
        clean_msg = _sanitize_error_message(error, api_key, model_name)
        raise RuntimeError(f"Opportunity extraction failed: {clean_msg}") from None
