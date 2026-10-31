import json
import logging

import httpx
import pytest
import respx

from app.bolna.agent_config import build_task_config, build_tools, merge_for_put
from app.core.config import get_settings
from app.integrations.bolna_client import BolnaClient, BolnaError

BASE = "https://api.bolna.ai"


@pytest.fixture(autouse=True)
def bolna_env(monkeypatch):
    s = get_settings()
    monkeypatch.setattr(s, "BOLNA_API_KEY", "bn-test-key")
    monkeypatch.setattr(s, "BOLNA_AGENT_ID", "agent-123")
    monkeypatch.setattr(s, "BOLNA_WEB_CALL_SESSION_PATH", "/web-call/session")


@respx.mock
async def test_mint_posts_agent_id_and_user_data_with_bearer():
    route = respx.post(f"{BASE}/web-call/session").mock(
        return_value=httpx.Response(200, json={"token": "abc"})
    )
    out = await BolnaClient().mint_web_session("agent-123", {"recall_session": "t", "user_name": "Mayur"})
    assert out == {"token": "abc"}
    req = route.calls[0].request
    assert req.headers["authorization"] == "Bearer bn-test-key"
    assert json.loads(req.content) == {
        "agent_id": "agent-123",
        "user_data": {"recall_session": "t", "user_name": "Mayur"},
    }


@respx.mock
async def test_session_path_configurable(monkeypatch):
    monkeypatch.setattr(get_settings(), "BOLNA_WEB_CALL_SESSION_PATH", "/web-call/freeswitch-session")
    route = respx.post(f"{BASE}/web-call/freeswitch-session").mock(return_value=httpx.Response(200, json={}))
    await BolnaClient().mint_web_session("agent-123", {})
    assert route.called


@respx.mock
async def test_bolna_error_does_not_leak_key(caplog):
    respx.post(f"{BASE}/call").mock(return_value=httpx.Response(403, json={"message": "not allowed"}))
    with caplog.at_level(logging.DEBUG), pytest.raises(BolnaError) as exc:
        await BolnaClient().make_call("agent-123", "+919876543210", {"recall_session": "secret-tok"})
    assert exc.value.status == 403
    assert "not allowed" in exc.value.body_excerpt
    assert "bn-test-key" not in str(exc.value) and "bn-test-key" not in caplog.text
    assert "secret-tok" not in str(exc.value)


@respx.mock
async def test_make_call_returns_execution_id():
    route = respx.post(f"{BASE}/call").mock(
        return_value=httpx.Response(200, json={"message": "done", "status": "queued", "execution_id": "ex-1"})
    )
    assert await BolnaClient().make_call("agent-123", "+919876543210", {"a": 1}) == "ex-1"
    sent = json.loads(route.calls[0].request.content)
    assert sent == {"agent_id": "agent-123", "recipient_phone_number": "+919876543210", "user_data": {"a": 1}}


@respx.mock
async def test_get_execution_and_patch_agent():
    respx.get(f"{BASE}/executions/ex-1").mock(
        return_value=httpx.Response(200, json={"id": "ex-1", "status": "completed"})
    )
    patch = respx.patch(f"{BASE}/v2/agent/agent-123").mock(
        return_value=httpx.Response(200, json={"state": "updated"})
    )
    c = BolnaClient()
    assert (await c.get_execution("ex-1"))["status"] == "completed"
    await c.patch_agent("agent-123", {"agent_prompts": {"task_1": {"system_prompt": "x"}}})
    assert json.loads(patch.calls[0].request.content)["agent_prompts"]["task_1"]["system_prompt"] == "x"


async def test_missing_api_key_raises(monkeypatch):
    monkeypatch.setattr(get_settings(), "BOLNA_API_KEY", "")
    with pytest.raises(BolnaError) as exc:
        await BolnaClient().get_agent("agent-123")
    assert "BOLNA_API_KEY" in str(exc.value)


