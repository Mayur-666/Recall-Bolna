import json

import httpx
import pytest
import respx

from app.bolna import tunnel_sync
from app.bolna.provisioning import configured_base_url
from app.core.config import get_settings

METRICS = "http://tunnel:2000"
AGENT = "https://api.bolna.ai/v2/agent/agent-123"
NEW = "https://fresh-words-here.trycloudflare.com"


@pytest.fixture(autouse=True)
def env(monkeypatch):
    s = get_settings()
    monkeypatch.setattr(s, "BOLNA_API_KEY", "bn-test-key")
    monkeypatch.setattr(s, "BOLNA_AGENT_ID", "agent-123")
    monkeypatch.setattr(s, "TUNNEL_METRICS_URL", METRICS)
    monkeypatch.setattr(tunnel_sync, "_current", None)


def agent(base_url: str) -> dict:
    return {
        "agent_config": {
            "agent_name": "Recall",
            "webhook_url": f"{base_url}/api/v1/bolna/webhook",
            "tasks": [
                {
                    "task_type": "conversation",
                    "tools_config": {
                        "llm_agent": {"llm_config": {"provider": "openai", "model": "gpt-4.1-mini"}},
                        "synthesizer": {"provider": "cartesia"},
                        "transcriber": {"provider": "deepgram"},
                        "input": {"provider": "plivo"},
                    },
                    "task_config": {},
                }
            ],
        },
        "agent_prompts": {"task_1": {"system_prompt": "old"}},
    }


@respx.mock
async def test_discovers_quick_tunnel_url():
    respx.get(f"{METRICS}/quicktunnel").mock(
        return_value=httpx.Response(200, json={"hostname": "fresh-words-here.trycloudflare.com"})
    )
    assert await tunnel_sync.discover_tunnel_url(METRICS) == NEW


@respx.mock
async def test_tunnel_not_up_yet_is_none():
    respx.get(f"{METRICS}/quicktunnel").mock(side_effect=httpx.ConnectError("refused"))
    assert await tunnel_sync.discover_tunnel_url(METRICS) is None
    respx.get(f"{METRICS}/quicktunnel").mock(return_value=httpx.Response(200, json={"hostname": ""}))
    assert await tunnel_sync.discover_tunnel_url(METRICS) is None
    assert await tunnel_sync.sync_once() is False


@respx.mock
async def test_new_tunnel_url_reprovisions_agent():
    respx.get(f"{METRICS}/quicktunnel").mock(
        return_value=httpx.Response(200, json={"hostname": "fresh-words-here.trycloudflare.com"})
    )
    stale = agent("https://old-dead-tunnel.trycloudflare.com")
    respx.get(AGENT).mock(
        side_effect=[httpx.Response(200, json=stale)] * 3 + [httpx.Response(200, json=agent(NEW))]
    )
    patch = respx.patch(AGENT).mock(return_value=httpx.Response(200, json={}))
    put = respx.put(AGENT).mock(return_value=httpx.Response(200, json={}))

    assert await tunnel_sync.sync_once() is True
    assert tunnel_sync.current_public_url() == NEW
    assert (
        json.loads(patch.calls[0].request.content)["agent_config"]["webhook_url"]
        == f"{NEW}/api/v1/bolna/webhook"
    )
    sent = json.loads(put.calls[0].request.content)
    tools = sent["agent_config"]["tasks"][0]["tools_config"]["api_tools"]
    assert all(t["url"].startswith(NEW) for t in tools["tools_params"].values())
    # Providers chosen in Agent Studio are kept.
    assert sent["agent_config"]["tasks"][0]["tools_config"]["synthesizer"] == {"provider": "cartesia"}


@respx.mock
async def test_agent_already_on_tunnel_url_is_left_alone():
    respx.get(f"{METRICS}/quicktunnel").mock(
        return_value=httpx.Response(200, json={"hostname": "fresh-words-here.trycloudflare.com"})
    )
    get = respx.get(AGENT).mock(return_value=httpx.Response(200, json=agent(NEW)))
    patch = respx.patch(AGENT)
    put = respx.put(AGENT)

    assert await tunnel_sync.sync_once() is True
    assert await tunnel_sync.sync_once() is True  # unchanged URL: no Bolna calls at all
    assert get.call_count == 1
    assert not patch.called and not put.called


def test_configured_base_url_reads_webhook():
    assert configured_base_url(agent(NEW)) == NEW
    assert configured_base_url({"agent_config": {"webhook_url": None}}) is None


def test_sync_disabled_without_bolna_or_tunnel(monkeypatch):
    assert tunnel_sync.sync_enabled() is True
    monkeypatch.setattr(get_settings(), "TUNNEL_METRICS_URL", "")
    assert tunnel_sync.sync_enabled() is False
