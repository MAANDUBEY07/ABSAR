from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import patch
from uuid import uuid4
import jwt
import httpx
import pytest
from cryptography.hazmat.primitives.asymmetric import ec
from app.utils.auth import verify_token
from app.config import settings


@pytest.mark.parametrize("status", [200, 401, 403, 503])
def test_legacy_supabase_tokens_require_remote_verification(signing, monkeypatch, status):
    _, claims = signing
    monkeypatch.setattr(settings, "auth_provider", "supabase")
    monkeypatch.setattr(settings, "supabase_url", "https://project.supabase.co")
    monkeypatch.setattr(settings, "supabase_anon_key", "public-key")
    token = jwt.encode(claims, "test-signing-secret-at-least-32-characters", algorithm="HS256")
    with patch(
        "app.utils.auth.httpx.get", return_value=httpx.Response(status, json={"id": claims["sub"]})
    ) as remote:
        if status == 200:
            assert verify_token(token)["sub"] == claims["sub"]
        else:
            from fastapi import HTTPException

            with pytest.raises((ValueError, HTTPException)):
                verify_token(token)
        assert remote.call_args.args[0] == "https://project.supabase.co/auth/v1/user"
        assert remote.call_args.kwargs["follow_redirects"] is False


@pytest.mark.parametrize(
    "change",
    [{"exp": 1}, {"iss": "https://attacker.example/auth/v1"}, {"aud": "anon"}, {"role": "anon"}],
)
def test_legacy_invalid_claims_never_reach_remote(signing, monkeypatch, change):
    _, claims = signing
    monkeypatch.setattr(settings, "auth_provider", "supabase")
    monkeypatch.setattr(settings, "supabase_url", "https://project.supabase.co")
    monkeypatch.setattr(settings, "supabase_anon_key", "public-key")
    token = jwt.encode(
        dict(claims, **change), "test-signing-secret-at-least-32-characters", algorithm="HS256"
    )
    with patch("app.utils.auth.httpx.get") as remote:
        with pytest.raises((ValueError, jwt.PyJWTError)):
            verify_token(token)
        remote.assert_not_called()


@pytest.fixture
def signing():
    instant = datetime.now(timezone.utc)
    claims = dict(
        sub=str(uuid4()),
        iss="https://project.supabase.co/auth/v1",
        aud="authenticated",
        exp=instant + timedelta(minutes=10),
        role="authenticated",
        email="signed@example.test",
    )
    return ec.generate_private_key(ec.SECP256R1()), claims


def test_supabase_valid_signature_and_trusted_endpoint(signing, monkeypatch):
    private, claims = signing
    monkeypatch.setattr(settings, "auth_provider", "supabase")
    monkeypatch.setattr(settings, "supabase_url", "https://project.supabase.co")
    token = jwt.encode(claims, private, algorithm="ES256", headers={"kid": "rotation-key"})
    fake = SimpleNamespace(
        get_signing_key_from_jwt=lambda token: SimpleNamespace(key=private.public_key())
    )
    with patch("app.utils.auth.jwks_client", return_value=fake) as client:
        assert verify_token(token)["sub"] == claims["sub"]
        client.assert_called_once_with("https://project.supabase.co/auth/v1/.well-known/jwks.json")


@pytest.mark.parametrize(
    "change",
    [
        dict(iss="https://attacker.supabase.co/auth/v1"),
        dict(aud="other"),
        dict(exp=1),
        dict(role="anon"),
        dict(sub="not-a-uuid"),
    ],
)
def test_supabase_invalid_claims(signing, monkeypatch, change):
    private, claims = signing
    monkeypatch.setattr(settings, "auth_provider", "supabase")
    monkeypatch.setattr(settings, "supabase_url", "https://project.supabase.co")
    token = jwt.encode(dict(claims, **change), private, algorithm="ES256", headers={"kid": "key"})
    fake = SimpleNamespace(
        get_signing_key_from_jwt=lambda token: SimpleNamespace(key=private.public_key())
    )
    with (
        patch("app.utils.auth.jwks_client", return_value=fake),
        pytest.raises((ValueError, jwt.PyJWTError)),
    ):
        verify_token(token)


def test_supabase_rejects_signature_and_algorithm(signing, monkeypatch):
    private, claims = signing
    monkeypatch.setattr(settings, "auth_provider", "supabase")
    monkeypatch.setattr(settings, "supabase_url", "https://project.supabase.co")
    unrelated = ec.generate_private_key(ec.SECP256R1())
    fake = SimpleNamespace(
        get_signing_key_from_jwt=lambda token: SimpleNamespace(key=unrelated.public_key())
    )
    token = jwt.encode(claims, private, algorithm="ES256", headers={"kid": "key"})
    with (
        patch("app.utils.auth.jwks_client", return_value=fake),
        pytest.raises(jwt.InvalidSignatureError),
    ):
        verify_token(token)
    token = jwt.encode(claims, "attacker-secret-long-enough-for-HS256", algorithm="HS256")
    with pytest.raises(ValueError):
        verify_token(token)


def test_cognito_is_excluded_from_active_authentication(monkeypatch):
    from app.config import Settings
    from pydantic import ValidationError

    with pytest.raises(ValidationError):
        Settings(auth_provider="cognito")
    monkeypatch.setattr(settings, "auth_provider", "cognito")
    with pytest.raises(ValueError, match="Unsupported authentication provider"):
        verify_token("untrusted")


def test_search_accepts_issuer_verified_legacy_session(client, signing, monkeypatch):
    _, claims = signing
    monkeypatch.setattr(settings, "auth_provider", "supabase")
    monkeypatch.setattr(settings, "supabase_url", "https://project.supabase.co")
    monkeypatch.setattr(settings, "supabase_anon_key", "public-key")
    monkeypatch.setattr(settings, "environment", "test")
    monkeypatch.setattr(
        "app.services.india_sources.listings",
        lambda category=None: [
            {
                "id": "sales",
                "title": "Sales Consultant",
                "category": "job",
                "location": "Delhi, India",
            }
        ],
    )
    token = jwt.encode(claims, "test-signing-secret-at-least-32-characters", algorithm="HS256")
    with patch(
        "app.utils.auth.httpx.get", return_value=httpx.Response(200, json={"id": claims["sub"]})
    ):
        response = client.get(
            "/api/v1/opportunities",
            params={"country": "India", "search": "sales consultant"},
            headers={"Authorization": "Bearer " + token},
        )
    assert response.status_code == 200, response.text
    assert response.json()["data"][0]["title"] == "Sales Consultant"


def test_legacy_remote_identity_mismatch_is_rejected(signing, monkeypatch):
    _, claims = signing
    monkeypatch.setattr(settings, "auth_provider", "supabase")
    monkeypatch.setattr(settings, "supabase_url", "https://project.supabase.co")
    monkeypatch.setattr(settings, "supabase_anon_key", "public-key")
    token = jwt.encode(claims, "test-signing-secret-at-least-32-characters", algorithm="HS256")
    with patch(
        "app.utils.auth.httpx.get", return_value=httpx.Response(200, json={"id": str(uuid4())})
    ):
        with pytest.raises(ValueError, match="identity mismatch"):
            verify_token(token)
