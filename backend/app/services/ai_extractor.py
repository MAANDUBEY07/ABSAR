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

import json
import logging
import os
from typing import Literal

from dotenv import load_dotenv
from google import genai
from google.genai import types
from pydantic import BaseModel, Field, ValidationError

logger = logging.getLogger(__name__)

load_dotenv()

# Operators must select a model available to their own account.
DEFAULT_GEMINI_MODEL = ""

# Request timeout in milliseconds (30 seconds)
DEFAULT_TIMEOUT_MS = 30000

OpportunityCategory = Literal[
    "scholarship",
    "internship",
    "job",
    "government_scheme",
    "grant",
]


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
    stipend_or_benefit: str | None = None

    missing_fields: list[str] = Field(default_factory=list)


def _sanitize_error_message(error: Exception, api_key: str | None, model_name: str) -> str:
    """Removes sensitive credentials and generates actionable error descriptions."""
    return (
        "Gemini provider request failed; verify credentials, model access, quota and connectivity"
    )


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


def extract_opportunity(
    notice_text: str,
    source_url: str | None = None,
) -> ExtractedOpportunity:
    """
    Extract opportunity information from notice text using Gemini.

    Args:
        notice_text: Text extracted from a PDF or webpage.
        source_url: Original URL of the notice, if available.

    Returns:
        Validated ExtractedOpportunity object.

    Raises:
        ValueError: If input is empty or extraction fails.
        RuntimeError: If Gemini configuration or API access fails.
    """

    if not notice_text or not notice_text.strip():
        raise ValueError("Notice text cannot be empty.")

    if len(notice_text) > 30000:
        raise ValueError("Notice text exceeds the maximum limit of 30,000 characters.")

    api_key = os.getenv("GEMINI_API_KEY")

    if not api_key:
        raise RuntimeError("GEMINI_API_KEY is missing from the environment.")

    model_name = os.getenv("GEMINI_MODEL") or DEFAULT_GEMINI_MODEL

    if not model_name:
        raise RuntimeError("GEMINI_MODEL must be configured for your account")

    prompt = f"""
You are AVSAR's opportunity information extraction system.

Extract factual information from the notice provided below.

STRICT RULES:
1. Only extract information explicitly supported by the notice.
2. Never invent an organization, deadline, skill, benefit, or eligibility rule.
3. If a field is not mentioned, return null.
4. If eligibility criteria are not mentioned, return an empty list.
5. If required skills are not mentioned, return an empty list.
6. Do not assume that an opportunity is a scholarship or internship
   unless the notice supports that classification.
7. Preserve the original meaning of eligibility conditions.
8. Do not convert vague deadlines into guessed dates.
9. Add important unavailable fields to missing_fields.
10. Return data matching the provided structured schema.

Original source URL:
{source_url or "Not provided"}

NOTICE TEXT:
{notice_text}
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
                return response.parsed

            return ExtractedOpportunity.model_validate(response.parsed)

        if not response.text:
            raise ValueError("Gemini returned an empty response.")

        extracted_data = json.loads(response.text)

        return ExtractedOpportunity.model_validate(extracted_data)

    except ValidationError:
        raise ValueError("Extracted opportunity data failed validation") from None

    except json.JSONDecodeError:
        raise ValueError("Gemini returned invalid JSON.") from None

    except Exception as error:
        clean_msg = _sanitize_error_message(error, api_key, model_name)
        raise RuntimeError(f"Opportunity extraction failed: {clean_msg}") from None
