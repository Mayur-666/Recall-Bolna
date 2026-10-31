"""Push Recall's prompt, tools, webhook and call settings to the Bolna agent.

Bolna's documented PATCH /v2/agent/{id} accepts agent_prompts and a few agent_config
fields (welcome message, webhook, synthesizer, ...) but not tools or task_config. So:
  1. PATCH prompt + welcome + webhook (never touches providers);
  2. GET -> replace only api_tools and Recall's task_config keys -> PUT,
     keeping the LLM / synthesizer / transcriber / telephony chosen in Agent Studio.
Used by scripts/provision_agent.py and by the tunnel sync on backend start.
"""

from typing import Any

from app.bolna.agent_config import (
    build_task_config,
    build_tools,
    load_prompt,
    merge_for_put,
    welcome_message,
)
from app.integrations.bolna_client import BolnaClient

WEBHOOK_PATH = "/api/v1/bolna/webhook"
PROVIDER_KEYS = ("llm", "synthesizer", "transcriber", "input")


def webhook_url(public_base_url: str) -> str:
    return f"{public_base_url.rstrip('/')}{WEBHOOK_PATH}"


def providers(agent: dict[str, Any]) -> dict[str, Any]:
    cfg = agent.get("agent_config", agent)
    tasks = cfg.get("tasks") or []
    tc = (tasks[0] if tasks else {}).get("tools_config") or {}
    llm = (tc.get("llm_agent") or {}).get("llm_config") or {}
    return {
        "llm": f"{llm.get('provider')}:{llm.get('model')}",
        "synthesizer": (tc.get("synthesizer") or {}).get("provider"),
        "transcriber": (tc.get("transcriber") or {}).get("provider"),
        "input": (tc.get("input") or {}).get("provider"),
        "tools": [t.get("name") for t in ((tc.get("api_tools") or {}).get("tools") or [])],
    }


def configured_base_url(agent: dict[str, Any]) -> str | None:
    """The public URL the agent currently calls back on, read from its webhook."""
    hook = (agent.get("agent_config", agent) or {}).get("webhook_url") or ""
    return hook[: -len(WEBHOOK_PATH)] if hook.endswith(WEBHOOK_PATH) else None


async def update_agent(
    client: BolnaClient, agent_id: str, public_base_url: str, tool_token: str
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Point the agent's tools and webhook at `public_base_url`. Returns providers (before, after)."""
    tools = build_tools(public_base_url, tool_token)
    hook = webhook_url(public_base_url)
    before = await client.get_agent(agent_id)
    await client.patch_agent(
        agent_id,
        {
            "agent_config": {"agent_welcome_message": welcome_message(), "webhook_url": hook},
            "agent_prompts": {"task_1": {"system_prompt": load_prompt()}},
        },
    )
    current = await client.get_agent(agent_id)
    await client.put_agent(
        agent_id,
        merge_for_put(current, tools, build_task_config(), load_prompt(), welcome_message(), hook),
    )
    after = await client.get_agent(agent_id)
    return providers(before), providers(after)


def changed_providers(before: dict[str, Any], after: dict[str, Any]) -> list[str]:
    return sorted(k for k in PROVIDER_KEYS if before[k] != after[k])
