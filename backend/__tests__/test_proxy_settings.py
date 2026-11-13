from app.config import parse_origins


def test_origins_are_split_and_cleaned():
    assert parse_origins("http://a.test, http://b.test ,,") == ["http://a.test", "http://b.test"]


def test_an_empty_setting_means_no_cross_origin_access():
    # Production serves the app and the API from one address, so no origin is allowed.
    assert parse_origins("") == []
    assert parse_origins("  ,  ") == []


def test_the_development_default_allows_the_local_web_app():
    from app.config import Settings

    assert "http://localhost:5173" in parse_origins(Settings(DATABASE_URL="x", SESSION_SECRET="y").CORS_ORIGINS)
