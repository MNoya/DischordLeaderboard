"""Pure-function tests for the pod-draft lobby + ready-check embeds."""
from __future__ import annotations

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
    assert maybe.name == "🤷 Maybe (0)"


def test_lobby_card_shows_overview_not_split_during_ready():
    """During a ready check the lobby card keeps the In Draftmancer overview; the live Ready/Pending
    split lives only on the separate progress card."""
    in_session = [(f"P{i}#000{i}", f"Player{i}") for i in range(5)]
    embed = render(
        title="Pod Draft", rsvps_yes=[], rsvps_maybe=[], in_session=in_session, state="ready",
    )
    assert _field(embed, "✅ In Draftmancer").name == "✅ In Draftmancer (5)"
    assert _field(embed, "✅ Ready (") is None
    assert _field(embed, "⏳ Pending") is None


def test_ready_progress_drafting_marks_everyone_ready():
    in_session = [(f"P{i}#000{i}", f"Player{i}") for i in range(8)]
    embed = render_ready_check_progress("Pod Draft", in_session, state="drafting")
    assert _field(embed, "✅ Ready").name == "✅ Ready (8)"
    assert _field(embed, "⏳ Pending") is None


def test_ready_progress_complete_labels_players():
    in_session = [(f"P{i}#000{i}", f"Player{i}") for i in range(8)]
    embed = render_ready_check_progress("Pod Draft", in_session, state="complete")
    assert _field(embed, "✅ Players").name == "✅ Players (8)"
    assert _field(embed, "⏳ Pending") is None
    assert "Draft complete" in embed.description


def test_ready_progress_in_progress_splits_ready_and_pending():
    in_session = [(f"P{i}#000{i}", f"Player{i}") for i in range(8)]
    ready = {arena for arena, _ in in_session[:3]}
    embed = render_ready_check_progress(
        "Pod Draft", in_session, state="ready", ready_arena_names=ready,
    )
    assert _field(embed, "✅ Ready").name == "✅ Ready (3)"
    assert _field(embed, "⏳ Pending").name == "⏳ Pending (5)"


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
    assert "Player3#0003` declined" in embed.description
    assert "retry" not in embed.description


def test_ready_progress_shows_initiator_only_during_active_check():
    in_session = [(f"P{i}#000{i}", f"Player{i}") for i in range(8)]
    active = render_ready_check_progress(
        "Pod Draft", in_session, state="ready", ready_arena_names=set(), initiated_by="Noya",
    )
    assert "Started by Noya" in active.description
    declined = render_ready_check_progress(
        "Pod Draft", in_session, state="notready", decliner_name="x", initiated_by="Noya",
    )
    assert "Started by" not in declined.description
