from __future__ import annotations

import logging
import unicodedata
from dataclasses import dataclass
from datetime import datetime, timezone

import discord
from discord import app_commands
from discord.ext import commands
from sqlalchemy import case, func, select
from sqlalchemy.orm import Session

from bot import audit, emojis
from bot.commands.stats import _rank_players_for_set, process_stats, render_embed as render_stats_embed
from bot.config import settings
from bot.database import SessionLocal
from bot.models import DraftEvent, LeaderboardMessage, MagicSet, Player, PlayerStats, PodDraftEvent, PodDraftParticipant
from bot.scoring import DEFAULT_QUEUE_GROUPS, boxes_for_event, compute_score
from bot.sets import ACTIVE_SET_CODE


# Color archetype label → PlayerArchetypeScore.archetype key
COLOR_CHOICES: dict[str, str] = {
    # 2-color guilds
    "Azorius":  "WU",
    "Orzhov":   "WB",
    "Boros":    "WR",
    "Selesnya": "WG",
    "Dimir":    "UB",
    "Izzet":    "UR",
    "Simic":    "UG",
    "Rakdos":   "BR",
    "Golgari":  "BG",
    "Gruul":    "RG",
    # 3-color shards/wedges
    "Esper":    "WUB",
    "Jeskai":   "WUR",
    "Bant":     "WUG",
    "Mardu":    "WBR",
    "Abzan":    "WBG",
    "Naya":     "WRG",
    "Grixis":   "UBR",
    "Sultai":   "UBG",
    "Temur":    "URG",
    "Jund":     "BRG",
    # 4+ color soup
    "Soup":     "MULTI",
}

logger = logging.getLogger(__name__)


@dataclass
class LeaderboardEntry:
    rank: int
    player_id: str
    slug: str
    display_name: str
    score: float
    trophies: int
    events: int = 0


@dataclass
class LeaderboardData:
    set_code: str
    set_name: str
    top: list[LeaderboardEntry]
    viewer: LeaderboardEntry | None
    last_updated: datetime | None = None
    drafter_count: int = 0
    show_score: bool = True
    filter_type: str | None = None
    filter_value: str | None = None


def process_leaderboard(
    session: Session, viewer_discord_id: str | None, top_n: int = 10,
    include_zero_scores: bool = False,
) -> LeaderboardData | None:
    magic_set = _current_set(session)
    if magic_set is None:
        return None

    ranked = _rank_players_for_set(session, magic_set.id)

    # Default view hides players with no points yet — they're "drafting but
    # not on the board". The full-DM view passes include_zero_scores=True
    # so signed-up players who haven't scored still appear
    visible = ranked if include_zero_scores else [row for row in ranked if row[5] > 0]
    top = [
        LeaderboardEntry(rank=rank, player_id=pid, slug=slug, display_name=name, score=score, trophies=trophies)
        for rank, pid, slug, name, _did, score, trophies in visible[:top_n]
    ]

    viewer_entry: LeaderboardEntry | None = None
    if viewer_discord_id is not None:
        for rank, pid, slug, name, did, score, trophies in ranked:
            if did == viewer_discord_id:
                viewer_entry = LeaderboardEntry(
                    rank=rank, player_id=pid, slug=slug, display_name=name, score=score, trophies=trophies,
                )
                break

    last_updated = session.execute(
        select(func.max(PlayerStats.last_fetched_at))
        .where(PlayerStats.set_id == magic_set.id)
    ).scalar()

    drafter_count = session.execute(
        select(func.count(func.distinct(PlayerStats.player_id)))
        .join(Player, Player.id == PlayerStats.player_id)
        .where(
            PlayerStats.set_id == magic_set.id,
            PlayerStats.events > 0,
            Player.active.is_(True),
            Player.leaderboard_opt_in.is_(True),
        )
    ).scalar() or 0

    return LeaderboardData(
        set_code=magic_set.code,
        set_name=magic_set.name,
        top=top,
        viewer=viewer_entry,
        last_updated=last_updated,
        drafter_count=drafter_count,
    )


