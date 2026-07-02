from __future__ import annotations

from pydantic import SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict

DRAFTMANCER_HOST = "draftmancer.com"


class Settings(BaseSettings):
    """Process-wide configuration loaded from env (or .env in repo root).

    Discord fields are optional so non-bot entry points (alembic CLI, the
    seed script, tests) can construct Settings without them.

    The active set is derived from today's date in ``bot/sets.py``, not here —
    rotation needs no config change.
    """
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str
    discord_bot_token: SecretStr | None = None
    discord_guild_id: int | None = None
    discord_admin_role_id: int | None = None
    discord_botlog_channel_id: int | None = None
    feedback_channel_id: int = 1504825374188507156
    public_site_url: str = "https://limitedlevelups.com"
    auto_refresh_enabled: bool = True

    @property
    def leaderboard_url(self) -> str:
        return f"{self.public_site_url.rstrip('/')}/leaderboard"

    scribe_cache_bust: bool = False
    format_schedule_enabled: bool = True

    pod_draft_channel_id: int = 1028072146645295125
    pod_draft_target_players: int = 8
    pod_draft_voice_channel_name: str = "Pod General"
    pod_schedule_enabled: bool = True
    pod_draft_session_prefix: str = "LLU"
    pod_draft_max_players: int = 10
    pod_draft_min_ready_players: int = 6
    pod_draft_pick_timer: int = 60
    pod_draft_bots: int = 0
    pod_draft_fallback_tz: str = "America/New_York"
    pod_draft_skip_reminder_wait: bool = False
    pod_draft_end_watchdog_minutes: int = 90
    sesh_bot_id: int = 616754792965865495
    draftmancer_ws_url: str = f"wss://{DRAFTMANCER_HOST}"
    draftmancer_web_url: str = f"https://{DRAFTMANCER_HOST}"
    mpt_api_key: SecretStr | None = None

    youtube_api_key: SecretStr | None = None
    youtube_channel_handle: str = "limitedlevel-ups"
    libsyn_feed_url: str = "https://feeds.libsyn.com/limitedlevelups/rss"
    media_sync_enabled: bool = True
    profile_sync_enabled: bool = True


settings = Settings()
