from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass(slots=True)
class Settings:
    telegram_token: str
    llm_api_key: str | None
    llm_api_url: str
    admin_ids: set[int]
    model_name: str = "gpt-5"
    db_path: str = "bot_data.sqlite3"

    # Database - PostgreSQL
    postgres_url: str = ""
    use_postgres: bool = False

    # Embeddings - OpenAI
    openai_api_key: str | None = None
    embedding_model: str = "text-embedding-3-small"

    # RAG Configuration
    rag_enabled: bool = False
    rag_top_k: int = 5
    rag_chunk_size: int = 512
    rag_chunk_overlap: int = 50


class ConfigError(RuntimeError):
    """Raised when required environment variables are missing."""


def _parse_admin_ids(raw_admins: str | None) -> set[int]:
    if not raw_admins:
        return set()

    parsed: set[int] = set()
    for chunk in raw_admins.split(","):
        value = chunk.strip()
        if not value:
            continue
        try:
            parsed.add(int(value))
        except ValueError as exc:
            raise ConfigError(
                "ADMIN_IDS must contain comma separated integer Telegram user IDs"
            ) from exc
    return parsed


def load_settings() -> Settings:
    telegram_token = (os.getenv("TELEGRAM_BOT_TOKEN") or "").strip()
    llm_api_key = (
        os.getenv("COMETAPI_API_KEY")
        or os.getenv("OPENAI_API_KEY")
        or ""
    ).strip()
    llm_api_url = (
        os.getenv("COMETAPI_BASE_URL")
        or "https://api.cometapi.com/v1/chat/completions"
    ).strip()
    default_db_path = "/tmp/bot_data.sqlite3" if os.getenv("VERCEL") == "1" else "bot_data.sqlite3"

    if not telegram_token:
        raise ConfigError("TELEGRAM_BOT_TOKEN environment variable is required")

    # Parse boolean env vars
    use_postgres = os.getenv("USE_POSTGRES", "false").lower() in ("true", "1", "yes")
    rag_enabled = os.getenv("RAG_ENABLED", "false").lower() in ("true", "1", "yes")

    # Parse integer env vars
    rag_top_k = int(os.getenv("RAG_TOP_K", "5"))
    rag_chunk_size = int(os.getenv("RAG_CHUNK_SIZE", "512"))
    rag_chunk_overlap = int(os.getenv("RAG_CHUNK_OVERLAP", "50"))

    return Settings(
        telegram_token=telegram_token,
        llm_api_key=llm_api_key or None,
        llm_api_url=llm_api_url,
        admin_ids=_parse_admin_ids(os.getenv("ADMIN_IDS")),
        model_name=(os.getenv("OPENAI_MODEL") or "gpt-5").strip(),
        db_path=(os.getenv("BOT_DB_PATH") or default_db_path).strip(),
        postgres_url=(os.getenv("POSTGRES_URL") or "").strip(),
        use_postgres=use_postgres,
        openai_api_key=(os.getenv("OPENAI_API_KEY") or "").strip() or None,
        embedding_model=(os.getenv("EMBEDDING_MODEL") or "text-embedding-3-small").strip(),
        rag_enabled=rag_enabled,
        rag_top_k=rag_top_k,
        rag_chunk_size=rag_chunk_size,
        rag_chunk_overlap=rag_chunk_overlap,
    )
