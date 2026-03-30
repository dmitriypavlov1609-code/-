from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass(slots=True)
class Settings:
    telegram_token: str
    groq_api_key: str | None
    admin_ids: set[int]
    model_name: str = "llama-3.3-70b-versatile"
    db_path: str = "bot_data.sqlite3"


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
    groq_api_key = (os.getenv("GROQ_API_KEY") or "").strip()

    if not telegram_token:
        raise ConfigError("TELEGRAM_BOT_TOKEN environment variable is required")
    return Settings(
        telegram_token=telegram_token,
        groq_api_key=groq_api_key or None,
        admin_ids=_parse_admin_ids(os.getenv("ADMIN_IDS")),
        model_name=os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile"),
        db_path=(os.getenv("BOT_DB_PATH") or "bot_data.sqlite3").strip(),
    )
