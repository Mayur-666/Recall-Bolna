import uuid

import pytest

from app.core.config import get_settings

TRANSCRIPT = "Priya: We should use WebSockets for live updates.\nMayur: Agreed, let's go with that."


def _form(**overrides):
    data = {
        "title": "API sync",
        "conversation_date": "2026-10-20",
        "participants": "Priya, Mayur",
        "text": TRANSCRIPT + f"\n# {uuid.uuid4().hex}",  # unique per test unless overridden
    }
    data.update(overrides)
    return data


@pytest.fixture
async def authed(client, make_user, login):
    user, pw = await make_user()
    await login(user, pw)
    return user


async def test_create_paste_queues_job(client, authed):
    resp = await client.post("/api/v1/conversations", data=_form())
    assert resp.status_code == 201, resp.text
    body = resp.json()
    assert body["status"] == "queued"
    assert body["participants"] == ["Priya", "Mayur"]
    assert body["source_type"] == "paste"

    listed = await client.get("/api/v1/conversations")
    assert any(c["id"] == body["id"] for c in listed.json())


@pytest.mark.parametrize(
    ("name", "content"),
    [
        ("notes.txt", "Priya: plain text file.\n"),
        ("call.vtt", "WEBVTT\n\n00:00:01.000 --> 00:00:03.000\n<v Priya>Hello there.\n"),
        ("call.srt", "1\n00:00:01,000 --> 00:00:03,000\nPriya: Hello there.\n"),
    ],
)
async def test_upload_txt_vtt_srt_accepted(client, authed, name, content):
    data = _form()
    data.pop("text")
    content += f"\n{uuid.uuid4().hex}"
    resp = await client.post(
        "/api/v1/conversations", data=data, files={"file": (name, content.encode(), "text/plain")}
    )
    assert resp.status_code == 201, resp.text
    assert resp.json()["source_type"] == "upload"
    assert resp.json()["original_filename"] == name


async def test_upload_too_large_413(client, authed):
    data = _form()
    data.pop("text")
    big = b"a" * (get_settings().MAX_UPLOAD_BYTES + 1)
    resp = await client.post(
        "/api/v1/conversations", data=data, files={"file": ("big.txt", big, "text/plain")}
    )
    assert resp.status_code == 413


async def test_text_too_long_422(client, authed):
    resp = await client.post(
        "/api/v1/conversations", data=_form(text="x" * (get_settings().MAX_TRANSCRIPT_CHARS + 1))
    )
    assert resp.status_code == 422


async def test_non_utf8_upload_422(client, authed):
    data = _form()
    data.pop("text")
    resp = await client.post(
        "/api/v1/conversations", data=data, files={"file": ("bad.txt", b"\xff\xfe\xfa\x00bad", "text/plain")}
    )
    assert resp.status_code == 422


async def test_unsupported_extension_422(client, authed):
    data = _form()
    data.pop("text")
    resp = await client.post(
        "/api/v1/conversations", data=data, files={"file": ("evil.exe", b"MZ", "application/octet-stream")}
    )
    assert resp.status_code == 422


async def test_empty_text_422(client, authed):
    resp = await client.post("/api/v1/conversations", data=_form(text="   \n "))
    assert resp.status_code == 422


async def test_duplicate_whitespace_variant_409_returns_existing_id(client, authed):
    base = f"Priya: Ship on Friday.\nMayur: OK.\n{uuid.uuid4().hex}"
    first = await client.post("/api/v1/conversations", data=_form(text=base))
    assert first.status_code == 201
    variant = base.replace("\n", "  \r\n") + "\n\n\n"
    dup = await client.post("/api/v1/conversations", data=_form(text=variant))
    assert dup.status_code == 409
    assert dup.json()["error"]["details"]["existing_id"] == first.json()["id"]


async def test_other_users_conversation_404(client, make_user, login):
    a, pw_a = await make_user()
    await login(a, pw_a)
    conv = (await client.post("/api/v1/conversations", data=_form())).json()

    b, pw_b = await make_user()
    await login(b, pw_b)
    assert (await client.get(f"/api/v1/conversations/{conv['id']}")).status_code == 404
    assert (await client.post(f"/api/v1/conversations/{conv['id']}/retry")).status_code == 404
    assert (await client.delete(f"/api/v1/conversations/{conv['id']}")).status_code == 404
    assert all(c["id"] != conv["id"] for c in (await client.get("/api/v1/conversations")).json())


async def test_retry_only_from_failed_409(client, authed):
    conv = (await client.post("/api/v1/conversations", data=_form())).json()
    resp = await client.post(f"/api/v1/conversations/{conv['id']}/retry")
    assert resp.status_code == 409


async def test_missing_conversation_date_422(client, authed):
    data = _form()
    data.pop("conversation_date")
    assert (await client.post("/api/v1/conversations", data=data)).status_code == 422


async def test_self_speaker_must_be_a_participant_422(client, authed):
    resp = await client.post("/api/v1/conversations", data=_form(self_speaker="Someone Else"))
    assert resp.status_code == 422


async def test_detail_and_delete(client, authed):
    conv = (await client.post("/api/v1/conversations", data=_form(self_speaker="Mayur"))).json()
    detail = await client.get(f"/api/v1/conversations/{conv['id']}")
    assert detail.status_code == 200
    body = detail.json()
    assert body["transcript_text"].startswith("Priya:")
    assert body["self_speaker"] == "Mayur"
    assert body["segments"] == [] and body["memory_items"] == []
    assert (await client.delete(f"/api/v1/conversations/{conv['id']}")).status_code == 204
    assert (await client.get(f"/api/v1/conversations/{conv['id']}")).status_code == 404


async def test_requires_auth_401(client):
    assert (await client.get("/api/v1/conversations")).status_code == 401
