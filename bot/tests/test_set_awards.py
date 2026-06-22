from datetime import datetime, timezone

from bot.models import DraftEvent
from bot.services import set_awards as sa


def _event(account_id, start_rank, end_rank, day):
    return DraftEvent(
        account_id=account_id, start_rank=start_rank, end_rank=end_rank,
        started_at=datetime(2026, 6, day, 12, tzinfo=timezone.utc),
        finished_at=datetime(2026, 6, day, 14, tzinfo=timezone.utc),
    )


def _ctx(events):
    return sa.PlayerCtx(player=None, events=events)


def test_climb_does_not_stitch_a_low_rank_on_one_account_to_mythic_on_another():
    events = [
        _event(1, "Bronze-4", "Gold-1", 1),
        _event(2, "Diamond-2", "Mythic", 4),
    ]

    _days, _floor_index, start_tier = sa._best_mythic_climb(_ctx(events))

    assert start_tier == "Diamond"


def test_single_account_bronze_to_mythic_registers_the_full_climb():
    events = [
        _event(1, "Bronze-4", "Gold-1", 1),
        _event(1, "Gold-1", "Mythic", 4),
    ]

    days, _floor_index, start_tier = sa._best_mythic_climb(_ctx(events))

    assert start_tier == "Bronze"
    assert days == 3


def test_lower_start_tier_always_outranks_a_faster_higher_start():
    slow_gold = sa._climb_score(sa.RANK_TIERS.index("Gold"), 20)
    fast_platinum = sa._climb_score(sa.RANK_TIERS.index("Platinum"), 0)

    assert slow_gold > fast_platinum
