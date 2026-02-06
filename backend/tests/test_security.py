"""Tests for JWT and password hashing."""
from app.core.security import (
    get_password_hash,
    verify_password,
    create_access_token,
    create_refresh_token,
    decode_token,
    hash_refresh_token,
)


def test_password_hash_and_verify():
    pwd = "securepassword123"
    hashed = get_password_hash(pwd)
    assert hashed != pwd
    assert verify_password(pwd, hashed) is True
    assert verify_password("wrong", hashed) is False


def test_create_and_decode_access_token():
    token = create_access_token("user-123")
    assert isinstance(token, str)
    payload = decode_token(token)
    assert payload is not None
    assert payload["sub"] == "user-123"
    assert payload.get("type") == "access"


def test_create_and_decode_refresh_token():
    token = create_refresh_token("user-123")
    payload = decode_token(token)
    assert payload is not None
    assert payload["sub"] == "user-123"
    assert payload.get("type") == "refresh"


def test_decode_invalid_token_returns_none():
    assert decode_token("invalid") is None
    assert decode_token("") is None


def test_hash_refresh_token():
    token = create_refresh_token("user-123")
    h = hash_refresh_token(token)
    assert isinstance(h, str)
    assert len(h) == 64
    assert h == hash_refresh_token(token)