def process_leaderboard_for_format(
    session: Session, viewer_discord_id: str | None, format_label: str, top_n: int = 10,
) -> LeaderboardData | None:
    """Per-format leaderboard: ranks each player by their score contribution
    in the named queue group (Premier, Quick, Sealed, etc.).
    """
    magic_set = _current_set(session)
    if magic_set is None:
        return None

    group = next((g for g in DEFAULT_QUEUE_GROUPS if g.label == format_label), None)
    if group is None:
        return None

    rows = session.execute(
        select(
            Player.id, Player.slug, Player.display_name, Player.discord_id,
            PlayerStats.format, PlayerStats.events, PlayerStats.wins,
            PlayerStats.losses, PlayerStats.trophies,
        )
        .join(PlayerStats, PlayerStats.player_id == Player.id)
        .where(
            Player.active.is_(True),
            Player.leaderboard_opt_in.is_(True),
            PlayerStats.set_id == magic_set.id,
            PlayerStats.format.in_(group.formats),
        )
    ).all()

    bucket: dict[str, dict] = {}
    for r in rows:
        b = bucket.setdefault(r.id, {
            "slug": r.slug, "display_name": r.display_name, "discord_id": r.discord_id,
            "stats": [], "trophies": 0,
        })
        b["stats"].append({
            "format": r.format, "events": int(r.events or 0),
            "wins": int(r.wins or 0), "losses": int(r.losses or 0),
            "trophies": int(r.trophies or 0),
        })
        b["trophies"] += int(r.trophies or 0)

    scored: list[tuple[float, int, str, str, str, str | None]] = []
    for pid, b in bucket.items():
        score = compute_score(b["stats"], groups=(group,))
        if score <= 0:
            continue
        scored.append((score, b["trophies"], pid, b["slug"], b["display_name"], b["discord_id"]))

    scored.sort(key=lambda x: (-x[0], x[4].lower()))

    ranked = [
        (idx + 1, pid, slug, name, did, score, trophies)
        for idx, (score, trophies, pid, slug, name, did) in enumerate(scored)
    ]
    top = [
        LeaderboardEntry(rank=rank, player_id=pid, slug=slug, display_name=name, score=score, trophies=trophies)
        for rank, pid, slug, name, _did, score, trophies in ranked[:top_n]
    ]
    viewer_entry: LeaderboardEntry | None = None
    if viewer_discord_id is not None:
        for rank, pid, slug, name, did, score, trophies in ranked:
            if did == viewer_discord_id:
                viewer_entry = LeaderboardEntry(
                    rank=rank, player_id=pid, slug=slug, display_name=name, score=score, trophies=trophies,
                )
                break

    last_updated = session.execute(
        select(func.max(PlayerStats.last_fetched_at))
        .where(PlayerStats.set_id == magic_set.id)
    ).scalar()

    return LeaderboardData(
        set_code=magic_set.code,
        set_name=magic_set.name,
        top=top,
        viewer=viewer_entry,
        last_updated=last_updated,
        drafter_count=len(scored),
    )


def process_leaderboard_for_archetype(
    session: Session, viewer_discord_id: str | None, archetype: str, top_n: int = 10,
) -> LeaderboardData | None:
    """Per-archetype (color combo) leaderboard. Aggregates from draft_events,
    filtering by archetype, then runs compute_score per player.
    """
    magic_set = _current_set(session)
    if magic_set is None:
        return None

    events = session.execute(
        select(
            Player.id, Player.slug, Player.display_name, Player.discord_id,
            DraftEvent.format, DraftEvent.colors, DraftEvent.wins, DraftEvent.losses,
            DraftEvent.is_trophy,
        )
        .join(DraftEvent, DraftEvent.player_id == Player.id)
        .where(
            Player.active.is_(True),
            Player.leaderboard_opt_in.is_(True),
            DraftEvent.set_id == magic_set.id,
        )
    ).all()

    bucket: dict[str, dict] = {}
    for r in events:
        if not _archetype_matches(r.colors, archetype):
            continue
        b = bucket.setdefault(r.id, {
            "slug": r.slug, "display_name": r.display_name, "discord_id": r.discord_id,
            "stats_by_format": {}, "trophies": 0,
        })
        f = b["stats_by_format"].setdefault(
            r.format,
            {"format": r.format, "events": 0, "wins": 0, "losses": 0, "trophies": 0},
        )
        f["events"] += 1
        f["wins"] += int(r.wins or 0)
        f["losses"] += int(r.losses or 0)
        if r.is_trophy:
            f["trophies"] += 1
            b["trophies"] += 1

    scored: list[tuple[float, int, str, str, str, str | None]] = []
    for pid, b in bucket.items():
        score = compute_score(list(b["stats_by_format"].values()))
        if score <= 0:
            continue
        scored.append((score, b["trophies"], pid, b["slug"], b["display_name"], b["discord_id"]))

    scored.sort(key=lambda x: (-x[0], x[4].lower()))

    ranked = [
        (idx + 1, pid, slug, name, did, score, trophies)
        for idx, (score, trophies, pid, slug, name, did) in enumerate(scored)
    ]
    top = [
        LeaderboardEntry(rank=rank, player_id=pid, slug=slug, display_name=name, score=score, trophies=trophies)
        for rank, pid, slug, name, _did, score, trophies in ranked[:top_n]
    ]
    viewer_entry: LeaderboardEntry | None = None
    if viewer_discord_id is not None:
        for rank, pid, slug, name, did, score, trophies in ranked:
            if did == viewer_discord_id:
                viewer_entry = LeaderboardEntry(
                    rank=rank, player_id=pid, slug=slug, display_name=name, score=score, trophies=trophies,
                )
                break

    last_updated = session.execute(
        select(func.max(DraftEvent.fetched_at))
        .where(DraftEvent.set_id == magic_set.id)
    ).scalar()

    return LeaderboardData(
        set_code=magic_set.code,
        set_name=magic_set.name,
        top=top,
        viewer=viewer_entry,
        last_updated=last_updated,
        drafter_count=len(scored),
    )


