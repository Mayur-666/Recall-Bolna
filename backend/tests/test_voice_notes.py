import asyncio

from sqlalchemy import select

from app.db.session import get_sessionmaker
from app.models import Conversation, IngestionJob, ToolCall
from app.services.call_sessions import CallSessionService
from app.services.events import get_event_bus
from app.services.transcript_parser import parse_transcript
from app.services.voice_notes import note_title, speaker_label

AUTH = {"Authorization": "Bearer test-tool-token"}
SAVE = "/api/v1/bolna/tools/save_memory"
NOTE = "We moved the investor demo to Friday, November 6."


async def new_token(user):
    async with get_sessionmaker()() as s:
        cs, raw = await CallSessionService(s).create(user.id, "web")
        await s.commit()
    return cs, raw


async def user_conversations(user):
    async with get_sessionmaker()() as s:
        return list((await s.scalars(select(Conversation).where(Conversation.user_id == user.id))).all())


def test_speaker_label_is_parseable_and_safe():
    assert speaker_label("Mayur Sonare") == "Mayur Sonare"
    assert speaker_label("dr. ada   lovelace byron king") == "Dr. Ada Lovelace"
    assert speaker_label("👋 ") == "Me"
    assert speaker_label("") == "Me"
    for name in ("Mayur Sonare", "o'neil", "Jean-Luc Picard", "x"):
        label = speaker_label(name)
        segs = parse_transcript(f"{label}: {NOTE}", None, [label])
        assert segs[0].speaker == label


def test_note_title_is_short():
    assert note_title("Remember the launch") == "Voice note: Remember the launch"
    assert note_title(NOTE).endswith("…")


async def test_save_memory_queues_a_voice_note_for_the_callers_account(client, make_user):
    user, _ = await make_user(name="Mayur Sonare")
    other, _ = await make_user(name="Someone Else")
    cs, token = await new_token(user)

    resp = await client.post(SAVE, json={"recall_session": token, "note": NOTE}, headers=AUTH)
    assert resp.status_code == 200
    assert resp.json()["status"] == "saved"
    assert "remember" in resp.json()["guidance"].lower()

    [conv] = await user_conversations(user)
    assert conv.source_type == "voice"
    assert conv.transcript_text == f"Mayur Sonare: {NOTE}"
    assert conv.participants == ["Mayur Sonare"] and conv.self_speaker == "Mayur Sonare"
    assert conv.status == "queued"
    assert await user_conversations(other) == []
    async with get_sessionmaker()() as s:
        jobs = (await s.scalars(select(IngestionJob).where(IngestionJob.conversation_id == conv.id))).all()
        call = (await s.scalars(select(ToolCall).where(ToolCall.call_session_id == cs.id))).one()
    assert len(jobs) == 1
    assert call.tool_name == "save_memory" and call.result_status == "saved"


async def test_same_note_twice_is_already_saved_not_duplicated(client, make_user):
    user, _ = await make_user()
    _, token = await new_token(user)
    first = await client.post(SAVE, json={"recall_session": token, "note": NOTE}, headers=AUTH)
    again = await client.post(SAVE, json={"recall_session": token, "note": f"  {NOTE} "}, headers=AUTH)
    assert first.json()["status"] == "saved"
    assert again.json()["status"] == "already_saved"
    assert len(await user_conversations(user)) == 1


async def test_save_memory_requires_tool_auth_and_a_live_session(client, make_user):
    user, _ = await make_user()
    _, token = await new_token(user)
    assert (await client.post(SAVE, json={"recall_session": token, "note": NOTE})).status_code == 401
    assert (await client.post(SAVE, json={"recall_session": "nope", "note": NOTE}, headers=AUTH)).status_code == 401
    # The account always comes from the session; a model-invented user_id is rejected outright.
    bad = await client.post(SAVE, json={"recall_session": token, "note": NOTE, "user_id": "x"}, headers=AUTH)
    assert bad.status_code == 422
    empty = await client.post(SAVE, json={"recall_session": token, "note": "%(note)s"}, headers=AUTH)
    assert empty.status_code == 422
    assert await user_conversations(user) == []


async def test_save_memory_publishes_live_events(client, make_user):
    user, _ = await make_user()
    cs, token = await new_token(user)
    bus = get_event_bus()
    received = []

    async def listen():
        async for event in bus.subscribe(cs.id):
            received.append(event)
            if event["type"] in ("tool_call_completed", "tool_call_failed"):
                return

    task = asyncio.create_task(listen())
    await asyncio.sleep(0.05)
    await client.post(SAVE, json={"recall_session": token, "note": NOTE}, headers=AUTH)
    await asyncio.wait_for(task, timeout=2)
    assert [e["type"] for e in received] == ["tool_call_started", "tool_call_completed"]
    assert received[0]["tool"] == received[1]["tool"] == "save_memory"
    assert received[1]["status"] == "saved" and received[1]["note"] == NOTE and received[1]["conversation_id"]
