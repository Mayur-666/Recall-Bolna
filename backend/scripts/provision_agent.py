"""Create or update the Recall agent on Bolna.

  python scripts/provision_agent.py --create     # first time: prints the new agent id for .env
  python scripts/provision_agent.py              # update prompt, welcome, webhook, tools, interruption settings
  python scripts/provision_agent.py --dry-run    # print what would be sent, call nothing

The public URL is PUBLIC_BASE_URL, or else the running quick tunnel's URL (TUNNEL_METRICS_URL).
The backend already does this update by itself on start and whenever the tunnel URL changes;
this script is for the first --create and for checking by hand. See app/bolna/provisioning.py.
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
    welcome_message,
)
from app.bolna.provisioning import changed_providers, update_agent, webhook_url  # noqa: E402
from app.bolna.tunnel_sync import discover_tunnel_url  # noqa: E402
from app.core.config import get_settings  # noqa: E402
from app.integrations.bolna_client import BolnaClient, BolnaError  # noqa: E402


async def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--create", action="store_true")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()
    s = get_settings()

    base_url = s.PUBLIC_BASE_URL
    if not base_url and s.TUNNEL_METRICS_URL:
        base_url = await discover_tunnel_url(s.TUNNEL_METRICS_URL) or ""
        if base_url:
            print(f"Using the tunnel URL {base_url}")
    missing = [k for k in ("RECALL_TOOL_TOKEN",) if not getattr(s, k)]
    if not base_url:
        missing.append("PUBLIC_BASE_URL (or a running tunnel)")
    if not args.dry_run and not s.BOLNA_API_KEY:
        missing.append("BOLNA_API_KEY")
    if missing:
        print(f"Missing: {', '.join(missing)}")
        return 2
    tools = build_tools(base_url, s.RECALL_TOOL_TOKEN)
    webhook = webhook_url(base_url)

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

    before, after = await update_agent(client, s.BOLNA_AGENT_ID, base_url, s.RECALL_TOOL_TOKEN)
    print("Providers before:", before)
    print("Providers after: ", after)
    if changed := changed_providers(before, after):
        print(f"WARNING: provider fields changed: {changed} — check Agent Studio.")
        return 1
    print("Tools and interruption settings updated; provider choices unchanged.")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(asyncio.run(main()))
    except BolnaError as exc:
        print(f"Bolna API error {exc.status}: {exc.body_excerpt}")
        raise SystemExit(1) from None