def process_leaderboard_for_direct(
    session: Session, viewer_discord_id: str | None, top_n: int = 10,
) -> LeaderboardData | None:
    """Arena Direct Sealed leaderboard: ranks players by boxes won.

    Box rules live in scoring.boxes_for_event — standard 6/7-win payouts plus
    collector-booster-weekend overrides. Per-event rather than aggregate so the
    date-windowed rule can fire.
    """
    magic_set = _current_set(session)
    if magic_set is None:
        return None

    rows = session.execute(
        select(
            Player.id, Player.slug, Player.display_name, Player.discord_id,
            DraftEvent.wins, DraftEvent.finished_at,
        )
        .join(DraftEvent, DraftEvent.player_id == Player.id)
        .where(
            Player.active.is_(True),
            Player.leaderboard_opt_in.is_(True),
            DraftEvent.set_id == magic_set.id,
            DraftEvent.format == "ArenaDirect_Sealed",
        )
    ).all()

    bucket: dict[str, dict] = {}
    for r in rows:
        b = bucket.setdefault(r.id, {
            "slug": r.slug, "display_name": r.display_name, "discord_id": r.discord_id,
            "boxes": 0, "trophies": 0,
        })
        wins = int(r.wins or 0)
        b["boxes"] += boxes_for_event(magic_set.code, wins, r.finished_at)
        if wins == 7:
            b["trophies"] += 1

    scored = [
        (b["boxes"], b["trophies"], pid, b["slug"], b["display_name"], b["discord_id"])
        for pid, b in bucket.items()
        if b["boxes"] > 0
    ]
    scored.sort(key=lambda x: (-x[0], -x[1], x[4].lower()))

    ranked = [
        (idx + 1, pid, slug, name, did, boxes, trophies)
        for idx, (boxes, trophies, pid, slug, name, did) in enumerate(scored)
    ]
    top = [
        LeaderboardEntry(rank=rank, player_id=pid, slug=slug, display_name=name, score=float(boxes), trophies=trophies, events=boxes)
        for rank, pid, slug, name, _did, boxes, trophies in ranked[:top_n]
    ]
    viewer_entry: LeaderboardEntry | None = None
    if viewer_discord_id is not None:
        for rank, pid, slug, name, did, boxes, trophies in ranked:
            if did == viewer_discord_id:
                viewer_entry = LeaderboardEntry(
                    rank=rank, player_id=pid, slug=slug, display_name=name,
                    score=float(boxes), trophies=trophies, events=boxes,
                )
                break

    last_updated = session.execute(
        select(func.max(DraftEvent.fetched_at))
        .where(DraftEvent.set_id == magic_set.id, DraftEvent.format == "ArenaDirect_Sealed")
    ).scalar()

    return LeaderboardData(
        set_code=magic_set.code,
        set_name=magic_set.name,
        top=top,
        viewer=viewer_entry,
        last_updated=last_updated,
        drafter_count=len(scored),
        show_score=False,
    )


def process_leaderboard_for_pod(
    session: Session, viewer_discord_id: str | None, top_n: int = 10,
) -> LeaderboardData | None:
    """Pod-draft leaderboard for the active set: ranked by trophies, no score column."""
    magic_set = _current_set(session)
    if magic_set is None:
        return None

    trophy_expr = func.coalesce(func.sum(case((PodDraftParticipant.placement == 1, 1), else_=0)), 0)
    events_expr = func.count(PodDraftParticipant.id)

    rows = session.execute(
        select(
            Player.id, Player.slug, Player.display_name, Player.discord_id,
            trophy_expr.label("trophies"),
            events_expr.label("events"),
        )
        .join(PodDraftParticipant, PodDraftParticipant.player_id == Player.id)
        .join(PodDraftEvent, PodDraftEvent.id == PodDraftParticipant.event_id)
        .where(
            Player.active.is_(True),
            PodDraftParticipant.placement.is_not(None),
            func.upper(PodDraftEvent.set_code) == magic_set.code.upper(),
        )
        .group_by(Player.id, Player.slug, Player.display_name, Player.discord_id)
        .order_by(trophy_expr.desc(), events_expr.desc(), Player.display_name.asc())
    ).all()

    ranked = [
        (idx + 1, r.id, r.slug, r.display_name, r.discord_id, int(r.trophies), int(r.events))
        for idx, r in enumerate(rows)
    ]
    top = [
        LeaderboardEntry(rank=rank, player_id=pid, slug=slug, display_name=name, score=float(trophies), trophies=trophies, events=events)
        for rank, pid, slug, name, _did, trophies, events in ranked[:top_n]
    ]
    viewer_entry: LeaderboardEntry | None = None
    if viewer_discord_id is not None:
        for rank, pid, slug, name, did, trophies, events in ranked:
            if did == viewer_discord_id:
                viewer_entry = LeaderboardEntry(rank=rank, player_id=pid, slug=slug, display_name=name, score=float(trophies), trophies=trophies, events=events)
                break

    last_updated = session.execute(
        select(func.max(PodDraftEvent.event_time))
        .where(
            func.upper(PodDraftEvent.set_code) == magic_set.code.upper(),
            PodDraftEvent.event_time <= func.now(),
        )
    ).scalar()

    return LeaderboardData(
        set_code=magic_set.code,
        set_name=magic_set.name,
        top=top,
        viewer=viewer_entry,
        last_updated=last_updated,
        drafter_count=0,
        show_score=False,
    )


MEDAL_EMOJIS = {1: "🥇", 2: "🥈", 3: "🥉"}

