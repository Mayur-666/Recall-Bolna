"""Single source of configuration. Every value is overridable by environment variable."""

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=None, extra="ignore")

    # --- database ---
    DATABASE_URL: str = "postgresql+asyncpg://recall:recall@localhost:5432/recall"
    TEST_DATABASE_URL: str = "postgresql+asyncpg://recall:recall@localhost:5432/recall_test"

    # --- auth ---
    JWT_SECRET: str = "dev-only-insecure-secret-change-me"
    JWT_TTL_MIN: int = 720
    DEMO_EMAIL: str = "demo@recall.local"
    DEMO_PASSWORD: str = ""
    DEMO_NAME: str = "Mayur"
    APP_TIMEZONE: str = "Asia/Kolkata"
    # The web app is served over plain http on localhost in dev; set true behind HTTPS.
    COOKIE_SECURE: bool = False
    GOOGLE_CLIENT_ID: str = ""
    GOOGLE_CLIENT_SECRET: str = ""

    # --- model (embeddings + extraction) ---
    MODEL_BASE_URL: str = "http://ollama:11434/v1"
    MODEL_API_KEY: str = "ollama"
    EMBED_MODEL: str = "nomic-embed-text"
    EMBED_DIM: int = 768
    EMBED_QUERY_PREFIX: str = "search_query: "
    EMBED_DOC_PREFIX: str = "search_document: "
    EMBED_TIMEOUT_S: float = 1.5
    EXTRACT_MODEL: str = "qwen2.5:7b-instruct"

    # --- retrieval ---
    RETRIEVAL_MIN_VECTOR_SIM: float = 0.68  # calibrated on nomic-embed-text, see docs/eval-results.md
    AMBIGUITY_MARGIN: float = 0.15
    LINK_MIN_SIM: float = 0.75
    RRF_K: int = 60
    CANDIDATES_PER_LIST: int = 20
    MAX_RESULTS: int = 5
    EXCERPT_MAX_CHARS: int = 400

    # --- ingestion ---
    MAX_UPLOAD_BYTES: int = 1_000_000
    MAX_TRANSCRIPT_CHARS: int = 200_000
    WORKER_ENABLED: bool = True

    # --- bolna ---
    BOLNA_API_KEY: str = ""
    BOLNA_AGENT_ID: str = ""
    BOLNA_BASE_URL: str = "https://api.bolna.ai"
    # @bolna/web-call 3.0.1 mints via this path (its Session type docs); bolna.ai docs show /web-call/session.
    BOLNA_WEB_CALL_SESSION_PATH: str = "/web-call/freeswitch-session"
    BOLNA_WEBHOOK_IP: str = "13.203.39.153"
    RECALL_TOOL_TOKEN: str = ""
    PUBLIC_BASE_URL: str = ""
    CALL_TOKEN_TTL_MIN: int = 30
    TOOL_RATE_LIMIT_PER_MIN: int = 30


@lru_cache
def get_settings() -> Settings:
    return Settings()
