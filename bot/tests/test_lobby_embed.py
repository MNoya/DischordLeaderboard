"""Pure-function tests for the pod-draft lobby + ready-check embeds."""
from __future__ import annotations

import discord

from bot.services.lobby_embed import render, render_ready_check_progress


def _field(embed, prefix: str):
    return next((f for f in embed.fields if f.name.startswith(prefix)), None)


def test_in_session_arena_handle_deduped_from_maybe():
    """A player in the Draftmancer session whose Maybe RSVP is their Arena handle should not also
    appear in the Maybe bucket (dedup by arena name, not just linked display name)."""
    embed = render(
        title="Pod Draft",
        rsvps_yes=[],
        rsvps_maybe=["Suiname#00231"],
        in_session=[("Suiname#00231", "Maybe Greg")],
        state="linked",
    )
    maybe = _field(embed, "🤷 Maybe")
    assert maybe is not None
    assert maybe.name.endswith("(0)")


def test_unlinked_seat_counted_in_draftmancer_but_listed_separately():
    """An in-session player with no linked Player row counts toward the In Draftmancer total but is
    listed in its own Unrecognized bucket, not among the linked players."""
    embed = render(
        title="Pod Draft",
        rsvps_yes=[],
        rsvps_maybe=[],
        in_session=[("Player1#0001", "Player One"), ("Stranger#12345", None)],
        state="unlinked",
    )

    roster = _field(embed, "✅ In Draftmancer")
    unrecognized = _field(embed, "⚠️ Unrecognized")

    assert roster.name.endswith("(2)")
    assert unrecognized is not None
    assert unrecognized.name.endswith("(1)")
    assert "Stranger#12345" in unrecognized.value


def test_team_pod_folds_roster_into_two_team_columns_once_drafting():
    """A team draft replaces the flat player list with Green/Blue columns once teams are assigned,
    keying by normalized Arena name so the seat's team survives suffix/case differences."""
    in_session = [("Ava#1", "Ava"), ("Bram#2", "Bram"), ("Cara#3", "Cara"), ("Dex#4", "Dex")]
    teams = {"ava#1": "A", "cara#3": "A", "bram#2": "B", "dex#4": "B"}

    embed = render(
        title="Pod Draft", rsvps_yes=[], rsvps_maybe=[], in_session=in_session,
        state="drafting", teams=teams,
    )

    green = _field(embed, "🟩")
    blue = _field(embed, "🟦")
    assert _field(embed, "✅") is None
    assert "Ava" in green.value and "Cara" in green.value
    assert "Bram" in blue.value and "Dex" in blue.value


def test_team_pod_keeps_flat_roster_before_draft_starts():
    """Teams aren't known until startDraft, so a team pod still shows the flat In Draftmancer list
    through the lobby and ready-check phases."""
    embed = render(
        title="Pod Draft", rsvps_yes=[], rsvps_maybe=[],
        in_session=[("Ava#1", "Ava"), ("Bram#2", "Bram")],
        state="linked", teams={"ava#1": "A", "bram#2": "B"},
    )

    assert _field(embed, "✅ In Draftmancer") is not None
    assert _field(embed, "🟩") is None


def test_spectators_listed_comma_separated_when_present():
    embed = render(
        title="Pod Draft", rsvps_yes=[], rsvps_maybe=[], in_session=[],
        state="linked", spectators=["Tassagk", "Vesperin"],
    )
    field = _field(embed, "👀 Spectators")
    assert field.name.endswith("(2)")
    assert field.value == "Tassagk, Vesperin"


def test_no_spectator_field_when_none():
    embed = render(
        title="Pod Draft", rsvps_yes=[], rsvps_maybe=[], in_session=[], state="linked",
    )
    assert _field(embed, "👀 Spectators") is None


def test_lobby_card_shows_overview_not_split_during_ready():
    """During a ready check the lobby card keeps the In Draftmancer overview; the live Ready/Pending
    split lives only on the separate progress card."""
    in_session = [(f"P{i}#000{i}", f"Player{i}") for i in range(5)]
    embed = render(
        title="Pod Draft", rsvps_yes=[], rsvps_maybe=[], in_session=in_session, state="ready",
    )
    assert _field(embed, "✅ In Draftmancer").name.endswith("(5)")
    assert _field(embed, "✅ Ready (") is None
    assert _field(embed, "⏳ Pending") is None


