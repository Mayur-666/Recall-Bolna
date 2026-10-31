"""Keep the Bolna agent pointed at the current cloudflared quick-tunnel URL.

A quick tunnel gets a new random *.trycloudflare.com address every time it starts. cloudflared
reports it on its metrics server (GET /quicktunnel -> {"hostname": ...}), so the backend polls
that and re-provisions the agent whenever the address changes. No PUBLIC_BASE_URL needed.
"""

import asyncio
import logging

import httpx

from app.bolna.provisioning import changed_providers, configured_base_url, update_agent
from app.core.config import get_settings
from app.integrations.bolna_client import BolnaClient, BolnaError

log = logging.getLogger(__name__)

_current: str | None = None


def current_public_url() -> str | None:
    """The tunnel URL the agent was last pointed at (None until the first sync)."""
    return _current


async def discover_tunnel_url(metrics_url: str, http: httpx.AsyncClient | None = None) -> str | None:
    """https://<hostname> from cloudflared's metrics server, or None if it isn't up yet."""
    client = http or httpx.AsyncClient(timeout=5.0)
    try:
        resp = await client.get(f"{metrics_url.rstrip('/')}/quicktunnel")
        hostname = resp.json().get("hostname") if resp.status_code == 200 else None
    except (httpx.HTTPError, ValueError):
        return None
    finally:
        if http is None:
            await client.aclose()
    return f"https://{hostname}" if hostname else None


def sync_enabled() -> bool:
    s = get_settings()
    return bool(s.TUNNEL_METRICS_URL and s.BOLNA_API_KEY and s.BOLNA_AGENT_ID and s.RECALL_TOOL_TOKEN)


async def sync_once(client: BolnaClient | None = None, http: httpx.AsyncClient | None = None) -> bool:
    """One check: if the tunnel URL changed, re-provision the agent. True when the agent is in sync."""
    global _current
    s = get_settings()
    url = await discover_tunnel_url(s.TUNNEL_METRICS_URL, http)
    if url is None:
        return False
    if url == _current:
        return True
    client = client or BolnaClient()
    agent = await client.get_agent(s.BOLNA_AGENT_ID)
    if configured_base_url(agent) == url:
        log.info("Bolna agent already uses %s", url)
    else:
        before, after = await update_agent(client, s.BOLNA_AGENT_ID, url, s.RECALL_TOOL_TOKEN)
        log.info("Bolna agent now uses %s (tools: %s)", url, ", ".join(after["tools"]))
        if changed := changed_providers(before, after):
            log.warning("provider fields changed while provisioning: %s — check Agent Studio", changed)
    _current = url
    return True


async def run_tunnel_sync(stop: asyncio.Event) -> None:
    interval = get_settings().TUNNEL_SYNC_INTERVAL_S
    while not stop.is_set():
        try:
            in_sync = await sync_once()
        except (BolnaError, ValueError) as exc:
            log.warning("could not provision the Bolna agent: %s", exc)
            in_sync = False
        except Exception:
            log.exception("tunnel sync failed")
            in_sync = False
        # Poll fast until the first sync (tunnel still starting), then just watch for restarts.
        try:
            await asyncio.wait_for(stop.wait(), timeout=interval if in_sync else 3)
        except TimeoutError:
            pass
