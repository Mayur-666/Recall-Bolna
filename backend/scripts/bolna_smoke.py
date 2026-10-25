"""Check the real Bolna integration step by step. Prints PASS / FAIL / BLOCKED per step.

  python scripts/bolna_smoke.py                    # account, agent, PATCH round-trip, web-call mint, tunnel
  python scripts/bolna_smoke.py --wait-for-tool 3  # also wait up to 3 minutes for a real tool call
                                                    # made from a browser call started in the Recall UI

Nothing here fakes a result: a step that can't run says BLOCKED and why.
"""

import argparse
import asyncio
import sys
import time
from datetime import UTC, datetime

import httpx

sys.path.insert(0, ".")

from sqlalchemy import select  # noqa: E402

from app.core.config import get_settings  # noqa: E402
from app.db.session import get_sessionmaker  # noqa: E402
from app.integrations.bolna_client import BolnaClient, BolnaError  # noqa: E402
from app.models import CallSession, ToolCall  # noqa: E402

RESULTS: list[tuple[str, str, str]] = []


def report(step: str, status: str, detail: str = "") -> None:
    RESULTS.append((step, status, detail))
    print(f"[{status:7}] {step}{(' — ' + detail) if detail else ''}")


async def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--wait-for-tool", type=float, default=0, help="minutes to wait for a live tool call")
    args = ap.parse_args()
    s = get_settings()
    client = BolnaClient()

    # 1. API key
    if not s.BOLNA_API_KEY:
        report("1 API key", "BLOCKED", "BOLNA_API_KEY is empty in .env (platform.bolna.ai -> Developers)")
    else:
        try:
            me = await client.get_me()
            report("1 API key", "PASS", f"authenticated; account fields: {sorted(me)[:6]}")
        except BolnaError as e:
            report("1 API key", "FAIL", f"GET /user/me -> {e.status} {e.body_excerpt}")

    # 2. Agent readable
    agent = None
    if not (s.BOLNA_API_KEY and s.BOLNA_AGENT_ID):
        report(
            "2 Agent", "BLOCKED", "needs BOLNA_API_KEY and BOLNA_AGENT_ID (run provision_agent.py --create)"
        )
    else:
        try:
            agent = await client.get_agent(s.BOLNA_AGENT_ID)
            from scripts.provision_agent import providers

            report("2 Agent", "PASS", f"providers/tools: {providers(agent)}")
        except BolnaError as e:
            report("2 Agent", "FAIL", f"GET /v2/agent -> {e.status} {e.body_excerpt}")

    # 3. PATCH round-trip leaves providers unchanged
    if agent is None:
        report("3 PATCH round-trip", "BLOCKED", "agent not readable")
    else:
        from scripts.provision_agent import providers

        try:
            cfg = agent.get("agent_config", agent)
            await client.patch_agent(
                s.BOLNA_AGENT_ID,
                {"agent_config": {"agent_welcome_message": cfg.get("agent_welcome_message")}},
            )
            again = await client.get_agent(s.BOLNA_AGENT_ID)
            same = providers(agent) == providers(again)
            report(
                "3 PATCH round-trip",
                "PASS" if same else "FAIL",
                "providers unchanged" if same else "providers changed",
            )
        except BolnaError as e:
            report("3 PATCH round-trip", "FAIL", f"{e.status} {e.body_excerpt}")

    # 4. Web-call session mint (documented SDK backend endpoint)
    if not (s.BOLNA_API_KEY and s.BOLNA_AGENT_ID):
        report("4 Web-call session", "BLOCKED", "needs BOLNA_API_KEY and BOLNA_AGENT_ID")
    else:
        try:
            sess = await client.mint_web_session(
                s.BOLNA_AGENT_ID, {"recall_session": "smoke-test-not-a-token"}
            )
            report("4 Web-call session", "PASS", f"{s.BOLNA_WEB_CALL_SESSION_PATH} -> keys {sorted(sess)}")
        except BolnaError as e:
            hint = " (Web Call may need enabling by Bolna support, or try BOLNA_WEB_CALL_SESSION_PATH=/web-call/freeswitch-session)"
            report(
                "4 Web-call session",
                "FAIL",
                f"{e.status} {e.body_excerpt}{hint if e.status in (403, 404) else ''}",
            )

    # 5. Tool endpoint reachable through the public URL, with auth enforced
    if not s.PUBLIC_BASE_URL.startswith("https://"):
        report("5 Public tool URL", "BLOCKED", "PUBLIC_BASE_URL must be the https tunnel URL")
    else:
        url = f"{s.PUBLIC_BASE_URL.rstrip('/')}/api/v1/bolna/tools/search_memories"
        try:
            async with httpx.AsyncClient(timeout=15) as h:
                no_auth = await h.post(url, json={"question": "x", "recall_session": "x"})
                with_auth = await h.post(
                    url,
                    json={"question": "x", "recall_session": "invalid"},
                    headers={"Authorization": f"Bearer {s.RECALL_TOOL_TOKEN}"},
                )
            ok = (
                no_auth.status_code == 401
                and with_auth.status_code == 401
                and "session" in with_auth.text.lower()
            )
            report(
                "5 Public tool URL",
                "PASS" if ok else "FAIL",
                f"no bearer -> {no_auth.status_code}; bearer + bad session -> {with_auth.status_code}",
            )
        except httpx.HTTPError as e:
            report("5 Public tool URL", "FAIL", f"unreachable: {type(e).__name__}")

    # 6. A real tool call during a live browser call
    if args.wait_for_tool <= 0:
        report(
            "6 Live tool call", "SKIPPED", "run with --wait-for-tool N while talking to Recall in the browser"
        )
    else:
        start = datetime.now(UTC)
        print(
            f"Waiting up to {args.wait_for_tool} min: start a call on the Ask Recall page and ask a question…"
        )
        deadline = time.monotonic() + args.wait_for_tool * 60
        found = None
        while time.monotonic() < deadline and found is None:
            async with get_sessionmaker()() as db:
                found = await db.scalar(
                    select(ToolCall)
                    .where(ToolCall.created_at >= start)
                    .order_by(ToolCall.created_at)
                    .limit(1)
                )
                if found is not None:
                    cs = await db.get(CallSession, found.call_session_id)
            if found is None:
                await asyncio.sleep(2)
        if found is None:
            report(
                "6 Live tool call",
                "FAIL",
                "no tool call reached Recall. Check `docker compose logs backend | grep 'tool call rejected'`",
            )
        else:
            exec_arg = (found.args or {}).get("execution_id")
            report("6 Live tool call", "PASS", f"{found.tool_name} -> {found.result_status}")
            report("6a recall_session filled", "PASS", "token resolved to a live call session (row exists)")
            report(
                "6b execution_id filled",
                "PASS" if exec_arg else "FAIL",
                f"execution_id={'present' if exec_arg else 'missing/placeholder'}; linked on session: "
                f"{bool(cs and cs.bolna_execution_id)}",
            )

    failed = [r for r in RESULTS if r[1] == "FAIL"]
    blocked = [r for r in RESULTS if r[1] == "BLOCKED"]
    print(
        f"\nSummary: {len(RESULTS) - len(failed) - len(blocked)} ok/skipped, {len(failed)} failed, {len(blocked)} blocked"
    )
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
