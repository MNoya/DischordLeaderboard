from __future__ import annotations

from pydantic import SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Process-wide configuration loaded from env (or .env in repo root).

    Discord fields are optional so non-bot entry points (alembic CLI, the
    seed script, tests) can construct Settings without them.

    The active set code lives in ``bot/sets.py``, not here — rotate it by
    bumping ``ACTIVE_SET_CODE`` and redeploying.
    """
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str
    discord_bot_token: SecretStr | None = None
    discord_guild_id: int | None = None
    discord_admin_role_id: int | None = None
    discord_botlog_channel_id: int | None = None
    public_site_url: str = "https://dischord.pages.dev/leaderboard"
    auto_refresh_enabled: bool = True

    pod_draft_channel_id: int = 1028072146645295125
    pod_draft_session_prefix: str = "LLU"
    pod_draft_max_players: int = 10
    pod_draft_pick_timer: int = 60
    pod_draft_bots: int = 0
    pod_draft_fallback_tz: str = "America/New_York"
    pod_draft_skip_reminder_wait: bool = False
    pod_draft_test_roster: str = ""
    sesh_bot_id: int = 616754792965865495
    draftmancer_ws_url: str = "wss://draftmancer.com"
    mtga_emoji: str = "<:mtga:1504683442057773116>"
    llu_emoji: str = "<:llu:1504687468396412988>"


settings = Settings()
