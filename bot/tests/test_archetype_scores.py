from __future__ import annotations

from datetime import date, datetime, timezone

import pytest
from sqlalchemy import select

from bot.models import DraftEvent, MagicSet, Player, PlayerArchetypeScore
from bot.services.refresh import (
    _normalize_archetype,
    recompute_player_archetype_scores,
)


class TestNormalizeArchetype:
    def test_strips_splash(self):
        assert _normalize_archetype("WBg") == "WB"

    def test_sorts_wubrg(self):
        assert _normalize_archetype("RWU") == "WUR"
        assert _normalize_archetype("GWBR") == "WBRG"

    def test_drops_lowercase_only(self):
        # All-splash → empty
        assert _normalize_archetype("wu") == ""

    def test_none_and_empty(self):
        assert _normalize_archetype(None) == ""
        assert _normalize_archetype("") == ""

    def test_mono_color(self):
        assert _normalize_archetype("Wu") == "W"

    def test_five_color(self):
        assert _normalize_archetype("WUBRG") == "WUBRG"
        assert _normalize_archetype("GRBUW") == "WUBRG"


@pytest.fixture
def player_and_set(session):
    p = Player(
        slug="testp",
        discord_id="1",
        display_name="TestP",
        seventeenlands_token="t" * 32,
        seventeenlands_url="https://www.17lands.com/user_history/" + ("t" * 32),
        active=True,
    )
    s = MagicSet(code="SOS", name="Strixhaven", start_date=date(2026, 4, 21))
    session.add_all([p, s])
    session.flush()
    return p, s


def _add_event(session, p, s, *, fmt, colors, wins, losses, is_trophy, idx):
    session.add(
        DraftEvent(
            player_id=p.id,
            set_id=s.id,
            seventeenlands_event_id=f"evt-{idx}",
            format=fmt,
            expansion="SOS",
            wins=wins,
            losses=losses,
            is_trophy=is_trophy,
            colors=colors,
            started_at=datetime.now(timezone.utc),
            finished_at=datetime.now(timezone.utc),
        )
    )


class TestRecomputePlayerArchetypeScores:
    def test_groups_by_normalized_archetype(self, session, player_and_set):
        p, s = player_and_set
        # Two WB events (one with green splash) + one UR event
        _add_event(session, p, s, fmt="PremierDraft", colors="WB",  wins=7, losses=1, is_trophy=True,  idx=1)
        _add_event(session, p, s, fmt="PremierDraft", colors="WBg", wins=4, losses=3, is_trophy=False, idx=2)
        _add_event(session, p, s, fmt="PremierDraft", colors="UR",  wins=7, losses=2, is_trophy=True,  idx=3)
        session.flush()

        recompute_player_archetype_scores(session, p.id, s.id)
        session.flush()

        rows = {
            r.archetype: r
            for r in session.execute(
                select(PlayerArchetypeScore).where(PlayerArchetypeScore.player_id == p.id)
            ).scalars().all()
        }

        assert set(rows.keys()) == {"WB", "UR"}
        wb = rows["WB"]
        assert wb.events == 2
        assert wb.trophies == 1
        assert wb.wins == 11
        assert wb.losses == 4
        ur = rows["UR"]
        assert ur.events == 1
        assert ur.trophies == 1

    def test_drops_stale_archetypes(self, session, player_and_set):
        p, s = player_and_set
        # Initial: WB only
        _add_event(session, p, s, fmt="PremierDraft", colors="WB", wins=7, losses=1, is_trophy=True, idx=1)
        session.flush()
        recompute_player_archetype_scores(session, p.id, s.id)
        session.flush()
        assert session.execute(
            select(PlayerArchetypeScore).where(PlayerArchetypeScore.archetype == "WB")
        ).scalar_one_or_none() is not None

        # Player pivots away — only UR events now (delete WB events first)
        for ev in session.execute(select(DraftEvent)).scalars().all():
            session.delete(ev)
        session.flush()
        _add_event(session, p, s, fmt="PremierDraft", colors="UR", wins=7, losses=2, is_trophy=True, idx=2)
        session.flush()

        recompute_player_archetype_scores(session, p.id, s.id)
        session.flush()

        assert session.execute(
            select(PlayerArchetypeScore).where(PlayerArchetypeScore.archetype == "WB")
        ).scalar_one_or_none() is None
        assert session.execute(
            select(PlayerArchetypeScore).where(PlayerArchetypeScore.archetype == "UR")
        ).scalar_one_or_none() is not None
