import uuid

import pytest

from app.auth.security import (
    TokenType,
    create_access_token,
    create_refresh_token,
    decode_token,
    generate_api_key,
    hash_api_key,
    hash_password,
    verify_password,
)


def test_password_hash_roundtrip():
    hashed = hash_password("correct-horse-battery-staple")
    assert verify_password("correct-horse-battery-staple", hashed)
    assert not verify_password("wrong-password", hashed)


def test_password_longer_than_72_bytes_does_not_crash():
    long_password = "x" * 200
    hashed = hash_password(long_password)
    assert verify_password(long_password, hashed)


def test_access_and_refresh_tokens_round_trip():
    user_id = uuid.uuid4()
    access = create_access_token(user_id)
    refresh = create_refresh_token(user_id)

    assert decode_token(access, TokenType.ACCESS) == user_id
    assert decode_token(refresh, TokenType.REFRESH) == user_id


def test_access_token_rejected_as_refresh_token():
    user_id = uuid.uuid4()
    access = create_access_token(user_id)
    with pytest.raises(ValueError):
        decode_token(access, TokenType.REFRESH)


def test_garbage_token_raises_value_error():
    with pytest.raises(ValueError):
        decode_token("not-a-real-token", TokenType.ACCESS)


def test_api_key_generation_and_hashing():
    full_key, prefix, key_hash = generate_api_key()
    assert full_key.startswith("djs_")
    assert full_key[4:12] == prefix
    assert hash_api_key(full_key) == key_hash
