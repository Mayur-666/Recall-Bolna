"""Create or update the Recall agent on Bolna.

  python scripts/provision_agent.py --create     # first time: prints the new agent id for .env
  python scripts/provision_agent.py              # update prompt, welcome, webhook, tools, interruption settings
  python scripts/provision_agent.py --dry-run    # print what would be sent, call nothing

Bolna's documented PATCH /v2/agent/{id} accepts agent_prompts and a few agent_config
fields (welcome message, webhook, synthesizer, ...) but not tools or task_config. So:
  1. PATCH prompt + welcome + webhook (never touches providers);
  2. GET -> replace only api_tools and Recall's task_config keys -> PUT,
     keeping the LLM / synthesizer / transcriber / telephony chosen in Agent Studio.
Provider blocks are printed before and after so you can see they're unchanged.
"""

import argparse
import asyncio
import json
import sys
from typing import Any

sys.path.insert(0, ".")

from app.bolna.agent_config import (  # noqa: E402
    build_create_payload,
    build_task_config,
    build_tools,
    load_prompt,
    merge_for_put,
    welcome_message,
)
from app.core.config import get_settings  # noqa: E402
from app.integrations.bolna_client import BolnaClient, BolnaError  # noqa: E402


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


async def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--create", action="store_true")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()
    s = get_settings()

    missing = [k for k in ("RECALL_TOOL_TOKEN", "PUBLIC_BASE_URL") if not getattr(s, k)]
    if not args.dry_run and not s.BOLNA_API_KEY:
        missing.append("BOLNA_API_KEY")
    if missing:
        print(f"Missing in .env: {', '.join(missing)}")
        return 2
    tools = build_tools(s.PUBLIC_BASE_URL, s.RECALL_TOOL_TOKEN)
    webhook = f"{s.PUBLIC_BASE_URL.rstrip('/')}/api/v1/bolna/webhook"

    def redact(obj: Any) -> str:
        return json.dumps(obj, indent=2).replace(s.RECALL_TOOL_TOKEN, "***")

    client = BolnaClient()
    if args.create:
        payload = build_create_payload(tools, webhook)
        if args.dry_run:
            print(redact(payload))
            return 0
        agent_id = await client.create_agent(payload)
        print(f"Created agent. Add this to .env:\nBOLNA_AGENT_ID={agent_id}")
        print("Then pick the LLM, voice (TTS) and transcriber (STT) in Bolna Agent Studio.")
        return 0

    patch = {
        "agent_config": {"agent_welcome_message": welcome_message(), "webhook_url": webhook},
        "agent_prompts": {"task_1": {"system_prompt": load_prompt()}},
    }
    if args.dry_run:
        print("PATCH", redact(patch))
        print("PUT: api_tools =", redact(tools))
        print("PUT: task_config keys =", build_task_config())
        return 0
    if not s.BOLNA_AGENT_ID:
        print("BOLNA_AGENT_ID is empty. Run with --create first.")
        return 2

    before = await client.get_agent(s.BOLNA_AGENT_ID)
    print("Providers before:", providers(before))
    await client.patch_agent(s.BOLNA_AGENT_ID, patch)
    print("PATCHed prompt, welcome message and webhook URL.")

    current = await client.get_agent(s.BOLNA_AGENT_ID)
    put_payload = merge_for_put(
        current, tools, build_task_config(), load_prompt(), welcome_message(), webhook
    )
    await client.put_agent(s.BOLNA_AGENT_ID, put_payload)
    after = await client.get_agent(s.BOLNA_AGENT_ID)
    print("Providers after: ", providers(after))
    changed = {
        k
        for k in ("llm", "synthesizer", "transcriber", "input")
        if providers(before)[k] != providers(after)[k]
    }
    if changed:
        print(f"WARNING: provider fields changed: {sorted(changed)} — check Agent Studio.")
        return 1
    print("Tools and interruption settings updated; provider choices unchanged.")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(asyncio.run(main()))
    except BolnaError as exc:
        print(f"Bolna API error {exc.status}: {exc.body_excerpt}")
        raise SystemExit(1) from None