def test_build_tools_shape_matches_documented_schema():
    cfg = build_tools("https://abc.trycloudflare.com", "tool-secret")
    tools = {t["name"]: t for t in cfg["tools"]}
    assert set(tools) == {"search_memories", "get_source_context", "save_memory"}
    for name, t in tools.items():
        assert t["key"] == "custom_task"
        assert t["pre_call_message"]
        v = t["value"]
        assert v["method"] == "POST"
        assert v["url"] == f"https://abc.trycloudflare.com/api/v1/bolna/tools/{name}"
        assert v["api_token"] == "Bearer tool-secret"
        assert v["headers"] == {"Content-Type": "application/json"}
        props = t["parameters"]["properties"]
        assert set(v["param"]) == set(props)  # byte-identical names
        assert all(v["param"][p] == f"%({p})s" for p in props)
        assert "recall_session" in props and "execution_id" in props
        assert "user_id" not in props
    assert tools["search_memories"]["parameters"]["required"] == ["question"]
    assert tools["get_source_context"]["parameters"]["required"] == ["ref"]
    assert tools["save_memory"]["parameters"]["required"] == ["note"]
    assert cfg["tools_params"]["search_memories"]["url"].endswith("/search_memories")


def test_build_tools_rejects_non_https_url():
    with pytest.raises(ValueError):
        build_tools("http://localhost:8000", "x")


def test_task_config_interruption_values():
    tc = build_task_config()
    assert tc["number_of_words_for_interruption"] == 2
    assert tc["interruption_backoff_period"] == 150
    assert tc["incremental_delay"] == 300
    assert tc["hangup_after_silence"] == 45
    assert tc["call_terminate"] == 600
    # Saying goodbye ends the call (prompt-based hangup), with an interruptible closing line.
    assert tc["hangup_after_LLMCall"] is True
    assert "goodbye" in tc["call_cancellation_prompt"].lower()
    assert "remember" in tc["call_cancellation_prompt"].lower()  # never hang up on a save request
    assert tc["call_hangup_message"]
    assert tc["interruptible_hangup_message"] is True


def test_merge_for_put_preserves_provider_blocks():
    current = {
        "agent_name": "Recall",
        "agent_welcome_message": "old",
        "agent_type": "other",
        "tasks": [
            {
                "task_type": "conversation",
                "tools_config": {
                    "llm_agent": {"llm_config": {"provider": "openai", "model": "gpt-4.1-mini"}},
                    "synthesizer": {"provider": "sarvam"},
                    "transcriber": {"provider": "deepgram"},
                    "input": {"provider": "plivo"},
                    "output": {"provider": "plivo"},
                    "api_tools": None,
                },
                "task_config": {"hangup_after_silence": 10, "voicemail": False},
            }
        ],
        "agent_prompts": {"task_1": {"system_prompt": "old"}},
    }
    tools = build_tools("https://x.trycloudflare.com", "t")
    payload = merge_for_put(
        current, tools, build_task_config(), "new prompt", "hi {user_name}", "https://x/wh"
    )
    task = payload["agent_config"]["tasks"][0]
    assert task["tools_config"]["synthesizer"] == {"provider": "sarvam"}
    assert task["tools_config"]["llm_agent"]["llm_config"]["model"] == "gpt-4.1-mini"
    assert task["tools_config"]["api_tools"] == tools
    assert task["task_config"]["voicemail"] is False  # untouched keys kept
    assert task["task_config"]["hangup_after_silence"] == 45
    assert payload["agent_prompts"]["task_1"]["system_prompt"] == "new prompt"
    assert payload["agent_config"]["agent_welcome_message"] == "hi {user_name}"
    assert payload["agent_config"]["webhook_url"] == "https://x/wh"


def test_prompt_contains_auto_fill_variables():
    from app.bolna.agent_config import load_prompt, welcome_message

    prompt = load_prompt()
    for var in ("{recall_session}", "{execution_id}", "{user_name}", "{conversation_count}", "{today}"):
        assert var in prompt
    assert "search_memories" in prompt and "get_source_context" in prompt
    assert "{conversation_count}" in welcome_message()
