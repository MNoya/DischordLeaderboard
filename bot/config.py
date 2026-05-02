from __future__ import annotations

from pydantic import SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Process-wide configuration loaded from env (or .env in repo root).

    Discord fields are optional so non-bot entry points (alembic CLI, the
    seed script, tests) can construct Settings without them.
    """
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str
    discord_bot_token: SecretStr | None = None
    discord_guild_id: int | None = None
    discord_admin_role_id: int | None = None
    discord_botlog_channel_id: int | None = None
    # Code of the set the leaderboard is currently scoping to. Flip via redeploy.
    current_set_code: str = "SOS"
    public_site_url: str = "https://your-site.netlify.app"


settings = Settings()
