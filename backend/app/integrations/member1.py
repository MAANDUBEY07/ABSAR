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
    if callable(getattr(value, "to_dict", None)):
        return value.to_dict()
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
    import inspect

    function = getattr(import_module("app.services.resume_analyzer"), "analyze_resume")
    signature = inspect.signature(getattr(function, "side_effect", None) or function)
    try:
        signature.bind(text, owner_id, document_id)
        legacy = True
    except TypeError:
        legacy = False
    result = (
        _invoke("app.services.resume_analyzer", "analyze_resume", text, owner_id, document_id)
        if legacy
        else _invoke("app.services.resume_analyzer", "analyze_resume", text)
    )
    try:
        payload = _payload(result)
        if "parsed_skills" in payload and "owner_id" not in payload:
            from app.integrations.resume_claims import claims

            payload = dict(
                payload,
                owner_id=owner_id,
                document_id=document_id,
                skills=payload["parsed_skills"],
                evidence=claims(text),
                warnings=[
                    "Rule-based estimates; absence of evidence is not proof of no experience"
                ],
                disclaimer="Deterministic resume claims and completeness score; not verified qualifications",
            )
        analysis = ResumeAnalysis.model_validate(payload)
        if analysis.owner_id != owner_id or analysis.document_id != document_id:
            raise ValueError("Provider result crossed ownership boundary")
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


def ingest_scraped(result):
    from app.schemas.opportunity import OpportunityInput
    from app.services.catalog import create_opportunity

    source = _payload(result)
    data = {key: value for key, value in source.items() if key in OpportunityInput.model_fields}
    data.update(
        source_attribution=source.get("source_name"),
        retrieved_at=source.get("scraped_at"),
        benefit=source.get("stipend_or_benefit"),
        provenance=source,
    )
    data["requirements"] = dict(
        confirmed=False, required_skills=source.get("required_skills") or []
    )
    return create_opportunity(data)


def discover_source(source_id, owner_id):
    from types import SimpleNamespace
    from app.services.scraper import OpportunityScraperService
    from app.services.safe_fetch import fetch

    class PinnedSession:
        headers = {}

        def get(self, url, timeout=10):
            return SimpleNamespace(
                status_code=200, text=fetch(url).decode("utf-8", errors="replace")
            )

    adapter = OpportunityScraperService().get_adapter_for_source(source_id, session=PinnedSession())
    if adapter is None:
        raise AIServiceUnavailable("Unknown registered source")
    results = adapter.collect()
    ids = [ingest_scraped(result)["id"] for result in results[:50]]
    return dict(owner_id=owner_id, opportunity_ids=ids, source_id=source_id)
