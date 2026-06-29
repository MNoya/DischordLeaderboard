"""Submit-Deck button + ephemeral guild dropdown + write-in modal.

Pure UI; persistence is injected via callbacks so the same components back both the
testlobby preview (in-memory dict) and the live flow (DB write).

Callbacks raise NotInPodError when the caller isn't a registered participant for
the current pod — the UI then short-circuits to a polite ephemeral instead of
showing the dropdown.

Storage convention: WUBRG-sorted main colors uppercase, splash lowercase
(matches 17lands and the Pips component on the frontend). E.g. 'WU', 'URg'.
"""
from __future__ import annotations

from typing import Awaitable, Callable

import discord
from discord import ui


class NotInPodError(Exception):
    """Raised by lookup/submit callbacks when the interaction user isn't a participant."""


SubmitCallback = Callable[[discord.Interaction, str], Awaitable[None]]
LookupCallback = Callable[[discord.Interaction], Awaitable[tuple[str | None, bool | None]]]
ReviewToggleCallback = Callable[[discord.Interaction, bool], Awaitable[None]]
OrganizerCallback = Callable[[discord.Interaction], Awaitable[bool]]


# Track the most recent ephemeral per user so we can delete it on the next button click
# (avoids the stacked-ephemeral pile-up Discord otherwise leaves behind).
_PREV_EPHEMERAL: dict[int, discord.InteractionMessage] = {}


GUILDS: list[tuple[str, str]] = [
    ("WU", "Azorius"),
    ("WB", "Orzhov"),
    ("WR", "Boros"),
    ("WG", "Selesnya"),
    ("UB", "Dimir"),
    ("UR", "Izzet"),
    ("UG", "Simic"),
    ("BR", "Rakdos"),
    ("BG", "Golgari"),
    ("RG", "Gruul"),
]
GUILD_LABEL = {code: name for code, name in GUILDS}

# Two-color Mana font emoji names — follow the color-wheel hybrid order, NOT WUBRG: WR is `manarw`,
# WG is `managw`, UG is `managu`. Keyed by frozenset so input order doesn't matter.
PAIR_EMOJI_NAME: dict[frozenset[str], str] = {
    frozenset("WU"): "manawu",
    frozenset("WB"): "manawb",
    frozenset("WR"): "manarw",
    frozenset("WG"): "managw",
    frozenset("UB"): "manaub",
    frozenset("UR"): "manaur",
    frozenset("UG"): "managu",
    frozenset("BR"): "manabr",
    frozenset("BG"): "manabg",
    frozenset("RG"): "manarg",
}
OTHER_VALUE = "__other__"

NOT_IN_POD_MSG = "You are not registered as a player in this pod"

SAVED_MSG = "Choices saved. Adjust or dismiss below"

REVIEW_YES_VALUE = "yes"
REVIEW_NO_VALUE = "no"

DRAFT_REVIEW_FEATURE_ENABLED = False


def color_label(code: str) -> str:
    if code in GUILD_LABEL:
        return f"{GUILD_LABEL[code]} ({code})"
    return code


def _sanitize(raw: str) -> str | None:
    s = raw.strip()
    if not s or len(s) > 5:
        return None
    if not all(c in "WUBRGwubrg" for c in s):
        return None
    return s


class SubmitDeckView(ui.View):
    """Holds the Submit Deck button. Pass the persistence callbacks once at construction.

    For the live (persistent) registration, instantiate with DB-backed callbacks at startup
    via bot.add_view(SubmitDeckView(...)).
    """

    def __init__(
        self,
        on_submit: SubmitCallback,
        on_lookup: LookupCallback,
        on_review_toggle: ReviewToggleCallback,
        on_organizer: OrganizerCallback | None = None,
    ) -> None:
        super().__init__(timeout=None)
        self.add_item(SubmitDeckButton(on_submit, on_lookup, on_review_toggle, on_organizer))


