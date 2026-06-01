from datetime import datetime

from bot.scoring import QueueGroup, boxes_for_event, compute_score, compute_score_breakdown, supported_formats


def test_boxes_2024_six_win_play_sets_pay_two_at_trophy():
    for code in ("OTJ", "FDN", "BLB", "DSK"):
        assert boxes_for_event(code, 6, datetime(2024, 11, 23)) == 2
        assert boxes_for_event(code, 5, datetime(2024, 11, 23)) == 0


def test_boxes_aetherdrift_premiere_pays_one_at_trophy():
    assert boxes_for_event("DFT", 6, datetime(2025, 2, 22)) == 1
    assert boxes_for_event("DFT", 5, datetime(2025, 2, 22)) == 0


def test_boxes_collector_weekend_pays_one_at_seven_only():
    inside = datetime(2026, 4, 30)  # SOS collector premiere
    assert boxes_for_event("SOS", 7, inside) == 1
    assert boxes_for_event("SOS", 6, inside) == 0


def test_boxes_default_play_booster_ladder_for_later_weekends():
    later = datetime(2026, 5, 20)  # SOS, past the collector window
    assert boxes_for_event("SOS", 7, later) == 2
    assert boxes_for_event("SOS", 6, later) == 1
    assert boxes_for_event("SOS", 5, later) == 0


def test_boxes_play_booster_set_never_collector():
    assert boxes_for_event("TLA", 7, datetime(2025, 12, 1)) == 2
    assert boxes_for_event("TLA", 6, datetime(2025, 12, 1)) == 1


def test_supported_formats_includes_all_bucket_formats():
    fmts = supported_formats()
    assert "PremierDraft" in fmts
    assert "TradDraft" in fmts
    assert "Sealed" in fmts
    assert "TradSealed" in fmts
    # LCQ slots dormant but accepted as soon as 17lands ships data
    assert "LimitedChampionshipQualifier_Draft1" in fmts
    assert "LimitedChampionshipQualifier_Draft2" in fmts


def test_compute_score_zero_when_no_trophies():
    rows = [
        {"format": "PremierDraft", "events": 5, "wins": 12, "losses": 18, "trophies": 0},
    ]
    assert compute_score(rows) == 0.0


def test_compute_score_legacy_formula_single_bucket():
    # Premier bucket, points=10. trophies=4, events=10 → trophy_rate=0.4
    # shrinkage = 4/(4+2) ≈ 0.6667
    # score = 4 × 10 × 0.4 × 0.6667 = 10.667
    rows = [
        {"format": "PremierDraft", "events": 10, "wins": 50, "losses": 30, "trophies": 4},
    ]
    score = compute_score(rows)
    assert score == round(4 * 10 * 0.4 * (4 / 6), 2)


def test_compute_score_combines_sealed_with_tradsealed():
    # Both go into Sealed group (points=8). Combined trophies=3, events=6 → trophy_rate=0.5
    # shrinkage = 3/5 = 0.6
    # score = 3 × 8 × 0.5 × 0.6 = 7.2
    rows = [
        {"format": "Sealed", "events": 4, "wins": 10, "losses": 8, "trophies": 1},
        {"format": "TradSealed", "events": 2, "wins": 8, "losses": 0, "trophies": 2},
    ]
    score = compute_score(rows)
    assert score == round(3 * 8 * 0.5 * (3 / 5), 2)


def test_compute_score_sums_across_groups():
    rows = [
        {"format": "PremierDraft", "events": 10, "wins": 50, "losses": 30, "trophies": 4},
        {"format": "Sealed", "events": 6, "wins": 18, "losses": 8, "trophies": 3},
    ]
    expected = round(4 * 10 * 0.4 * (4 / 6), 2) + round(3 * 8 * 0.5 * (3 / 5), 2)
    # compute_score does the round at the end, so allow small discrepancy
    score = compute_score(rows)
    assert abs(score - expected) < 0.05


def test_compute_score_ignores_unknown_formats():
    rows = [
        {"format": "MidWeekSealed", "events": 5, "wins": 20, "losses": 10, "trophies": 2},
    ]
    assert compute_score(rows) == 0.0


def test_compute_score_includes_qualifier_sealed_variants():
    """Qualifier Weekend and Play-In Trad Sealed map to the Sealed group at 8 pts."""
    rows = [
        {"format": "Qualifier_D1_Sealed", "events": 1, "wins": 7, "losses": 1, "trophies": 1},
    ]
    assert compute_score(rows) == round(1 * 8 * 1 * (1 / 3), 2)


def test_compute_score_lcq_draft_2_special_rule():
    # rule="lcq_draft_2": wins × winrate × points (no trophies, no shrinkage)
    # wins=5, losses=2 → games=7, winrate=5/7
    # score = 5 × (5/7) × 10
    rows = [
        {"format": "LimitedChampionshipQualifier_Draft2",
         "events": 2, "wins": 5, "losses": 2, "trophies": 0},
    ]
    score = compute_score(rows)
    assert score == round(5 * (5 / 7) * 10, 2)


def test_compute_score_handles_zero_events_safely():
    rows = [
        {"format": "PremierDraft", "events": 0, "wins": 0, "losses": 0, "trophies": 0},
    ]
    assert compute_score(rows) == 0.0


def test_compute_score_custom_groups_override():
    custom = (
        QueueGroup("Premier", points=20, formats=("PremierDraft",)),
    )
    rows = [
        {"format": "PremierDraft", "events": 10, "wins": 50, "losses": 30, "trophies": 4},
    ]
    score = compute_score(rows, groups=custom)
    assert score == round(4 * 20 * 0.4 * (4 / 6), 2)


def test_compute_score_breakdown_returns_per_group():
    rows = [
        {"format": "PremierDraft", "events": 10, "wins": 50, "losses": 30, "trophies": 4},
        {"format": "Sealed", "events": 4, "wins": 10, "losses": 8, "trophies": 1},
        {"format": "TradSealed", "events": 2, "wins": 8, "losses": 0, "trophies": 2},
    ]
    breakdown = compute_score_breakdown(rows)
    by_label = {b["label"]: b for b in breakdown}

    assert "Premier" in by_label
    assert by_label["Premier"]["events"] == 10
    assert by_label["Premier"]["trophies"] == 4
    # Premier score: 4 × 10 × 0.4 × (4/6) = 10.67
    assert by_label["Premier"]["score"] == round(4 * 10 * 0.4 * (4 / 6), 2)

    assert "Sealed" in by_label
    # Combined Sealed + TradSealed: trophies=3, events=6, wins=18
    assert by_label["Sealed"]["events"] == 6
    assert by_label["Sealed"]["trophies"] == 3
    assert by_label["Sealed"]["wins"] == 18

    # Groups with no rows are skipped
    assert "Trad" not in by_label
    assert "Quick" not in by_label


def test_compute_score_breakdown_empty():
    assert compute_score_breakdown([]) == []


def test_compute_score_breakdown_skips_unknown_formats():
    rows = [
        {"format": "MidWeekSealed", "events": 5, "wins": 20, "losses": 10, "trophies": 2},
    ]
    assert compute_score_breakdown(rows) == []
