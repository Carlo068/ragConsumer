import pytest

from app.webhook_auth import webhook_authorized

TOKEN = "s3cret-token-value"


@pytest.mark.parametrize("header", [TOKEN, f"Bearer {TOKEN}", f"bearer {TOKEN}", f"  Bearer   {TOKEN}  "])
def test_the_right_token_is_accepted_with_or_without_the_bearer_prefix(header):
    assert webhook_authorized(header, TOKEN)


@pytest.mark.parametrize("header", [None, "", "Bearer ", "Bearer wrong", "wrong", TOKEN + "x", TOKEN[:-1], f"Basic {TOKEN}"])
def test_anything_else_is_refused(header):
    assert not webhook_authorized(header, TOKEN)


def test_with_no_token_configured_everything_is_refused():
    assert not webhook_authorized("anything", "")
    assert not webhook_authorized("", "")
    assert not webhook_authorized(None, "")
