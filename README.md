# Recall

**Ask what was decided. Hear the answer, see the line.**

Recall reads your meeting transcripts and answers questions out loud: who said it, in which meeting, and the exact quote. When a decision changed later, it says so. When nobody said it, it says that too, instead of guessing.

Built for the Bolna Symphony Buildathon. Voice runs on [Bolna](https://bolna.ai); everything else runs locally.

## What it does

- **Add a meeting transcript** (`.txt`, `.md`, `.vtt`, `.srt`, or paste it). A local model extracts decisions, commitments, dates and facts. Each one must quote the transcript word for word, or it's discarded.
- **Ask by voice or text.**
  - **Voice:** tap the orb for a live Bolna web call, or have Recall call your phone.
  - **Text:** type or dictate into the ask box; the answer is spoken by a local Kokoro voice.
- **See the evidence.** Matching memories light up on a memory map, and every answer links to the highlighted line in the transcript.
- **Tell it things to remember.** During a call, say "remember that we moved the demo to Friday". It's saved as a voice note and processed like any transcript, and it appears on the map within a few seconds.
- **Changed and conflicting decisions.** When a later meeting replaces a decision, Recall links the two and answers with the current one. When two meetings contradict each other, it asks which one applies.

## How it works

```
 Browser (Next.js)                       Backend (FastAPI)                 Local models (Docker)
 ─────────────────                       ─────────────────                 ─────────────────────
 memory map, ask box  ── /api ──▶  search: keyword + vector (pgvector)  ──▶ Ollama: nomic-embed-text,
 voice orb (Bolna SDK)             ingestion worker: parse → chunk →         qwen2.5:7b-instruct
                                   extract → link decisions               Kokoro-82M TTS (af_heart)
         ▲                                    ▲
         │ live events (SSE)                  │ tool calls: search_memories,
         │                                    │ get_source_context, save_memory
         └──────── Bolna voice agent ─────────┘  (HTTPS via a cloudflared tunnel)
```

- **Grounded answers:** answers only come from search results. A search that clears no similarity threshold returns "no reliable memory", and the agent says so.
- **Per-call identity:** each call gets a random token. Bolna passes it back on every tool call, so a call can only search the signed-in user's memories.
- **Evaluation:** on the seeded sample account, retrieval passes 18/18 evaluation cases with a p95 search latency of 27 ms. See [docs/eval-results.md](docs/eval-results.md) and [docs/model-benchmark.md](docs/model-benchmark.md).

## Quick start

**Requirements:**
- Docker Desktop.
- About 10 GB of free disk for models and images.
- An NVIDIA GPU is recommended for Ollama. With no GPU, remove the `deploy:` block under `ollama` in `docker-compose.yml` and extraction runs on CPU, more slowly.

```bash
git clone <this repo> && cd recall-bolna
cp .env.example .env          # then set the secrets: POSTGRES_PASSWORD, JWT_SECRET, DEMO_PASSWORD, RECALL_TOOL_TOKEN
docker compose up -d --build  # first build downloads the models; takes a while
```

The `ollama-init` service pulls `nomic-embed-text` and `qwen2.5:7b-instruct` on first start, and the `tts` image downloads Kokoro-82M while it builds. After that, nothing downloads at runtime.

Load the sample meetings into the demo account (`DEMO_EMAIL` / `DEMO_PASSWORD` from `.env`):

```bash
docker compose exec backend python scripts/seed_demo.py
```

Open **http://localhost:3000**, sign in, and try typing "Which deployment provider did we pick?".

| Service | Port | Purpose |
|---|---|---|
| `web` | 3000 | Next.js app |
| `backend` | 8000 | FastAPI API, Bolna tool endpoints, ingestion worker |
| `postgres` | 5432 | Postgres 16 + pgvector |
| `ollama` | 11434 | embeddings and extraction |
| `tts` | internal | Kokoro-82M text-to-speech |
| `tunnel` | — | cloudflared quick tunnel, so Bolna can reach the backend (URL synced to the agent automatically) |

## Voice calls (Bolna)

Typing and dictation work without Bolna. Live voice calls need a Bolna account, an agent, and a public HTTPS URL that Bolna can reach your backend on. Full guide: **[docs/bolna-setup.md](docs/bolna-setup.md)**. In short:

```bash
# 1. put BOLNA_API_KEY in .env, start everything (the tunnel starts with the rest)
docker compose up -d --build

# 2. create the agent once, then copy the printed BOLNA_AGENT_ID into .env
docker compose exec backend python scripts/provision_agent.py --create
docker compose up -d backend
```

That's all. The `tunnel` service is a cloudflared quick tunnel, and its random `trycloudflare.com` URL changes on every start. The backend reads the current URL from the tunnel and updates the Bolna agent's tools and webhook by itself, both on start and whenever the tunnel restarts. Check it with `docker compose logs backend | grep "Bolna agent"`. Leave `PUBLIC_BASE_URL` empty, unless you serve the backend on a fixed domain.

Choose the agent's LLM, voice and transcriber in Bolna Agent Studio. Provisioning never overrides them.

## Configuration

Everything is in `.env`; [.env.example](.env.example) documents each setting. The ones you're most likely to change:

| Setting | Default | What it does |
|---|---|---|
| `EXTRACT_MODEL` | `qwen2.5:7b-instruct` | model that extracts memories and writes typed answers |
| `KOKORO_VOICE` | `af_heart` | voice for spoken answers to typed questions; also baked in: `af_bella`, `af_nicole`, `af_sarah`, `am_michael`, `am_adam`, `bf_emma`, `bm_george` |
| `RETRIEVAL_MIN_VECTOR_SIM` | `0.68` | how strict "no reliable memory" is (calibrated by the evaluation) |
| `LINK_MIN_SIM` | `0.75` | how similar two topics must be to cluster or link |
| `APP_TIMEZONE` | `Asia/Kolkata` | meaning of "today" / "last week" |

## Development

```bash
# live reload: Next.js dev server + uvicorn --reload
docker compose -f docker-compose.yml -f docker-compose.dev.yml up --build --watch

# backend tests (use a separate recall_test database)
docker compose run --rm backend pytest -q
```

## Project layout

```
backend/   FastAPI app: api/, services/ (retrieval, extraction, linking, answers, TTS), workers/, bolna/ (agent prompt + config)
web/       Next.js app: landing page, /space (memory map + voice), components/, lib/
tts/       Kokoro-82M text-to-speech service (model baked into the image)
docs/      Bolna setup, evaluation results, model benchmark
```
