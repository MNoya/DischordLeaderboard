"""Owner-only `!test scribe` — render the event schedule from synthetic fixtures.

Runs the real grouping/partition/render path (bot.services.mtgscribe + event_scribe) on
hand-built events, so the layout can be eyeballed without hitting mtgscribe.com. The fixtures
give one set (Secrets of Strixhaven) several formats with mismatched windows on purpose: events
group by (set, start, end), so formats whose dates differ split into separate lines under
repeated set headers rather than merging into one.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from discord.ext import commands

from bot.commands.event_scribe import build_schedule_payload, process_events
from bot.commands.test_group import test_group
from bot.services import mtgscribe


async def setup(bot: commands.Bot) -> None:
    @test_group.command(name="scribe")
    @commands.is_owner()
    async def test_scribe(ctx: commands.Context) -> None:
        """Owner-only. Render the schedule embed from synthetic events through the real pipeline."""
        in_progress, upcoming = process_events(_fixture_events(datetime.now(timezone.utc)))
        emojis = {emoji.name: emoji for emoji in await ctx.bot.fetch_application_emojis()}
        await ctx.send(**build_schedule_payload(in_progress, upcoming, emojis, scope="Marvel Super Heroes"))


def _fixture_events(now: datetime) -> list:
    in_progress = [
        _scribe_event("Premier Draft", now, -30, 26 / 24),
        _scribe_event("Pick Two", now, -30, 26 / 24),
        _scribe_event("Traditional Draft", now, -30, 26 / 24),
        _scribe_event("Sealed", now, -10, 5),
        _scribe_event("Quick Draft", now, -5, 2),
        _arena_direct("Play Booster Boxes", "play-boosters", now, -2, 4),
    ]
    coming_up = [
        _scribe_event("Premier Draft", now, 33, 40),
        _scribe_event("Pick Two", now, 33, 40),
        _scribe_event("Traditional Draft", now, 33, 40),
        _scribe_event("Premier Draft", now, 9, 16),
        _arena_direct("Play Booster Boxes", "play-boosters", now, 3, 6),
        _arena_direct("Play Booster Boxes", "play-boosters", now, 10, 13),
        _arena_direct("Collector Booster Boxes", "collector-booster", now, 5, 8),
        _arena_direct("Collector Booster Boxes", "collector-booster", now, 17, 20),
        _flashback("Aetherdrift", now, 14, 21),
        _flashback("Duskmourn", now, 21, 28),
        _flashback("Bloomburrow", now, 28, 35),
        _quick_draft("Wilds of Eldraine", now, 4, 11),
        _quick_draft("Outlaws of Thunder Junction", now, 11, 18),
        _quick_draft("The Lost Caverns of Ixalan", now, 43, 49),
        _midweek("Secrets of Strixhaven Phantom Sealed", "Phantom Sealed", ("sealed",), now, 6, 8),
        _cube("Some Kind of new Cube", now, 13, 16),
    ]
    return in_progress + coming_up


def _scribe_event(fmt: str, now: datetime, start_offset_days: int, end_offset_days: int) -> mtgscribe.ScribeEvent:
    return _event(f"{fmt}: Secrets of Strixhaven", fmt, "Secrets of Strixhaven",
                  ("arena", "limited"), now, start_offset_days, end_offset_days)


def _arena_direct(product: str, booster_slug: str, now: datetime,
                  start_off: int, end_off: int) -> mtgscribe.ScribeEvent:
    return _event(f"Arena Direct: Secrets of Strixhaven {product}", "Arena Direct",
                  f"Secrets of Strixhaven {product}",
                  ("arena", "arena-direct", "limited", "sealed", booster_slug, "secrets-of-strixhaven"),
                  now, start_off, end_off)


def _flashback(set_name: str, now: datetime, start_off: int, end_off: int) -> mtgscribe.ScribeEvent:
    return _event(f"Premier Draft: {set_name}", "Premier Draft", set_name,
                  ("arena", "limited", "flashback", "premier-draft"), now, start_off, end_off)


def _quick_draft(set_name: str, now: datetime, start_off: int, end_off: int) -> mtgscribe.ScribeEvent:
    return _event(f"Quick Draft: {set_name}", "Quick Draft", set_name,
                  ("arena", "limited", "quick-draft"), now, start_off, end_off)


def _midweek(label: str, fmt: str, extra_tags: tuple, now: datetime,
             start_off: int, end_off: int) -> mtgscribe.ScribeEvent:
    return _event(f"Midweek Magic: {label}", fmt, label,
                  ("arena", "limited", "midweek-magic", *extra_tags), now, start_off, end_off)


def _cube(set_name: str, now: datetime, start_off: int, end_off: int) -> mtgscribe.ScribeEvent:
    return _event(f"Premier Draft: {set_name}", "Premier Draft", set_name,
                  ("arena", "limited", "premier-draft", "cube"), now, start_off, end_off)


def _event(title: str, format_label: str, group_label: str, tag_slugs: tuple,
           now: datetime, start_off: int, end_off: int) -> mtgscribe.ScribeEvent:
    start = now + timedelta(days=start_off)
    end = now + timedelta(days=end_off)
    return mtgscribe.ScribeEvent(
        title=title,
        format_label=format_label,
        group_label=group_label,
        start=start,
        end=end,
        start_local=start.replace(tzinfo=None),
        end_local=end.replace(tzinfo=None),
        tag_slugs=tag_slugs,
    )
