from bot.services import pod_format_interest as fi
from bot.sets import active_set_code


def test_normalize_orders_dedupes_and_drops_unknown():
    assert fi.normalize(["flashback", "latest", "flashback", "bogus"]) == [fi.LATEST, fi.FLASHBACK]
    assert fi.normalize([]) == []
    assert fi.normalize(None) == []


def test_flexible_is_both_draftable_set_interests():
    assert fi.is_flexible([fi.LATEST, fi.FLASHBACK]) is True
    assert fi.is_flexible([fi.LATEST]) is False
    assert fi.is_flexible([fi.FLASHBACK, fi.CUBE]) is False


def test_interest_summary_labels():
    assert fi.interest_summary([]) == "No preference"
    assert fi.interest_summary([fi.LATEST]) == "Latest Set"
    assert fi.interest_summary([fi.LATEST, fi.FLASHBACK]) == fi.FLEXIBLE_LABEL
    assert fi.interest_summary([fi.FLASHBACK, fi.CUBE]) == "Flashback and Cube"


def test_composition_classifies_each_member_once():
    members = [
        [fi.LATEST],
        [fi.LATEST],
        [fi.FLASHBACK],
        [fi.FLASHBACK],
        [fi.FLASHBACK],
        [fi.LATEST, fi.FLASHBACK],
        [fi.CUBE],
        [],
    ]

    comp = fi.composition(members)

    assert (comp.latest_only, comp.flashback_only, comp.flexible) == (2, 3, 1)
    assert (comp.cube, comp.unstated, comp.total) == (1, 1, 8)


def test_composition_capacity_folds_flexible_into_both():
    comp = fi.composition([[fi.LATEST], [fi.FLASHBACK], [fi.LATEST, fi.FLASHBACK], [fi.LATEST, fi.FLASHBACK]])

    assert comp.latest_capacity == 3
    assert comp.flashback_capacity == 3
    assert comp.has_signal is True


def test_should_offer_format_poll_needs_dedicated_flashback_and_capacity():
    strong = fi.composition([[fi.FLASHBACK], [fi.FLASHBACK], [fi.LATEST, fi.FLASHBACK]])
    only_flexible = fi.composition([[fi.LATEST, fi.FLASHBACK]] * 5)
    all_latest = fi.composition([[fi.LATEST]] * 8)

    assert fi.should_offer_format_poll(strong) is True
    assert fi.should_offer_format_poll(only_flexible) is False
    assert fi.should_offer_format_poll(all_latest) is False


def test_format_at_fire_stays_on_latest_set():
    members = [[fi.FLASHBACK]] * 8

    assert fi.format_at_fire(members) == active_set_code()
