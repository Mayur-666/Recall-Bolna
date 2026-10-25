"""Builders for the Bolna agent configuration Recall owns: prompt, welcome message,
custom tools and conversation (interruption) settings.

Provider blocks (LLM, synthesizer, transcriber, telephony) are chosen in Bolna Agent
Studio and are never overwritten by Recall. Field names follow the Bolna skills
reference (setup-tools/references/tool-schemas.md, create-agent).
"""

import copy
from pathlib import Path
from typing import Any

PROMPT_PATH = Path(__file__).with_name("agent_prompt.md")
WELCOME = "Hi {user_name}, I'm Recall. I'm holding {conversation_count} of your conversations. What would you like to remember?"


def load_prompt() -> str:
    return PROMPT_PATH.read_text(encoding="utf-8")


def welcome_message() -> str:
    return WELCOME


def _tool(
    name: str,
    description: str,
    pre_call: str,
    properties: dict[str, Any],
    required: list[str],
    url: str,
    token: str,
) -> dict[str, Any]:
    return {
        "name": name,
        "description": description,
        "pre_call_message": pre_call,
        "parameters": {"type": "object", "properties": properties, "required": required},
        "key": "custom_task",
        "value": {
            "method": "POST",
            "param": {p: f"%({p})s" for p in properties},
            "url": url,
            "api_token": f"Bearer {token}",
            "headers": {"Content-Type": "application/json"},
        },
    }


_SESSION_PROPS = {
    "recall_session": {
        "type": "string",
        "description": "Internal call id. Filled automatically; never ask for it.",
    },
    "execution_id": {
        "type": "string",
        "description": "Internal execution id. Filled automatically; never ask for it.",
    },
}


def build_tools(public_base_url: str, tool_token: str) -> dict[str, Any]:
    base = public_base_url.rstrip("/")
    if not base.startswith("https://"):
        raise ValueError(
            "PUBLIC_BASE_URL must be an https URL reachable by Bolna (e.g. a cloudflared tunnel)"
        )

    search = _tool(
        "search_memories",
        "Search the user's saved past conversations. Use this for EVERY question about what was said, decided, "
        "suggested, promised, planned or scheduled in past conversations, about who said something, about "
        "deadlines, action items or follow-ups, and for follow-up questions like 'who said that' or 'what about "
        "the other option'. Not for general knowledge.",
        "Let me check your memories.",
        {
            "question": {"type": "string", "description": "The user's question in their own words."},
            "standalone_query": {
                "type": "string",
                "description": "The question rewritten to be complete on its own, resolving 'that', 'it', 'the other "
                "one' etc. from this call. Example: 'Who said that?' -> 'Who suggested using WebSockets?'",
            },
            "from_date": {
                "type": "string",
                "description": "Start date YYYY-MM-DD if the user named a time period.",
            },
            "to_date": {
                "type": "string",
                "description": "End date YYYY-MM-DD if the user named a time period.",
            },
            "previous_result_ref": {
                "type": "string",
                "description": "The ref of an earlier result the follow-up refers to, if any.",
            },
            **_SESSION_PROPS,
        },
        ["question"],
        f"{base}/api/v1/bolna/tools/search_memories",
        tool_token,
    )
    context = _tool(
        "get_source_context",
        "Get the exact transcript lines around one earlier search result. Use when the user asks what exactly was "
        "said, who said it, or for more context about a specific result. Requires the result's ref.",
        "Let me pull up that part of the conversation.",
        {
            "ref": {"type": "string", "description": "The ref of the search result, e.g. c:... or m:..."},
            **_SESSION_PROPS,
        },
        ["ref"],
        f"{base}/api/v1/bolna/tools/get_source_context",
        tool_token,
    )
    tools = [search, context]
    return {
        "tools": tools,
        "tools_params": {t["name"]: copy.deepcopy(t["value"]) for t in tools},
    }


def build_task_config() -> dict[str, Any]:
    return {
        "number_of_words_for_interruption": 2,
        "interruption_backoff_period": 150,
        "incremental_delay": 300,
        "hangup_after_silence": 20,
    }


def default_provider_blocks() -> dict[str, Any]:
    """Only used when CREATING the agent; change providers afterwards in Agent Studio."""
    return {
        "llm_agent": {
            "agent_type": "simple_llm_agent",
            "agent_flow_type": "streaming",
            "llm_config": {
                "provider": "openai",
                "family": "openai",
                "model": "gpt-4.1-mini",
                "max_tokens": 200,
                "temperature": 0.2,
                "base_url": "https://api.openai.com/v1",
            },
        },
        "synthesizer": {
            "provider": "elevenlabs",
            "provider_config": {
                "voice": "Nila",
                "voice_id": "V9LCAAi4tTlqe9JadbCo",
                "model": "eleven_turbo_v2_5",
            },
            "stream": True,
            "buffer_size": 250,
            "audio_format": "wav",
        },
        "transcriber": {
            "provider": "deepgram",
            "model": "nova-3",
            "language": "en",
            "stream": True,
            "sampling_rate": 16000,
            "encoding": "linear16",
            "endpointing": 250,
        },
        "input": {"provider": "twilio", "format": "wav"},
        "output": {"provider": "twilio", "format": "wav"},
    }


def build_create_payload(tools: dict[str, Any], webhook_url: str | None) -> dict[str, Any]:
    return {
        "agent_config": {
            "agent_name": "Recall",
            "agent_welcome_message": welcome_message(),
            "webhook_url": webhook_url,
            "agent_type": "other",
            "tasks": [
                {
                    "task_type": "conversation",
                    "tools_config": {**default_provider_blocks(), "api_tools": tools},
                    "toolchain": {
                        "execution": "parallel",
                        "pipelines": [["transcriber", "llm", "synthesizer"]],
                    },
                    "task_config": build_task_config(),
                }
            ],
            "ingest_source_config": None,
        },
        "agent_prompts": {"task_1": {"system_prompt": load_prompt()}},
    }


_CONFIG_KEYS = ("agent_name", "agent_welcome_message", "webhook_url", "agent_type", "tasks", "ingest_source_config",
                "calling_guardrails")  # fmt: skip


def merge_for_put(
    current: dict[str, Any],
    tools: dict[str, Any],
    task_config: dict[str, Any],
    prompt: str,
    welcome: str,
    webhook_url: str | None,
) -> dict[str, Any]:
    """Full-update payload from the agent as Bolna returns it, replacing only what Recall owns."""
    source = current.get("agent_config", current)
    config = {k: copy.deepcopy(source[k]) for k in _CONFIG_KEYS if k in source}
    config["agent_welcome_message"] = welcome
    config["webhook_url"] = webhook_url
    tasks = config.get("tasks") or []
    if not tasks:
        raise ValueError("agent has no tasks; refusing to PUT a config that would drop its providers")
    conversation = next((t for t in tasks if t.get("task_type") == "conversation"), tasks[0])
    conversation.setdefault("tools_config", {})["api_tools"] = tools
    conversation["task_config"] = {**(conversation.get("task_config") or {}), **task_config}
    prompts = copy.deepcopy(current.get("agent_prompts") or {})
    prompts.setdefault("task_1", {})["system_prompt"] = prompt
    return {"agent_config": config, "agent_prompts": prompts}
