"""Owner-only `!test component` — PoC of a Components V2 champion announcement.

Components V2 is opt-in per-message via MessageFlags.components_v2 (32768). When set, the message
can't use traditional `content=` or `embeds=` — everything lives in `view=` as typed components
(Container, Section, TextDisplay, Separator, MediaGallery, Thumbnail, ActionRow, etc.).

This file is throwaway scaffolding for design exploration of V2; no production code reads it.
To remove: delete the file + drop the `setup` call from bot/main.py setup_hook.
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from itertools import cycle, islice

import discord
from discord import ui
from discord.ext import commands

from bot import emojis
from bot.commands.test_group import test_group


log = logging.getLogger(__name__)


_DECK_SCREENSHOT_URL_A = (
    "https://cdn.discordapp.com/attachments/1505053484976836720/1505415554876444802/image.png"
    "?ex=6a0a8afd&is=6a09397d&hm=c187253dfaa892ac443b7dfa4432cb2c8e77d4090b5403202fc7910ca87ec868&"
)
_DECK_SCREENSHOT_URL_B = (
    "https://cdn.discordapp.com/attachments/1505053484976836720/1505412309747499048/image.png"
    "?ex=6a0a87f7&is=6a093677&hm=1fb4f72d8ea4f4af63c924e342fb45505a8e4f2af22cd64c21cc066f6d4128ff&"
)
_DECK_SCREENSHOT_URL_C = (
    "https://cdn.discordapp.com/attachments/1505053484976836720/1505402147389444106/image.png"
    "?ex=6a0a7e80&is=6a092d00&hm=20bd0c76e2c65dfac412a33ccc975847cce70b07ccbcd9d8c6690176ab2684cd&"
)
_DECK_SCREENSHOT_URL_D = (
    "https://cdn.discordapp.com/attachments/1503568130297823273/1504303344582131882/"
    "Screenshot_2026-05-13_220355.png"
    "?ex=6a0a73a9&is=6a092229&hm=b14d1cdbe551ce651354086237038d71b604f85d991099184b41823d9019bd9b&"
)

_THREAD_DEEP_LINK = "https://discord.com/channels/1465844083107827745/1505053484976836720"

_NBSP = " "

_PODIUM = [
    # (medal, name, caption, image_url) — only ranks 1 and 2 get a full image + caption.
    ("🥇", "Noya", "I'd been waiting all night to open that double Bolt", _DECK_SCREENSHOT_URL_A),
    ("🥈", "Oophies", "Co-champion vibes, that R3 was wild", _DECK_SCREENSHOT_URL_B),
]

_ALSO_RANS = ["Arcyl", "Chonce", "whalematron", "Elfandor", "flutterdev", "Doctormagi"]

# (rank, medal, name, record, mana_emoji_name) — one row per pod participant.
_STANDINGS = [
    ("1.", "🥇", "Noya", "3-0", "manaur"),
    ("2.", "🥈", "Oophies", "2-1", "managw"),
    ("3.", "🥉", "Arcyl", "2-1", "manawb"),
    ("4.", "", "Chonce", "2-1", "manabg"),
    ("5.", "", "whalematron", "1-2", "manabr"),
    ("6.", "", "Elfandor", "1-2", "manag"),
    ("7.", "", "flutterdev", "1-2", "manaur"),
    ("8.", "", "Doctormagi", "0-3", "manawubrg"),
]


def _build_champion_view() -> ui.LayoutView:
    """Build the Components V2 layout: featured podium decks + grouped gallery for the rest."""
    view = ui.LayoutView()

    container = ui.Container(accent_colour=discord.Color.green())

    ts = int(datetime.now(timezone.utc).timestamp())
    container.add_item(ui.TextDisplay(
        "## 🏆 Noya takes SOS Pod Draft #3\n"
        f"-# Crowned <t:{ts}:F>"
    ))

    container.add_item(ui.Separator(visible=True, spacing=discord.SeparatorSpacing.small))

    def _row(rank: str, medal: str, name: str, record: str, mana_name: str) -> str:
        prefix = f"{rank} {medal} " if medal else f"{rank} "
        glyph = emojis.get(mana_name)
        suffix = f"  {glyph}" if glyph else ""
        return f"{prefix}{name}  {record}{suffix}"

    standings_text = "**Final Standings**\n" + "\n".join(_row(*row) for row in _STANDINGS)
    container.add_item(ui.TextDisplay(standings_text))

    container.add_item(ui.Separator(visible=True, spacing=discord.SeparatorSpacing.large))

    gap = _NBSP * 4
    for i, (medal, name, caption, image_url) in enumerate(_PODIUM):
        container.add_item(ui.TextDisplay(f"{medal} _{caption}_{gap}~{name}"))
        container.add_item(ui.MediaGallery(
            discord.MediaGalleryItem(media=image_url, description=f"{name}'s deck"),
        ))
        if i < len(_PODIUM) - 1:
            container.add_item(ui.Separator(visible=False, spacing=discord.SeparatorSpacing.small))

    container.add_item(ui.Separator(visible=True, spacing=discord.SeparatorSpacing.small))

    # Cycle ABC for all but the last seat, then drop D in the last slot specifically.
    rotated = list(islice(
        cycle((_DECK_SCREENSHOT_URL_A, _DECK_SCREENSHOT_URL_B, _DECK_SCREENSHOT_URL_C)),
        max(len(_ALSO_RANS) - 1, 0),
    ))
    rest_urls = rotated + [_DECK_SCREENSHOT_URL_D]
    rest_items = [
        discord.MediaGalleryItem(media=url, description=f"{name}'s deck")
        for name, url in zip(_ALSO_RANS, rest_urls)
    ]
    container.add_item(ui.MediaGallery(*rest_items))

    view.add_item(container)

    # ActionRow at the LayoutView top level renders OUTSIDE the accent-bar frame.
    actions = ui.ActionRow()
    actions.add_item(ui.Button(
        label="Thread",
        style=discord.ButtonStyle.link,
        url=_THREAD_DEEP_LINK,
    ))
    view.add_item(actions)

    return view


async def setup(bot: commands.Bot) -> None:
    @test_group.command(name="component")
    @commands.is_owner()
    async def test_component(ctx: commands.Context) -> None:
        """Owner-only. Post a hardcoded Components V2 sample announcement in this channel."""
        view = _build_champion_view()
        await ctx.send(view=view)