_CYCLE: list[tuple[str | None, str | None]] = [
    (None, None),
    ("format", "Premier"),
    ("format", "Trad"),
    ("format", "Pod"),
    ("format", "Direct"),
]
_CYCLE_DISPLAY = ["All", "Premier", "Trad", "Pod", "Direct"]
_CYCLE_LABELS = [f"{_CYCLE_DISPLAY[(i + 1) % len(_CYCLE_DISPLAY)]} ▶️" for i in range(len(_CYCLE_DISPLAY))]


def _cycle_label_for(filter_type: str | None, filter_value: str | None) -> str:
    key = (filter_type, filter_value)
    for i, c in enumerate(_CYCLE):
        if c == key:
            return _CYCLE_LABELS[i]
    return _CYCLE_LABELS[0]


class _CycleButton(discord.ui.Button):
    def __init__(self, label: str) -> None:
        super().__init__(label=label, style=discord.ButtonStyle.primary, custom_id="leaderboard:cycle")

    async def callback(self, interaction: discord.Interaction) -> None:
        msg_id = str(interaction.message.id)
        with SessionLocal() as session:
            tracked = session.execute(
                select(LeaderboardMessage).where(LeaderboardMessage.message_id == msg_id)
            ).scalar_one_or_none()
            if tracked is None:
                await interaction.response.send_message(
                    "Post a fresh leaderboard with /leaderboard to enable cycling.",
                    ephemeral=True,
                )
                return
            key = (tracked.filter_type, tracked.filter_value)
            try:
                idx = next(i for i, c in enumerate(_CYCLE) if c == key)
            except StopIteration:
                idx = 0
            next_idx = (idx + 1) % len(_CYCLE)
            next_ft, next_fv = _CYCLE[next_idx]
            next_label = _CYCLE_LABELS[next_idx]
            data, suffix = render_filtered_data(
                session, filter_type=next_ft, filter_value=next_fv, viewer_discord_id=None,
            )
            tracked.filter_type = next_ft
            tracked.filter_value = next_fv
            session.commit()

        if data is None:
            await interaction.response.send_message("Could not render leaderboard.", ephemeral=True)
            return
        embed = render_public_embed(data)
        if suffix:
            embed.title = f"{embed.title} · {suffix}"
        await interaction.response.edit_message(
            embed=embed,
            view=render_view(cycle_label=next_label, filter_type=next_ft, filter_value=next_fv),
        )

DISCORD_EMBED_DESC_LIMIT = 4096


def _player_url(slug: str, set_code: str | None = None, filter_type: str | None = None, filter_value: str | None = None) -> str:
    base = settings.public_site_url.rstrip("/")
    url = f"{base}/{set_code}/player/{slug}" if set_code else f"{base}/player/{slug}"
    if filter_type == "format" and filter_value:
        url += f"?format={filter_value}"
    return url


def _format_leaderboard(top: list[LeaderboardEntry], set_code: str | None = None, show_score: bool = True, filter_type: str | None = None, filter_value: str | None = None) -> str:
    """Wrap each row in inline code (single backticks) — renders as monospace
    without the code-block brick, and spaces are preserved so columns align.
    Same trick scoreboards.dev uses to get tabular layout in an embed.

    Scores are rounded to the nearest integer for display; tie-breaking still
    works because the underlying ORDER BY in process_leaderboard uses the raw
    float value, not this rendered string.
    """
    name_width = max(max(_display_width(e.display_name) for e in top), len("Name"))
    rank_col_width = max(max(len(f"{e.rank}.") for e in top), len("#"))

    if show_score:
        score_width = max(max(len(f"{round(e.score)}") for e in top), len("Points"))
        trophy_width = max(max(len(str(e.trophies)) for e in top), 1)
        # Trophy header emoji renders ~1 col wider than a digit, so pad header trophy field one less
        header_trophy_width = max(trophy_width - 1, 1)
        header_inner = (
            f"{'#':<{rank_col_width}} {'Name':<{name_width}}  "
            f"{'Points':>{score_width}}  {'🏆':>{header_trophy_width}}"
        )
    else:
        is_direct = filter_type == "format" and filter_value == "Direct"
        left_label = "📦" if is_direct else "Drafts"
        drafts_width = max(max(len(str(e.events)) for e in top), 2 if is_direct else len(left_label))
        # min 2 so single-digit trophies align under the emoji header
        trophy_width = max(max(len(str(e.trophies)) for e in top), 2)
        header_trophy_width = trophy_width - 1
        header_left_width = drafts_width - 1 if is_direct else drafts_width
        header_inner = (
            f"{'#':<{rank_col_width}} {'Name':<{name_width}}   "
            f"{left_label:>{header_left_width}}  {'🏆':>{header_trophy_width}}"
        )

    lines = [f"`{header_inner}`"]
    for e in top:
        medal = MEDAL_EMOJIS.get(e.rank)
        if medal is not None:
            # emoji takes ~1 col more than digit-pair in monospace rendering, so pad shorter
            rank = f"{medal:<{rank_col_width - 1}}"
        else:
            rank = f"{e.rank}.".ljust(rank_col_width)
        name = e.display_name + " " * max(0, name_width - _display_width(e.display_name))
        trophy = f"{e.trophies:>{trophy_width}}"
        if show_score:
            # Center the integer under the wider 'Points' header — right-bias so
            # single-digit values shift one space rightward and look more centered
            score = _center_right_bias(str(round(e.score)), score_width)
            inner = f"{rank} {name}  {score}  {trophy}"
        else:
            drafts_col = _center_right_bias(str(e.events), drafts_width)
            inner = f"{rank} {name}   {drafts_col}  {trophy}"
        lines.append(f"[`{inner}`](<{_player_url(e.slug, set_code, filter_type, filter_value)}>)")
    return "\n".join(lines)