class SubmitDeckButton(ui.Button):
    def __init__(
        self,
        on_submit: SubmitCallback,
        on_lookup: LookupCallback,
        on_review_toggle: ReviewToggleCallback,
        on_organizer: OrganizerCallback | None = None,
    ) -> None:
        super().__init__(
            label="Submit Deck",
            style=discord.ButtonStyle.primary,
            custom_id="poddecksubmit",
            emoji="🎨",
        )
        self._submit = on_submit
        self._lookup = on_lookup
        self._review_toggle = on_review_toggle
        self._organizer = on_organizer

    async def callback(self, interaction: discord.Interaction) -> None:
        if self._organizer is not None and await self._organizer(interaction):
            return
        try:
            current_color, current_review = await self._lookup(interaction)
        except NotInPodError:
            await interaction.response.send_message(NOT_IN_POD_MSG, ephemeral=True)
            return

        prev = _PREV_EPHEMERAL.pop(interaction.user.id, None)
        if prev is not None:
            try:
                await prev.delete()
            except discord.HTTPException:
                pass

        view = DeckColorSelectView(
            self._submit, self._review_toggle,
            current_value=current_color, current_review=current_review,
        )
        await interaction.response.send_message(view=view, ephemeral=True)
        try:
            _PREV_EPHEMERAL[interaction.user.id] = await interaction.original_response()
        except discord.HTTPException:
            pass


class DeckColorSelectView(ui.View):
    def __init__(
        self,
        on_submit: SubmitCallback,
        on_review_toggle: ReviewToggleCallback,
        current_value: str | None,
        current_review: bool | None,
    ) -> None:
        super().__init__(timeout=300)
        self.add_item(DeckColorSelect(on_submit, on_review_toggle, current_value, current_review))
        if DRAFT_REVIEW_FEATURE_ENABLED:
            self.add_item(DraftReviewSelect(on_submit, on_review_toggle, current_value, current_review))


class DeckColorSelect(ui.Select):
    def __init__(
        self,
        on_submit: SubmitCallback,
        on_review_toggle: ReviewToggleCallback,
        current_value: str | None,
        current_review: bool | None,
    ) -> None:
        from bot import emojis as _emojis
        guild_codes = {code for code, _ in GUILDS}
        is_write_in = current_value is not None and current_value not in guild_codes
        options = [discord.SelectOption(
            label=f"Other ({current_value})" if is_write_in else "Other (write-in)",
            value=OTHER_VALUE,
            description="Mono, 3-color, splash, etc.",
            emoji=_emojis.get_emoji("manax"),
            default=is_write_in,
        )]
        options.extend(
            discord.SelectOption(
                label=f"{name} ({code})",
                value=code,
                default=(current_value == code),
                emoji=_emojis.get_emoji(PAIR_EMOJI_NAME[frozenset(code)]),
            )
            for code, name in GUILDS
        )
        super().__init__(placeholder="Choose your deck colors", options=options, min_values=1, max_values=1)
        self._submit = on_submit
        self._review_toggle = on_review_toggle
        self._current_review = current_review

    async def callback(self, interaction: discord.Interaction) -> None:
        value = self.values[0]
        if value == OTHER_VALUE:
            await interaction.response.send_modal(
                DeckColorWriteInModal(self._submit, self._review_toggle, self._current_review),
            )
            return
        await interaction.response.defer()
        try:
            await self._submit(interaction, value)
        except NotInPodError:
            await interaction.edit_original_response(content=NOT_IN_POD_MSG, view=None)
            return
        await interaction.edit_original_response(
            content=SAVED_MSG,
            view=DeckColorSelectView(
                self._submit, self._review_toggle,
                current_value=value, current_review=self._current_review,
            ),
        )


