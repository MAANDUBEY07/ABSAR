"""Compose existing Member 1 services without implementing AI behavior."""

from pathlib import Path
from app.integrations import member1
from app.integrations.normalization import deadline


def extract_draft(content, filename):
    if Path(filename).suffix.lower() != ".pdf":
        raise ValueError("Member 1 notice pipeline currently requires PDF input")
    parsed = member1.parse_notice(content)
    if not parsed.has_extractable_text:
        raise ValueError("Notice has no extractable text; OCR or human review required")
    result = member1.extract_notice(parsed.text)
    data = result.model_dump(mode="json")
    warnings = list(parsed.warnings)
    try:
        normalized_date = deadline(data.get("deadline"))
    except ValueError:
        normalized_date = None
        warnings.append("Source deadline is ambiguous or invalid; confirm manually")
    draft = dict(
        title=data.get("title"),
        category=data.get("category") or "other",
        organization=data.get("organization"),
        description=data.get("description") or parsed.text,
        application_url=data.get("application_url"),
        source_url=data.get("source_url"),
        deadline=normalized_date.isoformat() if normalized_date else None,
        location=data.get("location"),
        benefit=data.get("stipend_or_benefit"),
        opportunity_mode=data.get("opportunity_mode"),
        category_metadata=data.get("category_metadata") or {},
        requirements={"confirmed": False, "required_skills": data.get("required_skills") or []},
        provenance="MEMBER1_AI_EXTRACTION",
        missing_fields=data.get("missing_fields") or [],
        source_eligibility_criteria=data.get("eligibility_criteria") or [],
    )
    return dict(draft=draft, warnings=warnings, text=parsed.text, page_count=parsed.page_count)
