import jwt
import pytest

from app.qdrant_access import mint_read_token

SECRET = "x" * 32


def decode(token, secret=SECRET):
    return jwt.decode(token, secret, algorithms=["HS256"])


def test_token_grants_read_on_exactly_the_named_collections():
    token = mint_read_token(["matter_a", "matter_b"], SECRET, 60, now=1000)
    assert decode_without_exp(token)["access"] == [
        {"collection": "matter_a", "access": "r"},
        {"collection": "matter_b", "access": "r"},
    ]


def test_token_is_never_more_than_read_only():
    token = mint_read_token(["matter_a"], SECRET, 60, now=1000)
    modes = {entry["access"] for entry in decode_without_exp(token)["access"]}
    assert modes == {"r"}


def test_token_is_short_lived():
    token = mint_read_token(["matter_a"], SECRET, 60, now=1000)
    assert decode_without_exp(token)["exp"] == 1060


def test_token_signed_with_another_secret_does_not_verify():
    token = mint_read_token(["matter_a"], SECRET, 3600)
    with pytest.raises(jwt.InvalidSignatureError):
        decode(token, secret="y" * 32)


def test_no_matters_means_no_access_at_all():
    token = mint_read_token([], SECRET, 60, now=1000)
    assert decode_without_exp(token)["access"] == []


def decode_without_exp(token):
    # The fixed timestamps above are in the past; only the claims matter here.
    return jwt.decode(token, SECRET, algorithms=["HS256"], options={"verify_exp": False})
