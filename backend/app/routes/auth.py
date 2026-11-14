from fastapi import APIRouter
from app.routes.common import DB, Owner, ok
from app.config import settings
from app.models.profile import Profile
from app.repositories.relational import owned

router = APIRouter()


@router.get("/auth/config")
def config():
    return ok(
        dict(
            provider=settings.auth_provider,
            supabase_url=settings.supabase_url or None,
            supabase_anon_key=settings.supabase_anon_key or None,
            demo_mode=settings.demo_mode,
        )
    )


@router.get("/auth/me")
def me(owner: Owner, db: DB):
    profile = owned(db, Profile, owner, owner)
    return ok(dict(id=owner, email=profile.payload.get("notification_email")))


@router.post("/auth/logout")
def logout(owner: Owner):
    return ok(
        dict(
            local_session_cleared=True,
            access_token_revoked=False,
            instruction="Clear client tokens and sign out through your auth provider. Issued access JWTs remain valid until expiry.",
        )
    )
