"""Admin-only `/preview-season-awards` — awards ceremony for a set's preview season.

Scans every channel whose name contains "preview-season" for image posts inside the
set's preview window, tallies emoji reactions, and posts a Components V2 ceremony:
one award per reaction category plus a hype meter of fire vs trash sentiment.

Presentation is fully decoupled from data: `build_awards_view` renders an
`AwardsData`, so `!testawards` can feed fixture data through the same builder.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta
from zoneinfo import ZoneInfo

import discord
from discord import app_commands, ui
from discord.ext import commands

from bot import audit
from bot.commands import descriptions as desc
from bot.discord_helpers import NBSP, ZWSP, first_image_url
from bot.sets import PREVIEW_WINDOWS, PreviewWindow

log = logging.getLogger(__name__)

COMMUNITY_TZ = ZoneInfo("America/New_York")

FIRE = "🔥"
WASTEBASKET = "🗑"
WILTED_ROSE = "🥀"
JOY = "😂"
EYES = "👀"
CORE_EMOJIS = (FIRE, WASTEBASKET, WILTED_ROSE, JOY, EYES)
EMOJI_DISPLAY = {WASTEBASKET: "🗑️"}

GAP = NBSP * 2
SUBTEXT_START = f"-# {ZWSP}"

HYPE_BAR_SLOTS = 10
CAPTION_MAX_CHARS = 100
FLAVOR_EXTRA_RECOUNTS = 2

MSG_ADMIN_ONLY = "This command is reserved for the bot admin."
MSG_NO_CHANNELS = "No channels with “preview-season” in the name were found in this server."
MSG_NO_POSTS = "No image posts found between {start} and {end} — nothing to award."
MSG_NO_REACTIONS = "Found {count} image posts but no reactions to score."
MSG_POSTED = "🏆 Awards posted — {awards} prizes handed out across {posts} posts."


@dataclass(frozen=True)
class AwardWinner:
    jump_url: str
    image_url: str
    recounts: tuple[tuple[str, int], ...]
    caption: str | None = None


@dataclass(frozen=True)
class AwardsData:
    set_code: str
    window_label: str
    channel_label: str
    hottest: AwardWinner | None
    trash: AwardWinner | None
    comedy: AwardWinner | None
    surprise: AwardWinner | None
    flavor: AwardWinner | None
    totals: tuple[tuple[str, int], ...]
    hot_pct: int | None

    @property
    def award_count(self) -> int:
        winners = (self.hottest, self.trash, self.comedy, self.surprise, self.flavor)
        return sum(winner is not None for winner in winners)


@dataclass(frozen=True)
class ScoredPost:
    jump_url: str
    image_url: str
    content: str
    created_at: datetime
    reactions: dict[str, int]


def build_awards_view(data: AwardsData) -> ui.LayoutView:
    view = ui.LayoutView()
    container = ui.Container(accent_colour=discord.Color.green())

    container.add_item(ui.TextDisplay(
        f"## 🏆 {data.set_code} Preview Season Awards\n"
        f"{SUBTEXT_START}{data.window_label}{GAP}{data.channel_label}"
    ))
    container.add_item(ui.Separator(visible=True, spacing=discord.SeparatorSpacing.small))

    rows = (
        ("### 🔥 Windmill Slam", "Certified Heater", data.hottest),
        ("### 🗑️ Last-Pick Material", "Leave in the Sideboard", data.trash),
        ("### 😂 Comedy Gold", "No Caption Needed", data.comedy),
        ("### 👀 Wait, It Does What?", "Read It Again", data.surprise),
        ("### ⭐ Flavor Win", "Nailed It", data.flavor),
    )
    awarded_rows = [(heading, tagline, winner) for heading, tagline, winner in rows if winner is not None]
    for i, (heading, tagline, winner) in enumerate(awarded_rows):
        container.add_item(ui.Section(
            ui.TextDisplay(_award_text(heading, tagline, winner)),
            accessory=ui.Thumbnail(media=winner.image_url, spoiler=True),
        ))
        if i < len(awarded_rows) - 1:
            container.add_item(ui.Separator(visible=False, spacing=discord.SeparatorSpacing.small))

    if data.hot_pct is not None:
        container.add_item(ui.Separator(visible=True, spacing=discord.SeparatorSpacing.large))
        container.add_item(ui.TextDisplay(_hype_meter_text(data.hot_pct)))

    if data.totals:
        container.add_item(ui.Separator(visible=True, spacing=discord.SeparatorSpacing.small))
        container.add_item(ui.TextDisplay(_footer_text(data.totals)))

    view.add_item(container)
    return view


def _award_text(heading: str, tagline: str, winner: AwardWinner) -> str:
    line = f"_{winner.caption}_" if winner.caption else tagline
    recount = (GAP * 2).join(_emoji_count(emoji, count) for emoji, count in winner.recounts)
    return f"{heading}\n{GAP}[{line}]({winner.jump_url})\n{SUBTEXT_START}{GAP}{recount}"


def _hype_meter_text(hot_pct: int) -> str:
    filled = round(hot_pct * HYPE_BAR_SLOTS / 100)
    bar = "|".join(["🟩"] * filled + ["⬛"] * (HYPE_BAR_SLOTS - filled))
    return f"### 📊 Hype Meter\n{bar}{GAP}**{hot_pct}%**"


def _footer_text(totals: tuple[tuple[str, int], ...]) -> str:
    counts = (GAP * 2).join(_emoji_count(emoji, count) for emoji, count in totals)
    return f"{SUBTEXT_START}Total {counts}"


def _emoji_count(emoji: str, count: int) -> str:
    return f"{EMOJI_DISPLAY.get(emoji, emoji)} {count}"


class PreviewSeasonAwards(commands.Cog):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

    @app_commands.command(name="preview-season-awards", description=desc.PREVIEW_SEASON_AWARDS)
    @app_commands.describe(set="Set Code")
    @app_commands.choices(set=[app_commands.Choice(name=w.set_code, value=w.set_code) for w in PREVIEW_WINDOWS])
    @app_commands.allowed_contexts(guilds=True, dms=False, private_channels=False)
    @app_commands.allowed_installs(guilds=True, users=False)
    async def preview_season_awards(self, interaction: discord.Interaction, set: str) -> None:
        if not await self.bot.is_owner(interaction.user):
            await interaction.response.send_message(MSG_ADMIN_ONLY, ephemeral=True)
            return

        window = next(w for w in PREVIEW_WINDOWS if w.set_code == set)
        channels = [c for c in interaction.guild.text_channels if "preview-season" in c.name]
        if not channels:
            await interaction.response.send_message(MSG_NO_CHANNELS, ephemeral=True)
            return

        await interaction.response.defer(ephemeral=True)
        posts = await _collect_posts(channels, window)
        if not posts:
            await interaction.followup.send(
                MSG_NO_POSTS.format(start=_day_label(window.start_date), end=_day_label(window.end_date)),
                ephemeral=True,
            )
            return

        data = tally_awards(posts, set, _window_label(window), _channel_label(channels))
        if data.award_count == 0:
            await interaction.followup.send(MSG_NO_REACTIONS.format(count=len(posts)), ephemeral=True)
            return

        await interaction.channel.send(view=build_awards_view(data))
        audit.event(
            "preview_season_awards_posted",
            set_code=set,
            posts=len(posts),
            awards=data.award_count,
            channel_id=str(interaction.channel.id),
        )
        log.info(f"preview season awards posted for {set}: {data.award_count} awards from {len(posts)} posts")
        await interaction.followup.send(
            MSG_POSTED.format(awards=data.award_count, posts=len(posts)), ephemeral=True,
        )


def tally_awards(posts: list[ScoredPost], set_code: str, window_label: str, channel_label: str) -> AwardsData:
    totals: dict[str, int] = {}
    for post in posts:
        for emoji in CORE_EMOJIS:
            totals[emoji] = totals.get(emoji, 0) + post.reactions.get(emoji, 0)

    hot_denominator = totals[FIRE] + totals[WASTEBASKET] + totals[WILTED_ROSE]
    hot_pct = round(totals[FIRE] * 100 / hot_denominator) if hot_denominator else None

    return AwardsData(
        set_code=set_code,
        window_label=window_label,
        channel_label=channel_label,
        hottest=_category_winner(posts, (FIRE,)),
        trash=_category_winner(posts, (WASTEBASKET, WILTED_ROSE)),
        comedy=_category_winner(posts, (JOY,), with_caption=True),
        surprise=_category_winner(posts, (EYES,)),
        flavor=_flavor_winner(posts),
        totals=tuple((emoji, count) for emoji, count in totals.items() if count > 0),
        hot_pct=hot_pct,
    )


def _category_winner(
    posts: list[ScoredPost], emojis: tuple[str, ...], with_caption: bool = False,
) -> AwardWinner | None:
    best: ScoredPost | None = None
    best_score = 0
    for post in posts:
        score = sum(post.reactions.get(emoji, 0) for emoji in emojis)
        if score > best_score or (score == best_score and score > 0 and post.created_at < best.created_at):
            best = post
            best_score = score
    if best is None:
        return None
    recounts = tuple((emoji, best.reactions[emoji]) for emoji in emojis if best.reactions.get(emoji, 0) > 0)
    caption = _trim_caption(best.content) if with_caption else None
    return AwardWinner(jump_url=best.jump_url, image_url=best.image_url, recounts=recounts, caption=caption)


def _flavor_winner(posts: list[ScoredPost]) -> AwardWinner | None:
    best: ScoredPost | None = None
    best_emoji = ""
    best_score = 0
    for post in posts:
        for emoji, count in post.reactions.items():
            if emoji in CORE_EMOJIS:
                continue
            if count > best_score or (count == best_score and count > 0 and post.created_at < best.created_at):
                best = post
                best_emoji = emoji
                best_score = count
    if best is None:
        return None
    extras = [(emoji, count) for emoji, count in best.reactions.items() if emoji != best_emoji and count > 0]
    extras.sort(key=lambda item: item[1], reverse=True)
    recounts = ((best_emoji, best_score), *extras[:FLAVOR_EXTRA_RECOUNTS])
    return AwardWinner(jump_url=best.jump_url, image_url=best.image_url, recounts=recounts)


def _trim_caption(content: str) -> str | None:
    caption = " ".join(content.split())
    if not caption:
        return None
    if len(caption) > CAPTION_MAX_CHARS:
        caption = caption[:CAPTION_MAX_CHARS].rstrip() + "…"
    return caption


async def _collect_posts(channels: list[discord.TextChannel], window: PreviewWindow) -> list[ScoredPost]:
    start = datetime.combine(window.start_date, time.min, tzinfo=COMMUNITY_TZ)
    end = datetime.combine(window.end_date + timedelta(days=1), time.min, tzinfo=COMMUNITY_TZ)
    posts: list[ScoredPost] = []
    for channel in channels:
        async for message in channel.history(after=start, before=end, limit=None):
            image_url = first_image_url(message, include_embeds=True)
            if image_url is None:
                continue
            reactions: dict[str, int] = {}
            for reaction in message.reactions:
                key = _normalize_emoji(reaction.emoji)
                reactions[key] = reactions.get(key, 0) + reaction.count
            posts.append(ScoredPost(
                jump_url=message.jump_url,
                image_url=image_url,
                content=message.content,
                created_at=message.created_at,
                reactions=reactions,
            ))
    log.info(f"collected {len(posts)} preview season image posts across {len(channels)} channels")
    return posts


def _normalize_emoji(emoji: discord.PartialEmoji | discord.Emoji | str) -> str:
    return str(emoji).replace("\ufe0f", "")


def _window_label(window: PreviewWindow) -> str:
    if window.start_date.month == window.end_date.month:
        return f"{_day_label(window.start_date)} – {window.end_date.day}"
    return f"{_day_label(window.start_date)} – {_day_label(window.end_date)}"


def _day_label(day: date) -> str:
    return f"{day:%B} {day.day}"


def _channel_label(channels: list[discord.TextChannel]) -> str:
    return " & ".join(f"#{channel.name}" for channel in channels)


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(PreviewSeasonAwards(bot))