def _display_width(s: str) -> int:
    """Monospace column width, counting emoji and wide CJK glyphs as 2 cells where len() counts 1."""
    return sum(2 if unicodedata.east_asian_width(ch) == "W" else 1 for ch in s)


def _center_right_bias(s: str, width: int) -> str:
    """Center s in width chars, putting any leftover padding on the LEFT.

    Python's built-in centering biases right (extra space ends up on the right),
    which makes single-digit values inside wider header columns look offset to
    the left. Right-biasing the padding shifts those values one space rightward
    so they read closer to the column's visual center.
    """
    pad = max(0, width - len(s))
    right = pad // 2
    left = pad - right
    return ' ' * left + s + ' ' * right


def _apply_footer(embed: discord.Embed, data: LeaderboardData) -> None:
    """Two-line footer:

      Row 1: ``N active drafters``
      Row 2: ``Last updated | Today at HH:MM``  (timestamp appended by Discord)

    The clickable site link is on the embed title (via ``embed.url``); the URL
    no longer appears in the footer to avoid redundancy.
    """
    rows: list[str] = []
    if data.drafter_count > 0:
        label = "player" if data.drafter_count == 1 else "players"
        rows.append(f"{data.drafter_count} {label} sharing their drafts · /join to add yours")
    if data.last_updated is not None:
        embed.timestamp = data.last_updated
        rows.append("Last updated")
    if rows:
        embed.set_footer(text="\n".join(rows))


def render_embed(data: LeaderboardData) -> discord.Embed:
    base_url = settings.public_site_url.rstrip("/")
    if data.filter_type == "format" and data.filter_value:
        site_url = f"{base_url}?format={data.filter_value}"
    else:
        site_url = base_url
    embed = discord.Embed(
        title=f"🏆 Leaderboard — {data.set_code}",
        url=site_url,
        color=discord.Color.gold(),
    )
    if not data.top:
        embed.description = "_No players have scored yet for this set._"
    else:
        embed.description = _format_leaderboard(
            data.top, data.set_code, show_score=data.show_score,
            filter_type=data.filter_type, filter_value=data.filter_value,
        )
    _apply_footer(embed, data)
    return embed


# Alias kept so external callers asking for the 'public' variant still resolve;
# the personalized variant retired when stats embed took over the per-viewer info
render_public_embed = render_embed


async def _send_personal_followup(
    interaction: discord.Interaction, viewer_discord_id: str, viewer_registered: bool,
) -> None:
    """Ephemeral follow-up to the invoker — rich stats breakdown if signed up,
    /join prompt otherwise. Re-uses the /stats embed so the two commands stay
    visually consistent."""
    if not viewer_registered:
        await interaction.followup.send(
            content="You're not on the leaderboard — run `/join` to join.",
            ephemeral=(interaction.guild is not None),
        )
        return
    with SessionLocal() as session:
        stats_data = process_stats(session, player_name=None, viewer_discord_id=viewer_discord_id)
    if stats_data is not None:
        await interaction.followup.send(embed=render_stats_embed(stats_data), ephemeral=(interaction.guild is not None))


class LeaderboardView(discord.ui.View):
    """Persistent view for leaderboard messages — buttons keep working across bot restarts.

    The Join button calls back into the Signup cog so it behaves identically to the
    /join slash command (DM-flow signup, reactivation, already-signed-up handling).
    The Stats button is a URL link handled client-side by Discord.
    """

    def __init__(
        self,
        cycle_label: str = _CYCLE_LABELS[0],
        filter_type: str | None = None,
        filter_value: str | None = None,
    ) -> None:
        super().__init__(timeout=None)
        self.add_item(_CycleButton(label=cycle_label))
        stats_url = settings.public_site_url
        if filter_type == "format" and filter_value:
            stats_url = f"{stats_url.rstrip('/')}?format={filter_value}"
        # URL buttons are exempt from the persistent-view custom_id requirement
        self.add_item(discord.ui.Button(
            label="Stats", url=stats_url,
            style=discord.ButtonStyle.link,
            emoji=emojis.get_emoji("llu"),
        ))

    @discord.ui.button(label="Join", style=discord.ButtonStyle.success, custom_id="leaderboard:join")
    async def join_button(self, interaction: discord.Interaction, button: discord.ui.Button) -> None:
        # Already signed-up users clicking Join are usually misclicks or curious
        # — show their personal stats instead of starting the signup flow
        user_id = str(interaction.user.id)
        with SessionLocal() as session:
            existing = session.execute(
                select(Player).where(
                    Player.discord_id == user_id, Player.active.is_(True),
                )
            ).scalar_one_or_none()

        if existing is not None:
            stats_cog = interaction.client.get_cog("Stats")
            if stats_cog is not None:
                await stats_cog.stats.callback(stats_cog, interaction)
                return

        signup_cog = interaction.client.get_cog("Signup")
        if signup_cog is None:
            await interaction.response.send_message(
                "Sign-up isn't available right now.", ephemeral=(interaction.guild is not None),
            )
            return
        await signup_cog.signup.callback(signup_cog, interaction)


