"""Optional adapter boundary. Payload identity is never authentication."""

from app.utils.auth import verify_token


def authenticated_identity(access_token: str):
    return verify_token(access_token)["sub"]


def handler(payload, access_token=None):
    if not access_token:
        raise PermissionError("A verified provider token is required; student_id is not identity")
    owner = authenticated_identity(access_token)
    return {
        "owner_id": owner,
        "status": "USE_PERSISTENT_CAREER_API",
        "message": "Invoke /api/v1/career-agent with the verified bearer token",
    }
