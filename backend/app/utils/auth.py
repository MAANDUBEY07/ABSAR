from functools import lru_cache
from uuid import UUID
import jwt
import httpx
from fastapi import Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from app.config import settings
from app.config.database import get_db
from app.models.profile import Profile
from app.schemas.profile import ProfileInput
from sqlalchemy.exc import IntegrityError

bearer = HTTPBearer(auto_error=False)


@lru_cache(maxsize=8)
def jwks_client(url):
    return jwt.PyJWKClient(url, cache_keys=True, lifespan=300, timeout=5)


def verify_legacy_supabase_token(token, issuer):
    """Legacy symmetric keys are not published in JWKS. Ask the issuer to verify."""
    if not settings.supabase_anon_key:
        raise ValueError("Supabase public API key is required")
    claims = jwt.decode(
        token,
        algorithms=["HS256"],
        audience="authenticated",
        issuer=issuer,
        options={
            "verify_signature": False,
            "verify_exp": True,
            "verify_nbf": True,
            "verify_aud": True,
            "verify_iss": True,
            "require": ["sub", "exp", "iss", "aud"],
        },
    )
    if claims.get("role") != "authenticated":
        raise ValueError("Unauthenticated role")
    UUID(claims["sub"])
    try:
        response = httpx.get(
            issuer + "/user",
            headers={"apikey": settings.supabase_anon_key, "Authorization": "Bearer " + token},
            timeout=5,
            follow_redirects=False,
        )
    except httpx.RequestError:
        raise HTTPException(503, "Authentication service unavailable. Please try again.") from None
    if response.status_code in {401, 403}:
        raise ValueError("Supabase rejected token")
    if response.status_code != 200:
        raise HTTPException(503, "Authentication service unavailable. Please try again.")
    try:
        user = response.json()
    except ValueError:
        raise HTTPException(503, "Authentication service returned an invalid response") from None
    if not isinstance(user, dict) or user.get("id") != claims["sub"]:
        raise ValueError("Token identity mismatch")
    return claims


def verify_token(token):
    if len(token) > 16384:
        raise ValueError("Oversized token")
    if settings.auth_provider == "local":
        if settings.hosted:
            raise ValueError("Local auth disabled")
        claims = jwt.decode(
            token,
            settings.jwt_secret,
            algorithms=["HS256"],
            audience="opportunityos",
            issuer="opportunityos-local",
            options={"require": ["sub", "exp", "iat", "iss", "aud"]},
        )
    else:
        if settings.auth_provider != "supabase":
            raise ValueError("Unsupported authentication provider")
        issuer = settings.supabase_url.rstrip("/") + "/auth/v1"
        algorithms, audience = ["RS256", "ES256"], "authenticated"
        url = issuer + "/.well-known/jwks.json"
        header = jwt.get_unverified_header(token)
        if header.get("alg") == "HS256":
            return verify_legacy_supabase_token(token, issuer)
        if header.get("alg") not in algorithms or not isinstance(header.get("kid"), str):
            raise ValueError("Untrusted algorithm")
        key = jwks_client(url).get_signing_key_from_jwt(token).key
        claims = jwt.decode(
            token,
            key,
            algorithms=algorithms,
            audience=audience,
            issuer=issuer,
            options={"require": ["sub", "exp", "iss", "aud"]},
        )
        if settings.auth_provider == "supabase" and claims.get("role") != "authenticated":
            raise ValueError("Unauthenticated role")
    UUID(claims["sub"])
    return claims


def identity(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer), db=Depends(get_db)
):
    try:
        if credentials is None:
            raise ValueError("Missing bearer")
        claims = verify_token(credentials.credentials)
    except (jwt.PyJWTError, ValueError, KeyError, TypeError):
        raise HTTPException(
            401, "Invalid or expired access token", headers={"WWW-Authenticate": "Bearer"}
        ) from None
    row = db.scalar(select(Profile).where(Profile.owner_id == claims["sub"]))
    email = claims.get("email") if claims.get("email_verified", True) else None
    if row is None:
        row = Profile(
            id=claims["sub"],
            owner_id=claims["sub"],
            payload=dict(
                ProfileInput().model_dump(mode="json"),
                notification_email=email,
            ),
        )
        db.add(row)
        try:
            db.commit()
        except IntegrityError:
            db.rollback()
            row = db.scalar(select(Profile).where(Profile.owner_id == claims["sub"]))
            if row is None:
                raise HTTPException(503, "Identity synchronization unavailable") from None
    elif row.payload.get("notification_email") != email:
        row.payload = dict(row.payload, notification_email=email)
        db.commit()
    return claims["sub"]