def render_view(
    cycle_label: str = _CYCLE_LABELS[0],
    filter_type: str | None = None,
    filter_value: str | None = None,
) -> discord.ui.View:
    return LeaderboardView(cycle_label=cycle_label, filter_type=filter_type, filter_value=filter_value)


CODE_TO_COLOR_LABEL: dict[str, str] = {code: label for label, code in COLOR_CHOICES.items()}


def _drafter_count(session: Session) -> int:
    magic_set = _current_set(session)
    if magic_set is None:
        return 0
    return session.execute(
        select(func.count(func.distinct(PlayerStats.player_id)))
        .join(Player, Player.id == PlayerStats.player_id)
        .where(
            PlayerStats.set_id == magic_set.id,
            PlayerStats.events > 0,
            Player.active.is_(True),
            Player.leaderboard_opt_in.is_(True),
        )
    ).scalar() or 0


def render_filtered_data(
    session: Session,
    *,
    filter_type: str | None,
    filter_value: str | None,
    viewer_discord_id: str | None,
) -> tuple["LeaderboardData | None", str | None]:
    """Resolve a filter into the matching processor + display suffix.

    Returns (data, suffix). suffix is the human label appended to the embed
    title (e.g. "Premier", "Boros"). Both are None when no active set exists.
    """
    if filter_type == "format" and filter_value == "Pod":
        data = process_leaderboard_for_pod(session, viewer_discord_id=viewer_discord_id)
        suffix = "Pod"
    elif filter_type == "format" and filter_value == "Direct":
        data = process_leaderboard_for_direct(session, viewer_discord_id=viewer_discord_id)
        suffix = "Direct"
    elif filter_type == "format":
        assert filter_value is not None
        data = process_leaderboard_for_format(
            session, viewer_discord_id=viewer_discord_id, format_label=filter_value,
        )
        suffix = filter_value
    elif filter_type == "color":
        assert filter_value is not None
        data = process_leaderboard_for_archetype(
            session, viewer_discord_id=viewer_discord_id, archetype=filter_value,
        )
        suffix = CODE_TO_COLOR_LABEL.get(filter_value, filter_value)
    else:
        data = process_leaderboard(session, viewer_discord_id=viewer_discord_id)
        suffix = None

    if data is not None:
        data.drafter_count = _drafter_count(session)
        data.filter_type = filter_type
        data.filter_value = filter_value

    return data, suffix


def _filter_clause(filter_type: str | None, filter_value: str | None):
    """Postgres `IS NULL` vs `=` differ; build the right one for nullable filters."""
    type_clause = (
        LeaderboardMessage.filter_type.is_(None) if filter_type is None
        else LeaderboardMessage.filter_type == filter_type
    )
    value_clause = (
        LeaderboardMessage.filter_value.is_(None) if filter_value is None
        else LeaderboardMessage.filter_value == filter_value
    )
    return type_clause, value_clause


async def _replace_tracked_message(
    interaction: discord.Interaction,
    channel_id: str,
    set_id: str,
    embed: discord.Embed,
    view: discord.ui.View,
    filter_type: str | None = None,
    filter_value: str | None = None,
) -> None:
    """Post a fresh leaderboard and reconcile prior tracked messages with the
    same (channel, set, filter_type, filter_value).

    For each matching prior row:
      - if the message is pinned, leave the message and keep the tracking row
        so !refresh continues to edit it in place.
      - otherwise delete the message and drop the tracking row.

    The freshly-posted message gets its own tracking row carrying the filter
    so refresh can re-render it with the correct data later.

    A NotFound on fetch is normal (mod or user wiped it); we drop the row.
    """
    sent = await interaction.followup.send(embed=embed, view=view, wait=True)
    new_message_id = str(sent.id)

    type_clause, value_clause = _filter_clause(filter_type, filter_value)

    with SessionLocal() as session:
        prior_rows = session.execute(
            select(LeaderboardMessage).where(
                LeaderboardMessage.channel_id == channel_id,
                LeaderboardMessage.set_id == set_id,
                type_clause,
                value_clause,
            )
        ).scalars().all()
        prior_targets = [(row.id, row.message_id) for row in prior_rows]

        session.add(LeaderboardMessage(
            channel_id=channel_id, set_id=set_id, message_id=new_message_id,
            filter_type=filter_type, filter_value=filter_value,
        ))
        session.commit()

    for row_id, prior_message_id in prior_targets:
        if prior_message_id == new_message_id:
            continue
        keep_row = False
        try:
            old = await interaction.channel.fetch_message(int(prior_message_id))
            if old.pinned:
                logger.info(f"prior leaderboard message {prior_message_id} is pinned, leaving in place")
                keep_row = True
            else:
                await old.delete()
        except discord.NotFound:
            pass
        except discord.HTTPException as e:
            logger.warning(f"could not delete prior leaderboard message {prior_message_id}: {e}")
            keep_row = True

        if not keep_row:
            with SessionLocal() as session:
                stale = session.get(LeaderboardMessage, row_id)
                if stale is not None:
                    session.delete(stale)
                    session.commit()


