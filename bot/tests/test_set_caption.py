import pytest

from bot.sets import parse_caption_set_code, set_name_for


@pytest.mark.parametrize(
    "caption, expected",
    [
        ("MH1 flashback trophy 3-0", "MH1"),
        ("went 3-0 in MH2", "MH2"),
        ("IPA block draft", "IPA"),
        ("Urza's Saga was brutal, 3-1", "USG"),
        ("Modern Horizons 2 sealed", "MH2"),
        ("first trophy in Modern Horizons!", "MH1"),
        ("SOS quick draft", "SOS"),
        ("clean 3-0 rakdos", None),
        ("won game one then swept", None),
        ("", None),
        (None, None),
    ],
)
def test_parse_caption_set_code(caption, expected):
    assert parse_caption_set_code(caption) == expected


def test_set_name_for_falls_back_to_mtgo_registry():
    assert set_name_for("MH1") == "Modern Horizons"
    assert set_name_for("usg") == "Urza's Saga Block"
    assert set_name_for("ZZZ") == "ZZZ"
