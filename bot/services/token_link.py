from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from sqlalchemy import select
from sqlalchemy.orm import Session

from bot.models import Player
from bot.services.seventeenlands import SeventeenLandsClient, classify_token_reply, extract_token
from bot.slug import disambiguate_slug, slugify

LinkKind = Literal["linked", "invalid_format", "rejected_by_17lands", "token_in_use"]


@dataclass
class LinkResult:
    kind: LinkKind
    player_id: str | None = None
    created: bool = False
    relinked: bool = False


def link_token(
    session: Session,
    client: SeventeenLandsClient,
    discord_id: str,
    discord_username: str,
    display_name: str,
    token_input: str,
    avatar_hash: str | None = None,
    *,
    opt_in: bool,
) -> LinkResult:
    """Verify a 17lands token and attach it to the caller, creating a player row if needed.

    Shared by ``/join``, ``/link-17lands``, and the auto-link listener. ``opt_in``
    sets the ranking flag only on a first link (new row, or a player who had no
    token yet); a re-link of an existing token holder preserves their current
    ``leaderboard_opt_in`` so a routine token swap never silently changes their
    ranking. ``relinked`` reports which case it was. Rejects a token already owned
    by another Discord account. The caller pulls stats and broadcasts.
    """
    try:
        token = extract_token(token_input)
    except ValueError:
        return LinkResult(kind="invalid_format")

    if not client.verify_token(token):
        return LinkResult(kind="rejected_by_17lands")

    other = session.execute(
        select(Player).where(Player.seventeenlands_token == token, Player.discord_id != discord_id)
    ).scalar_one_or_none()
    if other is not None:
        return LinkResult(kind="token_in_use", player_id=other.id)

    player = session.execute(
        select(Player).where(Player.discord_id == discord_id)
    ).scalar_one_or_none()
    created = player is None
    relinked = player is not None and player.seventeenlands_token is not None
    if player is None:
        taken_slugs = set(session.execute(select(Player.slug)).scalars().all())
        player = Player(
            slug=disambiguate_slug(slugify(display_name), taken_slugs),
            discord_id=discord_id,
            discord_username=discord_username,
            display_name=display_name,
            avatar_hash=avatar_hash,
            seventeenlands_token=token,
            active=True,
            leaderboard_opt_in=opt_in,
        )
        session.add(player)
    else:
        player.seventeenlands_token = token
        player.token_invalid = False
        if not relinked:
            player.leaderboard_opt_in = opt_in
        if avatar_hash is not None and player.avatar_hash != avatar_hash:
            player.avatar_hash = avatar_hash

    session.commit()
    return LinkResult(kind="linked", player_id=player.id, created=created, relinked=relinked)


def outcome_log_suffix(kind: str, raw_reply: str) -> str:
    """Diagnostic tag for token-flow result logs. Never includes raw user content."""
    if kind == "invalid_format":
        return f"[shape={classify_token_reply(raw_reply)} len={len(raw_reply or '')}]"
    try:
        token = extract_token(raw_reply)
    except ValueError:
        return ""
    return f"[token=…{token[-4:]}]"