async def broadcast_current_set_update(bot: commands.Bot) -> dict:
    """Re-render every tracked leaderboard message for the currently active set.

    Wrapper used by callers (signup flow, !refresh) that just want 'reflect the
    latest data everywhere' without resolving the set themselves.
    """
    with SessionLocal() as session:
        ms = session.execute(
            select(MagicSet).where(MagicSet.code == ACTIVE_SET_CODE)
        ).scalar_one_or_none()
        if ms is None:
            return {"edited": 0, "pruned": 0}
        return await edit_tracked_messages_for_set(bot, ms)


async def edit_tracked_messages_for_set(bot: commands.Bot, magic_set: MagicSet) -> dict:
    """Refresh the rendered embed of every tracked leaderboard message for ``magic_set``.

    Used by ``!refresh`` (and any future periodic job) to keep posted leaderboards
    live without requiring users to re-invoke ``/leaderboard``. Stale tracking
    rows (message deleted in Discord) get pruned automatically.
    """
    summary = {"edited": 0, "pruned": 0}
    with SessionLocal() as session:
        rows = session.execute(
            select(LeaderboardMessage).where(LeaderboardMessage.set_id == magic_set.id)
        ).scalars().all()
        targets = [
            (r.id, r.channel_id, r.message_id, r.filter_type, r.filter_value)
            for r in rows
        ]

    if not targets:
        return summary

    rendered_cache: dict[tuple[str | None, str | None], discord.Embed | None] = {}

    def _render_for(filter_type: str | None, filter_value: str | None) -> discord.Embed | None:
        key = (filter_type, filter_value)
        if key in rendered_cache:
            return rendered_cache[key]
        with SessionLocal() as session:
            data, suffix = render_filtered_data(
                session, filter_type=filter_type, filter_value=filter_value, viewer_discord_id=None,
            )
        if data is None:
            rendered_cache[key] = None
            return None
        embed = render_public_embed(data)
        if suffix:
            embed.title = f"{embed.title} · {suffix}"
        rendered_cache[key] = embed
        return embed

    for row_id, channel_id, message_id, filter_type, filter_value in targets:
        embed = _render_for(filter_type, filter_value)
        if embed is None:
            continue
        try:
            channel = bot.get_channel(int(channel_id)) or await bot.fetch_channel(int(channel_id))
            msg = await channel.fetch_message(int(message_id))
            # Pass content=None to strip any prior message-content variant (transient format)
            await msg.edit(content=None, embed=embed, view=render_view(
                cycle_label=_cycle_label_for(filter_type, filter_value),
                filter_type=filter_type, filter_value=filter_value,
            ))
            with SessionLocal() as session:
                tracked = session.get(LeaderboardMessage, row_id)
                if tracked is not None:
                    tracked.last_rendered_at = datetime.now(timezone.utc)
                    session.commit()
            summary["edited"] += 1
        except discord.NotFound:
            with SessionLocal() as session:
                tracked = session.get(LeaderboardMessage, row_id)
                if tracked is not None:
                    session.delete(tracked)
                    session.commit()
            summary["pruned"] += 1
        except discord.HTTPException as e:
            logger.warning(f"pruning leaderboard message {message_id} in channel {channel_id} after edit failure: {e}")
            with SessionLocal() as session:
                tracked = session.get(LeaderboardMessage, row_id)
                if tracked is not None:
                    session.delete(tracked)
                    session.commit()
            summary["pruned"] += 1
    return summary


