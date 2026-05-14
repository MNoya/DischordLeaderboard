from __future__ import annotations

from datetime import date, datetime, timezone

import pytest
from sqlalchemy import select

from bot.models import DraftEvent, MagicSet, Player, PlayerArchetypeScore
from bot.services.refresh import (
    MULTI,
    _archetype_keys,
    _effective_color_count,
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


class TestEffectiveColorCount:
    def test_basics(self):
        assert _effective_color_count(None) == 0
        assert _effective_color_count("") == 0
        assert _effective_color_count("W") == 1
        assert _effective_color_count("WR") == 2

    def test_includes_splashes(self):
        assert _effective_color_count("WRu") == 3
        assert _effective_color_count("WRug") == 4
        assert _effective_color_count("WRubg") == 5

    def test_dedupes(self):
        # A color appearing as both main and splash counts once
        assert _effective_color_count("Ww") == 1

    def test_three_color_main(self):
        assert _effective_color_count("WUR") == 3
        assert _effective_color_count("WURb") == 4
        assert _effective_color_count("WURbg") == 5


class TestArchetypeKeys:
    def test_clean_two_color_only_named(self):
        # 2 effective → no MULTI
        assert _archetype_keys("WR") == ["WR"]

    def test_two_color_one_splash_only_named(self):
        # 3 effective → no MULTI
        assert _archetype_keys("WRu") == ["WR"]

    def test_two_color_two_splashes_adds_multicolor(self):
        # 4 effective → MULTI
        assert _archetype_keys("WRug") == ["WR", MULTI]

    def test_clean_three_color_only_named(self):
        # 3 effective → no MULTI
        assert _archetype_keys("WUR") == ["WUR"]

    def test_three_color_one_splash_adds_multicolor(self):
        # 4 effective → MULTI (still keeps WUR identity)
        assert _archetype_keys("WURb") == ["WUR", MULTI]

    def test_three_color_two_splashes_adds_multicolor(self):
        # 5 effective → MULTI
        assert _archetype_keys("WURbg") == ["WUR", MULTI]

    def test_four_color_main_adds_multicolor(self):
        assert _archetype_keys("WUBR") == ["WUBR", MULTI]

    def test_five_color_main_adds_multicolor(self):
        assert _archetype_keys("WUBRG") == ["WUBRG", MULTI]

    def test_empty_preserved(self):
        # Preserves existing behavior of recording empty/null colors under ''
        assert _archetype_keys(None) == [""]
        assert _archetype_keys("") == [""]


@pytest.fixture
def player_and_set(session):
    p = Player(
        slug="testp",
        discord_id="1",
        display_name="TestP",
        seventeenlands_token="t" * 32,
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


class TestMulticolorMembership:
    """An event with effective colors ≥ 4 lands in BOTH its named bucket AND
    MULTI. The cross-cutting bucket aggregates only those qualifying events.
    """

    def test_clean_jeskai_no_multicolor_row(self, session, player_and_set):
        p, s = player_and_set
        # Two clean Jeskai events (3 effective each)
        _add_event(session, p, s, fmt="PremierDraft", colors="WUR", wins=7, losses=1, is_trophy=True,  idx=1)
        _add_event(session, p, s, fmt="PremierDraft", colors="WUR", wins=4, losses=3, is_trophy=False, idx=2)
        session.flush()

        recompute_player_archetype_scores(session, p.id, s.id)
        session.flush()

        keys = {
            r.archetype
            for r in session.execute(
                select(PlayerArchetypeScore).where(PlayerArchetypeScore.player_id == p.id)
            ).scalars().all()
        }
        assert keys == {"WUR"}

    def test_jeskai_with_splash_doubles_into_multicolor(self, session, player_and_set):
        p, s = player_and_set
        # Clean Jeskai + Jeskai splashing G (4 effective) + Jeskai splashing G+B (5 effective)
        _add_event(session, p, s, fmt="PremierDraft", colors="WUR",   wins=7, losses=1, is_trophy=True,  idx=1)
        _add_event(session, p, s, fmt="PremierDraft", colors="WURg",  wins=7, losses=2, is_trophy=True,  idx=2)
        _add_event(session, p, s, fmt="PremierDraft", colors="WURbg", wins=4, losses=3, is_trophy=False, idx=3)
        session.flush()

        recompute_player_archetype_scores(session, p.id, s.id)
        session.flush()

        rows = {
            r.archetype: r
            for r in session.execute(
                select(PlayerArchetypeScore).where(PlayerArchetypeScore.player_id == p.id)
            ).scalars().all()
        }
        assert set(rows.keys()) == {"WUR", MULTI}

        # WUR holds all three events — splashes don't kick the deck out of its
        # main-color identity
        assert rows["WUR"].events == 3
        assert rows["WUR"].trophies == 2

        # MULTI holds only the two splashy events (4 and 5 effective colors)
        assert rows[MULTI].events == 2
        assert rows[MULTI].trophies == 1
        # Both splashy events came from the same format → wins/losses match those events
        assert rows[MULTI].wins == 7 + 4
        assert rows[MULTI].losses == 2 + 3

    def test_boros_two_splashes_doubles_into_multicolor(self, session, player_and_set):
        # Symmetric rule across main-color counts: a 2C deck splashing 2 colors
        # also lands in MULTI.
        p, s = player_and_set
        _add_event(session, p, s, fmt="PremierDraft", colors="WR",   wins=7, losses=2, is_trophy=True,  idx=1)
        _add_event(session, p, s, fmt="PremierDraft", colors="WRug", wins=7, losses=1, is_trophy=True,  idx=2)
        session.flush()

        recompute_player_archetype_scores(session, p.id, s.id)
        session.flush()

        rows = {
            r.archetype: r
            for r in session.execute(
                select(PlayerArchetypeScore).where(PlayerArchetypeScore.player_id == p.id)
            ).scalars().all()
        }
        assert set(rows.keys()) == {"WR", MULTI}
        assert rows["WR"].events == 2
        assert rows[MULTI].events == 1
        assert rows[MULTI].trophies == 1

    def test_stale_multicolor_dropped(self, session, player_and_set):
        # A player who pivoted away from multicolor should have their old
        # MULTI row cleaned up.
        p, s = player_and_set
        _add_event(session, p, s, fmt="PremierDraft", colors="WURbg", wins=7, losses=1, is_trophy=True, idx=1)
        session.flush()
        recompute_player_archetype_scores(session, p.id, s.id)
        session.flush()
        assert session.execute(
            select(PlayerArchetypeScore).where(PlayerArchetypeScore.archetype == MULTI)
        ).scalar_one_or_none() is not None

        # Pivot to clean Boros only
        for ev in session.execute(select(DraftEvent)).scalars().all():
            session.delete(ev)
        session.flush()
        _add_event(session, p, s, fmt="PremierDraft", colors="WR", wins=7, losses=2, is_trophy=True, idx=2)
        session.flush()

        recompute_player_archetype_scores(session, p.id, s.id)
        session.flush()

        assert session.execute(
            select(PlayerArchetypeScore).where(PlayerArchetypeScore.archetype == MULTI)
        ).scalar_one_or_none() is None
        assert session.execute(
            select(PlayerArchetypeScore).where(PlayerArchetypeScore.archetype == "WR")
        ).scalar_one_or_none() is not None
