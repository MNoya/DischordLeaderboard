"""Owner-only `!test awards` — preview season awards post rendered from fixture data.

Feeds a hardcoded `AwardsData` through the production `build_awards_view` so the
Components V2 layout can be tweaked and confirmed visually without scanning channels.
To remove: delete the file + drop the `setup` call from bot/main.py setup_hook.
"""
from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone

import discord
from discord.ext import commands

from bot.commands.preview_season_awards import AwardsData, AwardWinner, build_awards_view, reveal_awards
from bot.commands.set_awards import (
    SetAwardsData,
    build_data,
    build_my_awards_view,
    build_set_awards_view,
    reveal_set_awards,
)
from bot.commands.test_group import test_group
from bot.services import set_awards as awards_svc
from bot.services.set_awards import AwardCandidate
from bot.sets import ALL_SETS, active_set_code

log = logging.getLogger(__name__)

_AVATAR = "https://cdn.discordapp.com/embed/avatars/{}.png"
_SEIZE_WINNER_WHEN = datetime(2026, 5, 16, 18, tzinfo=timezone.utc)


def _cand(
    name: str, detail: str, avatar: str | None, tie: object,
    ceremony_detail: str | None = None, archetype: str | None = None, when: datetime | None = None,
) -> AwardCandidate:
    return AwardCandidate(
        discord_id=None, display_name=name, detail=detail, avatar_url=avatar, tie_key=tie,
        ceremony_detail=ceremony_detail, archetype=archetype, when=when,
    )


def _set_awards_fixture(guild: discord.Guild | None) -> SetAwardsData:
    """Build sample winners/runners as AwardCandidates and run them through the live `build_data`
    path, so the preview shares the production wording formatters and runner-up de-dup logic."""
    code = active_set_code()
    seed = next(s for s in ALL_SETS if s.code == code)
    runner_when = _SEIZE_WINNER_WHEN + timedelta(days=2)
    winners = {
        "first_striker": _cand(
            "Tibalt", awards_svc.first_striker_detail(timedelta(hours=1, minutes=35)), _AVATAR.format(1), None,
            ceremony_detail=awards_svc.first_striker_ceremony(timedelta(hours=1, minutes=35))),
        "seize_the_day": _cand(
            "Jhoira", awards_svc.seize_detail(7, _SEIZE_WINNER_WHEN), _AVATAR.format(0), 7,
            ceremony_detail=awards_svc.seize_ceremony_detail(7, _SEIZE_WINNER_WHEN), when=_SEIZE_WINNER_WHEN),
        "climber": _cand("Korvold", awards_svc.climber_detail("Bronze", 4), _AVATAR.format(2), (6, 4, 0)),
        "specialist": _cand(
            "Karn", awards_svc.specialist_detail(0.88, "URG", 24, 0.61), _AVATAR.format(3), 4.1,
            ceremony_detail=awards_svc.specialist_ceremony_detail(0.88, "URG", 24, 0.61), archetype="URG"),
        "revel_in_riches": _cand("Slimefoot", awards_svc.revel_detail(9, 6), _AVATAR.format(5), 9),
        "mvp": _cand(
            "Squee", awards_svc.mvp_detail(41), _AVATAR.format(4), 41,
            ceremony_detail=awards_svc.mvp_ceremony_detail(41)),
    }
    runners = {
        "first_striker": [_cand("Jhoira", awards_svc.first_striker_gap(timedelta(minutes=22)), None, None)],
        "seize_the_day": [_cand("Squee", awards_svc.seize_detail(6, runner_when), None, 6, when=runner_when)],
        "climber": [_cand("Niv", awards_svc.climber_detail("Gold", 1), None, (5, 1, 2))],
        "specialist": [_cand(
            "Jhoira", awards_svc.specialist_detail(0.83, "URG", 19, 0.61), None, 3.4,
            ceremony_detail=awards_svc.specialist_ceremony_detail(0.83, "URG", 19, 0.61), archetype="URG")],
        "revel_in_riches": [_cand("Tibalt", awards_svc.revel_detail(7, 5), None, 7)],
        "mvp": [_cand(
            "Gisa", awards_svc.mvp_detail(33), None, 33, ceremony_detail=awards_svc.mvp_ceremony_detail(33))],
    }
    return build_data(code, seed, winners, runners, guild)


