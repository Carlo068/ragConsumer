def test_login_success(client, make_user):
    make_user(email="alice@example.com", password="password123")

    response = client.post(
        "/auth/login", json={"email": "alice@example.com", "password": "password123"}
    )

    assert response.status_code == 200
    assert response.json()["email"] == "alice@example.com"


def test_login_wrong_password(client, make_user):
    make_user(email="alice@example.com", password="password123")

    response = client.post(
        "/auth/login", json={"email": "alice@example.com", "password": "wrong"}
    )

    assert response.status_code == 401


def test_login_unknown_email(client):
    response = client.post(
        "/auth/login", json={"email": "nobody@example.com", "password": "whatever"}
    )

    assert response.status_code == 401


def test_me_requires_authentication(client):
    response = client.get("/auth/me")

    assert response.status_code == 401


def test_me_after_login(logged_in_client):
    client, user = logged_in_client

    response = client.get("/auth/me")

    assert response.status_code == 200
    assert response.json()["email"] == user.email


def test_logout_clears_session(logged_in_client):
    client, _ = logged_in_client

    client.post("/auth/logout")
    response = client.get("/auth/me")

    assert response.status_code == 401