class DraftReviewSelect(ui.Select):
    """Mirror of the deck-color picker for the post-pod review opt-in. Selected option is shown
    in the placeholder, so state is unambiguous. min_values=1 so opening + closing without picking
    leaves the prior value intact."""

    def __init__(
        self,
        on_submit: SubmitCallback,
        on_review_toggle: ReviewToggleCallback,
        current_value: str | None,
        current_review: bool | None,
    ) -> None:
        options = [
            discord.SelectOption(
                label="Yes, staying for draft review",
                value=REVIEW_YES_VALUE,
                emoji="🙋",
                default=current_review is True,
            ),
            discord.SelectOption(
                label="No, skipping draft review",
                value=REVIEW_NO_VALUE,
                emoji="⏭️",
                default=current_review is False,
            ),
        ]
        super().__init__(
            placeholder="Staying for draft review?",
            options=options, min_values=1, max_values=1,
        )
        self._submit = on_submit
        self._review_toggle = on_review_toggle
        self._current_color = current_value

    async def callback(self, interaction: discord.Interaction) -> None:
        wants_review = self.values[0] == REVIEW_YES_VALUE
        await interaction.response.defer()
        try:
            await self._review_toggle(interaction, wants_review)
        except NotInPodError:
            await interaction.edit_original_response(content=NOT_IN_POD_MSG, view=None)
            return
        await interaction.edit_original_response(
            content=SAVED_MSG,
            view=DeckColorSelectView(
                self._submit, self._review_toggle,
                current_value=self._current_color, current_review=wants_review,
            ),
        )


class DeckColorWriteInModal(ui.Modal, title="Deck colors"):
    colors = ui.TextInput(
        label="Colors (e.g. URg, WUBR, WUBRG)",
        placeholder="Uppercase = main, lowercase = splash",
        min_length=1,
        max_length=5,
        required=True,
    )

    def __init__(
        self,
        on_submit: SubmitCallback,
        on_review_toggle: ReviewToggleCallback,
        current_review: bool | None,
    ) -> None:
        super().__init__()
        self._submit = on_submit
        self._review_toggle = on_review_toggle
        self._current_review = current_review

    async def on_submit(self, interaction: discord.Interaction) -> None:
        cleaned = _sanitize(self.colors.value)
        if cleaned is None:
            await interaction.response.edit_message(
                content=f"⚠️ `{self.colors.value}` isn't valid — use only W/U/B/R/G letters, 1–5 chars.",
                view=DeckColorSelectView(
                    self._submit, self._review_toggle,
                    current_value=None, current_review=self._current_review,
                ),
            )
            return
        await interaction.response.defer()
        try:
            await self._submit(interaction, cleaned)
        except NotInPodError:
            await interaction.edit_original_response(content=NOT_IN_POD_MSG, view=None)
            return
        await interaction.edit_original_response(
            content=SAVED_MSG,
            view=DeckColorSelectView(
                self._submit, self._review_toggle,
                current_value=cleaned, current_review=self._current_review,
            ),
        )


LIVE_COLOR_CUSTOM_ID = "poddeckselect-color"
LIVE_REVIEW_CUSTOM_ID = "poddeckselect-review"


class LiveDeckColorSelectView(ui.View):
    """Persistent direct-dropdown view for DM Submit Deck flow — both selects are visible on the
    message itself, so players don't need to click a button first. Interactions defer silently and
    rely on the parent module's refresh helper to re-render the message after persistence."""

    def __init__(
        self,
        on_submit: SubmitCallback,
        on_lookup: LookupCallback,
        on_review_toggle: ReviewToggleCallback,
        current_value: str | None = None,
        current_review: bool | None = None,
    ) -> None:
        super().__init__(timeout=None)
        self.add_item(LiveDeckColorSelect(
            on_submit, on_lookup, on_review_toggle, current_value, current_review,
        ))
        if DRAFT_REVIEW_FEATURE_ENABLED:
            self.add_item(LiveDraftReviewSelect(
                on_submit, on_lookup, on_review_toggle, current_value, current_review,
            ))


def _dm_ephemeral(interaction: discord.Interaction) -> bool:
    return interaction.guild is not None


