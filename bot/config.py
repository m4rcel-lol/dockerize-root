from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

try:
    from dotenv import load_dotenv
except ImportError:  # pragma: no cover - dependency exists in production image
    load_dotenv = None


def _env_bool(name: str, default: bool = False) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "y", "on"}


def _env_int(name: str, default: int) -> int:
    value = os.getenv(name)
    if value is None:
        return default
    try:
        return int(value)
    except ValueError:
        return default


@dataclass(slots=True, frozen=True)
class Config:
    token: str
    database_path: str
    max_channels_per_container: int
    default_container_visibility: str
    allow_bot_invites: bool
    emoji_docker: str
    emoji_success: str
    emoji_failure: str
    emoji_warning: str

    @classmethod
    def from_env(cls) -> "Config":
        if load_dotenv is not None:
            load_dotenv()

        token = os.getenv("DISCORD_TOKEN", "").strip()
        if not token or token == "put-token-here":
            raise RuntimeError("DISCORD_TOKEN is missing. Put your bot token in .env.")

        database_path = os.getenv("DATABASE_PATH", "/app/data/dockerize.sqlite3").strip()
        Path(database_path).parent.mkdir(parents=True, exist_ok=True)

        visibility = os.getenv("DEFAULT_CONTAINER_VISIBILITY", "private").strip().lower()
        if visibility not in {"private", "public"}:
            visibility = "private"

        return cls(
            token=token,
            database_path=database_path,
            max_channels_per_container=max(4, _env_int("MAX_CHANNELS_PER_CONTAINER", 10)),
            default_container_visibility=visibility,
            allow_bot_invites=_env_bool("ALLOW_BOT_INVITES", False),
            emoji_docker=os.getenv("EMOJI_DOCKER", ":docker:"),
            emoji_success=os.getenv("EMOJI_SUCCESS", ":success:"),
            emoji_failure=os.getenv("EMOJI_FAILURE", ":failure:"),
            emoji_warning=os.getenv("EMOJI_WARNING", ":warning:"),
        )
