"""Thin client for the documented Bolna REST API (https://api.bolna.ai).

The API key is sent only in the Authorization header and is never logged or put in
an error message. Error bodies are truncated before they are surfaced.
"""

import logging
from typing import Any

import httpx

from app.core.config import get_settings

log = logging.getLogger(__name__)


class BolnaError(Exception):
    def __init__(self, status: int, body_excerpt: str, message: str | None = None) -> None:
        self.status = status
        self.body_excerpt = body_excerpt
        super().__init__(message or f"Bolna API returned {status}: {body_excerpt}")


class BolnaClient:
    def __init__(self, http: httpx.AsyncClient | None = None) -> None:
        self.settings = get_settings()
        self._http = http

    async def _request(self, method: str, path: str, json: dict[str, Any] | None = None) -> Any:
        key = self.settings.BOLNA_API_KEY
        if not key:
            raise BolnaError(0, "", "BOLNA_API_KEY is not set in the server environment")
        url = f"{self.settings.BOLNA_BASE_URL.rstrip('/')}{path}"
        headers = {"Authorization": f"Bearer {key}", "Accept": "application/json"}
        client = self._http or httpx.AsyncClient(timeout=30.0)
        try:
            resp = await client.request(method, url, json=json, headers=headers)
        except httpx.HTTPError as exc:
            raise BolnaError(0, type(exc).__name__, f"Could not reach Bolna: {type(exc).__name__}") from exc
        finally:
            if self._http is None:
                await client.aclose()
        if resp.status_code >= 400:
            excerpt = resp.text[:300]
            log.warning("Bolna %s %s -> %s", method, path, resp.status_code)
            raise BolnaError(resp.status_code, excerpt)
        return resp.json() if resp.content else {}

    async def get_me(self) -> dict[str, Any]:
        result: dict[str, Any] = await self._request("GET", "/user/me")
        return result

    async def create_agent(self, payload: dict[str, Any]) -> str:
        out = await self._request("POST", "/v2/agent", payload)
        return str(out.get("agent_id") or out.get("id"))

    async def get_agent(self, agent_id: str) -> dict[str, Any]:
        result: dict[str, Any] = await self._request("GET", f"/v2/agent/{agent_id}")
        return result

    async def patch_agent(self, agent_id: str, payload: dict[str, Any]) -> dict[str, Any]:
        result: dict[str, Any] = await self._request("PATCH", f"/v2/agent/{agent_id}", payload)
        return result

    async def put_agent(self, agent_id: str, payload: dict[str, Any]) -> dict[str, Any]:
        result: dict[str, Any] = await self._request("PUT", f"/v2/agent/{agent_id}", payload)
        return result

    async def mint_web_session(self, agent_id: str, user_data: dict[str, Any]) -> dict[str, Any]:
        """Single-use web-call session for the browser SDK (@bolna/web-call)."""
        result: dict[str, Any] = await self._request(
            "POST", self.settings.BOLNA_WEB_CALL_SESSION_PATH, {"agent_id": agent_id, "user_data": user_data}
        )
        return result

    async def make_call(self, agent_id: str, phone_e164: str, user_data: dict[str, Any]) -> str:
        out = await self._request(
            "POST",
            "/call",
            {"agent_id": agent_id, "recipient_phone_number": phone_e164, "user_data": user_data},
        )
        return str(out["execution_id"])

    async def get_execution(self, execution_id: str) -> dict[str, Any]:
        result: dict[str, Any] = await self._request("GET", f"/executions/{execution_id}")
        return result


def get_bolna_client() -> BolnaClient:
    return BolnaClient()
