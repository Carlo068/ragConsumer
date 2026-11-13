import pytest

from app.ids import is_valid_id


@pytest.mark.parametrize("value", [
    "3f2b8c1e-9a4d-4b7e-8c21-5d6e7f8a9b0c",
    "3F2B8C1E-9A4D-4B7E-8C21-5D6E7F8A9B0C",
    "3f2b8c1e9a4d4b7e8c215d6e7f8a9b0c",
])
def test_uuids_are_valid(value):
    assert is_valid_id(value)


@pytest.mark.parametrize("value", ["", "abc", "123", "3f2b8c1e-9a4d", "'; DROP TABLE x; --", "../../etc/passwd", "x" * 500, None, 42])
def test_everything_else_is_not(value):
    assert not is_valid_id(value)
