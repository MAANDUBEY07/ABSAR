"""Backend normalization; uncertain source facts stay unknown, never guessed."""

from datetime import date, datetime


def deadline(value):
    if value is None or value == "":
        return None
    if isinstance(value, datetime):
        raise ValueError("Deadline must be a calendar date")
    if isinstance(value, date):
        return value
    if not isinstance(value, str):
        raise ValueError("Deadline must be a calendar date")
    value = value.strip()
    for fmt in ("%Y-%m-%d", "%Y/%m/%d", "%d %B %Y", "%d %b %Y"):
        try:
            return datetime.strptime(value, fmt).date()
        except ValueError:
            pass
    # Accept numeric day/month only where order is unambiguous.
    parts = value.replace("-", "/").split("/")
    if len(parts) == 3 and all(part.isdigit() for part in parts) and len(parts[2]) == 4:
        first, second, year = map(int, parts)
        if first > 12 and second <= 12:
            return date(year, second, first)
        if second > 12 and first <= 12:
            return date(year, first, second)
        if first == second:
            return date(year, second, first)
    raise ValueError("Invalid or ambiguous deadline; supply YYYY-MM-DD")


def opportunity_view(record):
    """Non-destructive compatibility view; never rewrite historical IDs/fingerprints."""
    result = dict(record)
    if result.get("category") == "coding_challenge":
        result["category"] = "coding_competition"
    # Research is not synonymous with innovation; retain it pending human reclassification.
    if result.get("opportunity_mode") is None and result.get("remote") is True:
        result["opportunity_mode"] = "online"
    result.setdefault("category_metadata", {})
    return result