_IMAGE_HOTTEST = (
    "https://media.discordapp.net/attachments/1387550143234052156/1512089489307205783/"
    "RDT_20260604_0943126322219300266296225.jpg"
    "?ex=6a242413&is=6a22d293&hm=af6622ff8efec55a72a663c635c6d4332059439cded4c6816c6f0db914c72f6e"
    "&=&format=webp&width=585&height=887"
)
_IMAGE_TRASH = (
    "https://media.discordapp.net/attachments/1387550143234052156/1511427842330853417/image.png"
    "?ex=6a23b61e&is=6a22649e&hm=5fa9cc8f804ed49ba8406c532d6b2abaf9584a5c1697dc1b3f471bfbf4e7ca7f"
    "&=&format=webp&quality=lossless"
)
_IMAGE_COMEDY = (
    "https://media.discordapp.net/attachments/775822803328040961/1511766280527417575/image.png"
    "?ex=6a244890&is=6a22f710&hm=32773fe81f12611d50eefc6888c6f8e06183406d7b709eff926d2da40b853039"
    "&=&format=webp&quality=lossless"
)
_IMAGE_READ_AGAIN = (
    "https://media.discordapp.net/attachments/1387550143234052156/1511908884468469840/mbdm9oqu165h1.png"
    "?ex=6a24249f&is=6a22d31f&hm=d2e595e1a437384c6198a923b3ab28a8a96fae67df49d765e3fda49d7e27b223"
    "&=&format=webp&quality=lossless"
)
_IMAGE_FLAVOR_WIN = (
    "https://media.discordapp.net/attachments/1387550143234052156/1512130862135771266/image0.jpg"
    "?ex=6a244a9b&is=6a22f91b&hm=c05f65f6d91414f23679079e136158d7d55839a11cbca97dfde4f07ac9de76d1"
    "&=&format=webp&width=635&height=887"
)

_POST_DEEP_LINK = "https://discord.com/channels/1465844083107827745/1505053484976836720"

_FIXTURE = AwardsData(
    set_code="MSH",
    window_label="June 2 – 8",
    channel_label="<#775822803328040961> & <#1387550143234052156>",
    hottest=AwardWinner(_POST_DEEP_LINK, _IMAGE_HOTTEST, (("🔥", 23),), caption="Okoye, Dora Milaje Leader"),
    trash=AwardWinner(
        _POST_DEEP_LINK, _IMAGE_TRASH, (("🗑", 12), ("🥀", 5), ("👀", 4)), caption="Madame Hydra",
    ),
    comedy=AwardWinner(
        _POST_DEEP_LINK, _IMAGE_COMEDY, (("😂", 31),),
        caption="me when I win with a pile of serra angels and 6/6 no texts",
        author="MemeSmith",
    ),
    surprise=AwardWinner(
        _POST_DEEP_LINK, _IMAGE_READ_AGAIN, (("👀", 14), ("❤️", 3)), caption="Evil's Thrall",
    ),
    flavor=AwardWinner(
        _POST_DEEP_LINK, _IMAGE_FLAVOR_WIN, (("🦅", 8), ("🇺🇸", 6), ("🔥", 10)),
        caption="Captain America, Wings of Freedom",
    ),
    totals=(("🔥", 87), ("🗑", 22), ("🥀", 12), ("😂", 31), ("👀", 14), ("🦅", 11), ("🇺🇸", 6)),
    hot_pct=72,
)


