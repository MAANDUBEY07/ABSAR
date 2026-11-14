"""Pure normalization helpers and public-destination validation."""

from urllib.parse import urlsplit, urlunsplit
from app.services.safe_fetch import destination as validate_public_destination


def normalized(values):
    return {str(value).strip().casefold() for value in (values or []) if str(value).strip()}


def canonical_url(value):
    if not value:
        return None
    url = urlsplit(str(value))
    return urlunsplit((url.scheme.lower(), url.netloc.lower(), url.path.rstrip("/"), url.query, ""))


__all__ = ["normalized", "canonical_url", "validate_public_destination"]
