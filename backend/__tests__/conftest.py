from typing import Iterator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event, text
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.auth import hash_password
from app.db import get_db
from app.main import app
from app.models import Base, User

# Fully isolated in-memory SQLite -- never touches the real dev/prod
# Postgres database, and needs nothing running (no Docker Compose, no
# network) for the suite to work. StaticPool keeps every connection in the
# process sharing the same in-memory database (SQLite's default pooling
# would otherwise hand out a fresh, empty :memory: db per connection).
test_engine = create_engine(
    "sqlite:///:memory:",
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)


@event.listens_for(test_engine, "connect")
def _enable_sqlite_foreign_keys(dbapi_connection, _):
    # Off by default in SQLite -- without this, ondelete="CASCADE" /
    # "SET NULL" / "RESTRICT" on the models are silently not enforced.
    cursor = dbapi_connection.cursor()
    cursor.execute("PRAGMA foreign_keys=ON")
    cursor.close()


TestSessionLocal = sessionmaker(bind=test_engine, autoflush=False, autocommit=False)


def _override_get_db() -> Iterator[Session]:
    session = TestSessionLocal()
    try:
        yield session
    finally:
        session.close()


app.dependency_overrides[get_db] = _override_get_db


@pytest.fixture(autouse=True)
def clean_db() -> Iterator[None]:
    """Every test starts from a fresh schema -- cheap enough to drop and
    recreate for an in-memory database, no need for truncate/rollback
    tricks."""
    Base.metadata.create_all(bind=test_engine)
    with test_engine.connect() as conn:
        conn.execute(
            text("INSERT INTO mcp_active_collection (id, collection_id) VALUES (1, NULL)")
        )
        conn.commit()
    yield
    Base.metadata.drop_all(bind=test_engine)


@pytest.fixture(autouse=True)
def no_real_minio_at_startup(monkeypatch):
    # The app's startup event calls ensure_bucket(), which otherwise makes a
    # real network call to MinIO -- nothing in this suite should depend on
    # MinIO (or any other external service) actually running.
    monkeypatch.setattr("app.main.ensure_bucket", lambda: None)


@pytest.fixture
def db() -> Iterator[Session]:
    session = TestSessionLocal()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture
def client() -> Iterator[TestClient]:
    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture
def make_user(db: Session):
    def _make_user(email: str = "alice@example.com", password: str = "password123") -> User:
        user = User(email=email, password_hash=hash_password(password))
        db.add(user)
        db.commit()
        db.refresh(user)
        return user

    return _make_user


@pytest.fixture
def logged_in_client(client: TestClient, make_user):
    user = make_user()
    response = client.post(
        "/auth/login", json={"email": user.email, "password": "password123"}
    )
    assert response.status_code == 200
    return client, user
