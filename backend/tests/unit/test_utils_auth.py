"""Unit tests for password hashing and JWT helpers (no DB, no network)."""

import jwt
import pytest
from freezegun import freeze_time

from app.config import settings
from app.utils.auth import (
    create_token,
    decode_token,
    hash_password,
    verify_password,
)

pytestmark = pytest.mark.unit


class TestPasswordHashing:
    def test_hash_is_not_plaintext_and_verifies(self):
        hashed = hash_password("CorrectHorse1!")
        assert hashed != "CorrectHorse1!"
        assert verify_password("CorrectHorse1!", hashed) is True

    def test_wrong_password_does_not_verify(self):
        hashed = hash_password("CorrectHorse1!")
        assert verify_password("wrong-password", hashed) is False

    def test_same_password_hashes_differ_due_to_salt(self):
        assert hash_password("samePassw0rd!") != hash_password("samePassw0rd!")


class TestTokens:
    def test_round_trip_contains_claims(self):
        token = create_token("user-123", "alice@example.com", "admin")
        payload = decode_token(token)
        assert payload["sub"] == "user-123"
        assert payload["email"] == "alice@example.com"
        assert payload["role"] == "admin"
        assert "exp" in payload

    def test_expired_token_raises(self):
        # Mint a token 9 hours in the past; tokens live 8 hours, so it is expired now.
        with freeze_time("2026-01-01 00:00:00"):
            token = create_token("user-123", "alice@example.com", "admin")
        with freeze_time("2026-01-01 09:00:01"):
            with pytest.raises(jwt.ExpiredSignatureError):
                decode_token(token)

    def test_tampered_token_raises(self):
        token = create_token("user-123", "alice@example.com", "admin")
        with pytest.raises(jwt.InvalidTokenError):
            decode_token(token + "tamper")

    def test_token_signed_with_wrong_secret_raises(self):
        forged = jwt.encode({"sub": "x"}, "not-the-real-secret-key-definitely-wrong", algorithm="HS256")
        assert settings.SECRET_KEY != "not-the-real-secret-key-definitely-wrong"
        with pytest.raises(jwt.InvalidTokenError):
            decode_token(forged)