class LiveDeckColorSelect(ui.Select):
    def __init__(
        self,
        on_submit: SubmitCallback,
        on_lookup: LookupCallback,
        on_review_toggle: ReviewToggleCallback,
        current_value: str | None,
        current_review: bool | None,
    ) -> None:
        from bot import emojis as _emojis
        guild_codes = {code for code, _ in GUILDS}
        is_write_in = current_value is not None and current_value not in guild_codes
        options = [discord.SelectOption(
            label=f"Other ({current_value})" if is_write_in else "Other (write-in)",
            value=OTHER_VALUE,
            description="Mono, 3-color, splash, etc.",
            emoji=_emojis.get_emoji("manax"),
            default=is_write_in,
        )]
        options.extend(
            discord.SelectOption(
                label=f"{name} ({code})",
                value=code,
                default=(current_value == code),
                emoji=_emojis.get_emoji(PAIR_EMOJI_NAME[frozenset(code)]),
            )
            for code, name in GUILDS
        )
        super().__init__(
            custom_id=LIVE_COLOR_CUSTOM_ID,
            placeholder="Choose your deck colors",
            options=options, min_values=1, max_values=1,
        )
        self._submit = on_submit
        self._lookup = on_lookup
        self._review_toggle = on_review_toggle
        self._current_review = current_review

    async def callback(self, interaction: discord.Interaction) -> None:
        value = self.values[0]
        if value == OTHER_VALUE:
            await interaction.response.send_modal(LiveDeckColorWriteInModal(
                self._submit, self._lookup, self._review_toggle, self._current_review,
            ))
            return
        await interaction.response.defer()
        try:
            await self._submit(interaction, value)
        except NotInPodError:
            await interaction.followup.send(NOT_IN_POD_MSG, ephemeral=_dm_ephemeral(interaction))


class LiveDraftReviewSelect(ui.Select):
    def __init__(
        self,
        on_submit: SubmitCallback,
        on_lookup: LookupCallback,
        on_review_toggle: ReviewToggleCallback,
        current_value: str | None,
        current_review: bool | None,
    ) -> None:
        options = [
            discord.SelectOption(
                label="Yes, staying for draft review",
                value=REVIEW_YES_VALUE,
                emoji="🙋",
                default=current_review is True,
            ),
            discord.SelectOption(
                label="No, skipping draft review",
                value=REVIEW_NO_VALUE,
                emoji="⏭️",
                default=current_review is False,
            ),
        ]
        super().__init__(
            custom_id=LIVE_REVIEW_CUSTOM_ID,
            placeholder="Staying for draft review?",
            options=options, min_values=1, max_values=1,
        )
        self._submit = on_submit
        self._lookup = on_lookup
        self._review_toggle = on_review_toggle

    async def callback(self, interaction: discord.Interaction) -> None:
        wants_review = self.values[0] == REVIEW_YES_VALUE
        await interaction.response.defer()
        try:
            await self._review_toggle(interaction, wants_review)
        except NotInPodError:
            await interaction.followup.send(NOT_IN_POD_MSG, ephemeral=_dm_ephemeral(interaction))


class LiveDeckColorWriteInModal(ui.Modal, title="Deck colors"):
    colors = ui.TextInput(
        label="Colors (e.g. URg, WUBR, WUBRG)",
        placeholder="Uppercase = main, lowercase = splash",
        min_length=1,
        max_length=5,
        required=True,
    )

    def __init__(
        self,
        on_submit: SubmitCallback,
        on_lookup: LookupCallback,
        on_review_toggle: ReviewToggleCallback,
        current_review: bool | None,
    ) -> None:
        super().__init__()
        self._submit = on_submit
        self._lookup = on_lookup
        self._review_toggle = on_review_toggle
        self._current_review = current_review

    async def on_submit(self, interaction: discord.Interaction) -> None:
        cleaned = _sanitize(self.colors.value)
        if cleaned is None:
            await interaction.response.send_message(
                f"⚠️ `{self.colors.value}` isn't valid — use only W/U/B/R/G letters, 1–5 chars.",
                ephemeral=_dm_ephemeral(interaction),
            )
            return
        await interaction.response.defer()
        try:
            await self._submit(interaction, cleaned)
        except NotInPodError:
            await interaction.followup.send(NOT_IN_POD_MSG, ephemeral=_dm_ephemeral(interaction))
