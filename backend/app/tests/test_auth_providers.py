from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import patch
from uuid import uuid4
import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric import ec, rsa
from app.utils.auth import verify_token
from app.config import settings


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


def test_cognito_pool_client_and_token_type(monkeypatch):
    monkeypatch.setattr(settings, "auth_provider", "cognito")
    monkeypatch.setattr(settings, "cognito_region", "ap-south-1")
    monkeypatch.setattr(settings, "cognito_user_pool_id", "ap-south-1_example")
    monkeypatch.setattr(settings, "cognito_client_id", "configured-client")
    private = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    claims = dict(
        sub=str(uuid4()),
        iss="https://cognito-idp.ap-south-1.amazonaws.com/ap-south-1_example",
        aud="configured-client",
        exp=datetime.now(timezone.utc) + timedelta(minutes=5),
        token_use="id",
    )
    fake = SimpleNamespace(
        get_signing_key_from_jwt=lambda token: SimpleNamespace(key=private.public_key())
    )
    with patch("app.utils.auth.jwks_client", return_value=fake):
        assert (
            verify_token(jwt.encode(claims, private, algorithm="RS256", headers={"kid": "key"}))[
                "token_use"
            ]
            == "id"
        )
        for change in (
            dict(aud="wrong-client"),
            dict(token_use="access"),
            dict(iss="https://other-pool.example"),
        ):
            token = jwt.encode(
                dict(claims, **change), private, algorithm="RS256", headers={"kid": "key"}
            )
            with pytest.raises((ValueError, jwt.PyJWTError)):
                verify_token(token)
