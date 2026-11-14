"""Call Member 1 modules through narrow, mockable integration boundaries.

Only interfaces already present in this checkout are called. Unavailable or incompatible
interfaces fail explicitly; this module never invents an AI implementation or fallback.
These are internal adapters, not independently published team API contracts.
"""

from importlib import import_module
from pydantic import BaseModel
from defusedxml.common import DefusedXmlException
from app.models.resume import ResumeAnalysis
from app.models.trust_report import TrustReport


class AIServiceUnavailable(RuntimeError):
    """The selected member-owned implementation is absent or incompatible."""


def _invoke(module_name, function_name, *args, **kwargs):
    try:
        function = getattr(import_module(module_name), function_name, None)
        if not callable(function):
            raise AIServiceUnavailable("Member 1 interface is not available")
        return function(*args, **kwargs)
    except DefusedXmlException:
        # Preserve the existing local XML-validation boundary; no provider request succeeded.
        raise
    except Exception:
        # Never expose provider exceptions, credentials, source text or personal data.
        raise AIServiceUnavailable(
            "Member 1 service is unavailable or returned incompatible data"
        ) from None


def _payload(value):
    if isinstance(value, BaseModel):
        return value.model_dump(mode="json")
    if isinstance(value, dict):
        return dict(value)
    raise AIServiceUnavailable("Member 1 service returned an incompatible result")


def analyze_trust(opportunity):
    result = _invoke("app.services.trust_checker", "analyze", opportunity)
    try:
        return TrustReport.model_validate(_payload(result)).model_dump(mode="json")
    except Exception:
        raise AIServiceUnavailable("Trust service returned incompatible data") from None


def analyze_resume(text, owner_id, document_id):
    result = _invoke("app.services.resume_analyzer", "analyze_resume", text, owner_id, document_id)
    try:
        analysis = ResumeAnalysis.model_validate(_payload(result))
        if analysis.owner_id != owner_id or analysis.document_id != document_id:
            raise ValueError("Provider result crossed the backend ownership boundary")
        return analysis.model_dump(mode="json")
    except Exception:
        raise AIServiceUnavailable(
            "Resume service returned incompatible ownership or data"
        ) from None


def discover_feed(feed_url, owner_id):
    result = _payload(_invoke("app.services.scraper", "discover_feed", feed_url, owner_id))
    ids = result.get("opportunity_ids")
    if (
        result.get("owner_id") != owner_id
        or not isinstance(ids, list)
        or not all(isinstance(value, str) for value in ids)
    ):
        raise AIServiceUnavailable("Discovery service returned incompatible ownership or data")
    return result


def parse_notice(pdf_bytes):
    # Return Member 1's own result/schema without substituting another parser.
    return _invoke("app.services.notice_parser", "parse_pdf", pdf_bytes)


def extract_notice(text, source_url=None):
    return _invoke("app.services.ai_extractor", "extract_opportunity", text, source_url=source_url)


def compare_opportunities(candidate, existing, config=None):
    return _invoke(
        "app.services.duplicate_detector", "compare_opportunities", candidate, existing, config
    )
