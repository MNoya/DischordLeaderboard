from bot.services.pod_seating_select import parse_seat_reorder

ORDER = ["alice#1", "bob#2", "carol#3", "dave#4"]
LABELS = ["Alice", "Bob", "Carol", "Dave"]


def test_reorder_by_names_only():
    reordered, err = parse_seat_reorder("Carol\nAlice\nDave\nBob", ORDER, LABELS)
    assert err is None
    assert reordered == ["carol#3", "alice#1", "dave#4", "bob#2"]


def test_ignores_stray_leading_numbers():
    reordered, err = parse_seat_reorder("#3 Carol\n1- Alice\n4) Dave\n2. Bob", ORDER, LABELS)
    assert err is None
    assert reordered == ["carol#3", "alice#1", "dave#4", "bob#2"]


def test_rejects_invalid_order():
    reordered, _ = parse_seat_reorder("Alice\nBob\nCarol\nEve", ORDER, LABELS)
    assert reordered is None
