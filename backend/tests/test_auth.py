import logging

import jwt


async def test_login_sets_httponly_cookie(client, make_user):
    user, pw = await make_user()
    resp = await client.post("/api/v1/auth/login", json={"email": user.email, "password": pw})
    assert resp.status_code == 200
    assert resp.json()["email"] == user.email
    cookie = resp.headers["set-cookie"].lower()
    assert "recall_session_jwt=" in cookie
    assert "httponly" in cookie
    assert "samesite=lax" in cookie


async def test_login_wrong_password_401(client, make_user):
    user, _ = await make_user()
    bad_pw = await client.post("/api/v1/auth/login", json={"email": user.email, "password": "nope"})
    no_user = await client.post("/api/v1/auth/login", json={"email": "ghost@test.local", "password": "x"})
    assert bad_pw.status_code == no_user.status_code == 401
    # Same message either way: no user enumeration.
    assert bad_pw.json() == no_user.json()


async def test_me_requires_cookie_401(client):
    resp = await client.get("/api/v1/auth/me")
    assert resp.status_code == 401
    assert resp.json()["error"]["code"] == "unauthorized"


async def test_me_returns_user(client, make_user, login):
    user, pw = await make_user(name="Asha")
    await login(user, pw)
    resp = await client.get("/api/v1/auth/me")
    assert resp.status_code == 200
    assert resp.json()["display_name"] == "Asha"


async def test_tampered_jwt_401(client, make_user):
    user, _ = await make_user()
    forged = jwt.encode({"sub": str(user.id)}, "wrong-secret", algorithm="HS256")
    client.cookies.set("recall_session_jwt", forged)
    resp = await client.get("/api/v1/auth/me")
    assert resp.status_code == 401


async def test_logout_clears_cookie(client, make_user, login):
    user, pw = await make_user()
    await login(user, pw)
    resp = await client.post("/api/v1/auth/logout")
    assert resp.status_code == 204
    assert (await client.get("/api/v1/auth/me")).status_code == 401


def test_logging_redacts_secrets(caplog):
    from app.core.logging import RedactingFilter

    logger = logging.getLogger("recall.test")
    logger.addFilter(RedactingFilter())
    with caplog.at_level(logging.INFO, logger="recall.test"):
        logger.info(
            "payload %s",
            {
                "password": "SECRET-PW-1",
                "token": "SECRET-TOK-2",
                "api_key": "SECRET-KEY-3",
                "Authorization": "Bearer SECRET-BEARER-4",
                "ok": "visible",
            },
        )
    text = caplog.text
    for secret in ("SECRET-PW-1", "SECRET-TOK-2", "SECRET-KEY-3", "SECRET-BEARER-4"):
        assert secret not in text
    assert "visible" in text
    assert "***" in text