class Leaderboard(commands.Cog):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

    @app_commands.command(name="leaderboard", description="Show the current set leaderboard")
    @app_commands.describe(
        format="Show only one queue (Premier, Quick, Sealed, Traditional)",
        color="Filter by archetype: guilds, shards/wedges, or Soup (4+ colors)",
    )
    @app_commands.choices(
        format=[
            app_commands.Choice(name="Premier",     value="Premier"),
            app_commands.Choice(name="Traditional", value="Trad"),
            app_commands.Choice(name="Sealed",      value="Sealed"),
            app_commands.Choice(name="Quick",       value="Quick"),
            app_commands.Choice(name="Pod",         value="Pod"),
            app_commands.Choice(name="Direct",      value="Direct"),
        ],
        color=[
            app_commands.Choice(name=label, value=code)
            for label, code in COLOR_CHOICES.items()
        ],
    )
    @app_commands.allowed_contexts(guilds=True, dms=True, private_channels=False)
    @app_commands.allowed_installs(guilds=True, users=False)
    async def leaderboard(
        self,
        interaction: discord.Interaction,
        format: app_commands.Choice[str] | None = None,
        color: app_commands.Choice[str] | None = None,
    ) -> None:
        user_id = str(interaction.user.id)
        audit.event(
            "leaderboard_invoked",
            user_id=user_id,
            format=format.value if format else None,
            color=color.value if color else None,
        )

        if format is not None and color is not None:
            await interaction.response.send_message(
                "Pick one filter — `format` or `color`, not both.",
                ephemeral=(interaction.guild is not None),
            )
            return

        in_guild = interaction.guild is not None
        ephemeral = in_guild

        if format is not None:
            filter_type, filter_value = "format", format.value
        elif color is not None:
            filter_type, filter_value = "color", color.value
        else:
            filter_type, filter_value = None, None

        with SessionLocal() as session:
            data, suffix = render_filtered_data(
                session,
                filter_type=filter_type, filter_value=filter_value,
                viewer_discord_id=user_id,
            )
            magic_set = _current_set(session)

        if data is None or magic_set is None:
            await interaction.response.send_message(
                "No active set is configured. `bot/sets.py::ACTIVE_SET_CODE` doesn't match any registered set.",
                ephemeral=ephemeral,
            )
            return

        embed = render_public_embed(data)
        if suffix:
            embed.title = f"{embed.title} · {suffix}"

        # In a guild channel: track the post (filter-aware) so !refresh keeps it
        # current. In a DM: single response, fully personalized.
        if in_guild:
            await interaction.response.defer()
            await _replace_tracked_message(
                interaction,
                channel_id=str(interaction.channel_id),
                set_id=magic_set.id,
                embed=embed,
                view=render_view(
                    cycle_label=_cycle_label_for(filter_type, filter_value),
                    filter_type=filter_type, filter_value=filter_value,
                ),
                filter_type=filter_type,
                filter_value=filter_value,
            )
            if filter_type is None:
                await _send_personal_followup(
                    interaction,
                    viewer_discord_id=user_id,
                    viewer_registered=data.viewer is not None,
                )
        else:
            # In DM: send the (already filter-aware) embed as the interaction response,
            # then the stats embed (or /join prompt) via dm.send so it doesn't visually
            # thread as a reply under the leaderboard message. Personal followup only
            # makes sense for the unfiltered overall leaderboard.
            await interaction.response.send_message(
                embed=embed,
                view=render_view(
                    cycle_label=_cycle_label_for(filter_type, filter_value),
                    filter_type=filter_type, filter_value=filter_value,
                ),
            )
            if filter_type is not None:
                return
            try:
                dm = interaction.channel  # already a DM channel here
                if data.viewer is not None:
                    with SessionLocal() as session:
                        stats_data = process_stats(session, player_name=None, viewer_discord_id=user_id)
                    if stats_data is not None:
                        await dm.send(embed=render_stats_embed(stats_data))
                else:
                    await dm.send("You're not on the leaderboard — run `/join` to join.")
            except Exception:
                logger.warning("/leaderboard DM personal followup failed", exc_info=True)

    @app_commands.command(
        name="leaderboard-full",
        description="DM you the entire leaderboard",
    )
    @app_commands.allowed_contexts(guilds=False, dms=True, private_channels=False)
    @app_commands.allowed_installs(guilds=True, users=False)
    async def leaderboard_full(self, interaction: discord.Interaction) -> None:
        user_id = str(interaction.user.id)
        audit.event("leaderboard_full_invoked", user_id=user_id)

        with SessionLocal() as session:
            data = process_leaderboard(
                session, viewer_discord_id=user_id,
                top_n=10**6, include_zero_scores=True,
            )

        if data is None:
            await interaction.response.send_message(
                "No active set is configured. `bot/sets.py::ACTIVE_SET_CODE` doesn't match any registered set.",
                ephemeral=(interaction.guild is not None),
            )
            return

        embed = render_embed(data)
        site_link = f"Check the full leaderboard at {settings.public_site_url} 🚀"
        if data.top and embed.description and len(embed.description) > DISCORD_EMBED_DESC_LIMIT:
            trimmed = list(data.top)
            while trimmed:
                body = _format_leaderboard(trimmed, data.set_code, filter_type=data.filter_type, filter_value=data.filter_value)
                if len(body) + 2 + len(site_link) <= DISCORD_EMBED_DESC_LIMIT:
                    break
                trimmed.pop()
            body = _format_leaderboard(trimmed, data.set_code, filter_type=data.filter_type, filter_value=data.filter_value) if trimmed else ""
            embed.description = f"{body}\n\n{site_link}" if body else site_link

        # Always deliver via DM, regardless of where the slash was invoked.
        # `allowed_contexts` only governs visibility, not response routing
        try:
            dm = await interaction.user.create_dm()
            await dm.send(embed=embed, view=render_view())
        except discord.Forbidden:
            await interaction.response.send_message(
                "Couldn't deliver the full leaderboard — open DMs from this server and try again.",
                ephemeral=(interaction.guild is not None),
            )
            return

        await interaction.response.send_message(
            "Full leaderboard sent to your DMs.",
            ephemeral=(interaction.guild is not None),
        )


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(Leaderboard(bot))


def _current_set(session: Session) -> MagicSet | None:
    return session.execute(
        select(MagicSet).where(MagicSet.code == ACTIVE_SET_CODE)
    ).scalar_one_or_none()


_WUBRG = "WUBRG"
_MULTI_ARCHETYPE = "MULTI"


def _normalize_archetype(colors: str | None) -> str:
    if not colors:
        return ""
    return "".join(sorted((c for c in colors if c.isupper()), key=_WUBRG.index))


def _effective_color_count(colors: str | None) -> int:
    if not colors:
        return 0
    return len({c.upper() for c in colors if c.upper() in _WUBRG})


def _archetype_matches(colors: str | None, archetype: str) -> bool:
    if archetype == _MULTI_ARCHETYPE:
        return _effective_color_count(colors) >= 4
    return _normalize_archetype(colors) == archetype
