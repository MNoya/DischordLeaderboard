"""Owner-only `!test awards` — preview season awards post rendered from fixture data.

Feeds a hardcoded `AwardsData` through the production `build_awards_view` so the
Components V2 layout can be tweaked and confirmed visually without scanning channels.
To remove: delete the file + drop the `setup` call from bot/main.py setup_hook.
"""
from __future__ import annotations

import logging

from discord.ext import commands

from bot.commands.preview_season_awards import AwardsData, AwardWinner, build_awards_view, reveal_awards
from bot.commands.test_group import test_group

log = logging.getLogger(__name__)


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