def test_lobby_card_hides_link_during_ready_check_but_shows_it_otherwise():
    url = "https://draftmancer.com/?session=X"

    linked = render(
        title="Pod Draft", rsvps_yes=[], rsvps_maybe=[], in_session=[], state="linked",
        draftmancer_url=url,
    )
    ready = render(
        title="Pod Draft", rsvps_yes=[], rsvps_maybe=[], in_session=[], state="ready",
        draftmancer_url=url,
    )

    assert url in (linked.description or "")
    assert url not in (ready.description or "")


def test_ready_progress_card_never_shows_the_link():
    in_session = [(f"P{i}#000{i}", f"Player{i}") for i in range(8)]

    embed = render_ready_check_progress(
        "Pod Draft", in_session, state="ready", ready_arena_names=set(),
    )

    assert "draftmancer.com" not in (embed.description or "")


def test_ready_progress_drafting_marks_everyone_ready():
    in_session = [(f"P{i}#000{i}", f"Player{i}") for i in range(8)]
    embed = render_ready_check_progress("Pod Draft", in_session, state="drafting")
    assert _field(embed, "✅ Ready").name.endswith("(8)")
    assert _field(embed, "⏳ Pending") is None


def test_ready_progress_complete_labels_players():
    in_session = [(f"P{i}#000{i}", f"Player{i}") for i in range(8)]
    embed = render_ready_check_progress("Pod Draft", in_session, state="complete")
    assert _field(embed, "✅ Players").name.endswith("(8)")
    assert _field(embed, "⏳ Pending") is None
    assert embed.color == discord.Color.green()


def test_ready_progress_in_progress_splits_ready_and_pending():
    in_session = [(f"P{i}#000{i}", f"Player{i}") for i in range(8)]
    ready = {arena for arena, _ in in_session[:3]}
    embed = render_ready_check_progress(
        "Pod Draft", in_session, state="ready", ready_arena_names=ready,
    )
    assert _field(embed, "✅ Ready").name.endswith("(3)")
    assert _field(embed, "⏳ Pending").name.endswith("(5)")


def test_ready_progress_superseded_shows_only_decliner_no_roster():
    """A superseded card a newer ready check has replaced shows only the decliner header — no roster
    snapshot at all, so a dead check never repeats the player list."""
    in_session = [(f"P{i}#000{i}", f"Player{i}") for i in range(8)]
    embed = render_ready_check_progress(
        "Pod Draft", in_session, state="notready",
        decliner_name="Player3#0003", superseded=True,
    )
    assert _field(embed, "✅ In Draftmancer") is None
    assert _field(embed, "⏳ Pending") is None
    assert "Player3#0003" in embed.description
    assert "retry" not in embed.description


def test_ready_progress_declined_collapses_to_tally():
    """A declined card collapses to the 'is Not Ready' banner plus an X/N ready tally, dropping the
    Draftmancer link and the Ready/Pending roster."""
    in_session = [(f"P{i}#000{i}", f"Player{i}") for i in range(8)]
    embed = render_ready_check_progress(
        "Pod Draft", in_session, state="notready",
        decliner_name="Player3#0003", ready_count=3, total_count=8,
    )
    assert "Player3#0003" in embed.description
    assert "3/8" in embed.description
    assert "draftmancer.com" not in embed.description
    assert _field(embed, "✅ Ready") is None
    assert _field(embed, "⏳ Pending") is None


def test_ready_progress_carries_initiator_through_decline():
    in_session = [(f"P{i}#000{i}", f"Player{i}") for i in range(8)]
    active = render_ready_check_progress(
        "Pod Draft", in_session, state="ready", ready_arena_names=set(), initiated_by="Noya",
    )
    assert "Noya" in active.description

    declined = render_ready_check_progress(
        "Pod Draft", in_session, state="notready", decliner_name="x", initiated_by="Noya",
    )

    assert "Noya" in (declined.description or "")