async def setup(bot: commands.Bot) -> None:
    @test_group.command(name="awards")
    @commands.is_owner()
    async def test_awards(ctx: commands.Context, mode: str = "") -> None:
        """Owner-only. Post the fixture-backed preview season awards sample in this channel.

        `!test awards gated` plays the timed one-award-per-edit reveal instead of the full post.
        """
        if mode == "gated":
            ceremony = await ctx.send(view=build_awards_view(_FIXTURE, reveal=0))
            await reveal_awards(ceremony, _FIXTURE)
            return
        await ctx.send(view=build_awards_view(_FIXTURE))

    @test_group.command(name="setawards")
    @commands.is_owner()
    async def test_set_awards(ctx: commands.Context, mode: str = "") -> None:
        """Owner-only. Post the fixture-backed Set Awards sample in this channel.

        `!test setawards gated` plays the timed one-award-per-edit reveal instead of the full post.
        """
        fixture = _set_awards_fixture(ctx.guild)
        if mode == "gated":
            ceremony = await ctx.send(view=build_set_awards_view(fixture, reveal=0))
            await reveal_set_awards(ceremony, fixture)
            return
        await ctx.send(view=build_set_awards_view(fixture))

    @test_group.command(name="myset")
    @commands.is_owner()
    async def test_my_set_awards(ctx: commands.Context, mode: str = "") -> None:
        """Owner-only. Post the fixture-backed personal Set Awards view ("How did I do?") in this channel.

        Default mixes ranked and not-qualified awards so the "didn't qualify" / "safe" reasons show;
        `!test myset full` ranks the caller in every award and fun streak; `!test myset off` ranks
        them in none, so every miss / safe line renders.
        """
        me = "ME"
        who = ctx.author.display_name

        def ahead(count: int, detail: str, tie: object) -> list[AwardCandidate]:
            return [AwardCandidate(f"f{k}", f"Drafter {k}", detail, None, tie) for k in range(count)]

        def mine(detail: str, tie: object) -> AwardCandidate:
            return AwardCandidate(me, who, detail, None, tie)

        span = (datetime(2026, 4, 21, 18, tzinfo=timezone.utc), datetime(2026, 5, 3, 18, tzinfo=timezone.utc))
        if mode == "full":
            ranked = {
                "first_striker": ahead(4, "**40m** after set release", None)
                + [mine("**1h 34m** after set release", None)],
                "seize_the_day": ahead(3, "**9 trophies** in 24h", 9) + [mine("**5 trophies** in 24h on May 16", 5)],
                "climber": ahead(5, "Bronze to Mythic in **5 days**", (0, 5))
                + [mine("Silver to Mythic in **7 days**", (1, 7))],
                "specialist": ahead(11, "**80%** on **WR** over 60 games", 3.5)
                + [mine("a **66%** win rate with **WU** over 41 games, vs field of 60%", 1.2)],
                "revel_in_riches": ahead(7, "**12** boxes in 8 events", 12) + [mine("**3** boxes in 4 events", 3)],
                "mvp": ahead(2, "**41** trophies", 41) + [mine("**18** trophies to trophy-hype", 18)],
            }
            extras = {
                "trophy_streak": 4, "trophy_streak_rank": 2, "trophy_span": span,
                "merchant_streak": 5, "merchant_streak_rank": 1, "merchant_events": 22,
                "heartbreakers": 4, "heartbreakers_rank": 7, "heartbreakers_events": 30,
                "cold_run": 6, "cold_run_rank": 3,
            }
        elif mode == "off":
            ranked = {
                "first_striker": ahead(3, "**40m** after set release", None),
                "seize_the_day": ahead(3, "**9 trophies** in 24h", 9),
                "climber": ahead(3, "Bronze to Mythic in **5 days**", (0, 5)),
                "specialist": ahead(3, "**80%** on **WR** over 60 games", 3.5),
                "revel_in_riches": ahead(3, "**12** boxes in 8 events", 12),
                "mvp": ahead(3, "**41** trophies", 41),
            }
            extras = {
                "trophy_streak": 1,
                "merchant_streak": 2, "merchant_events": 10,
                "heartbreakers": 2, "heartbreakers_events": 14,
                "cold_run": 2,
            }
        else:
            ranked = {
                "first_striker": ahead(2, "**40m** after set release", None)
                + [mine("**1h 34m** after set release", None)],
                "seize_the_day": ahead(3, "**9 trophies** in 24h", 9),
                "climber": [mine("Bronze to Mythic in **6 days**", (0, 6))]
                + ahead(2, "Silver to Mythic in **9 days**", (1, 9)),
                "specialist": ahead(4, "**80%** on **WR** over 60 games", 3.5),
                "revel_in_riches": ahead(3, "**12** boxes in 8 events", 12),
                "mvp": ahead(4, "**41** trophies", 41) + [mine("**6** trophies to trophy-hype", 6)],
            }
            extras = {
                "trophy_streak": 4, "trophy_streak_rank": 2, "trophy_span": span,
                "merchant_streak": 0, "merchant_events": 12,
                "heartbreakers": 2, "heartbreakers_events": 18,
                "cold_run": 5, "cold_run_rank": 3,
            }
        await ctx.send(view=build_my_awards_view("SOS", ranked, me, extras))
