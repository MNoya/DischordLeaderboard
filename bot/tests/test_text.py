import pytest

from bot.text import link_with_emoji, partition_emoji


@pytest.mark.parametrize(
    "text,leading,core,trailing",
    [
        ("Aetherdrift (DFT) Pod Draft", "", "Aetherdrift (DFT) Pod Draft", ""),
        ("🏁 🏎️ Aetherdrift (DFT) Pod Draft", "🏁 🏎️", "Aetherdrift (DFT) Pod Draft", ""),
        ("Aetherdrift Pod Draft 🏁", "", "Aetherdrift Pod Draft", "🏁"),
        ("🏁 Aetherdrift 🏎️ Pod Draft 🚀", "🏁", "Aetherdrift Pod Draft", "🚀"),
        ("Aether 🏎️ drift Draft", "", "Aether drift Draft", ""),
        ("<:llu:123> Aetherdrift", "<:llu:123>", "Aetherdrift", ""),
    ],
)
def test_partition_emoji_splits_leading_trailing_and_drops_interior(text, leading, core, trailing):
    assert partition_emoji(text) == (leading, core, trailing)


def test_link_with_emoji_moves_leading_emoji_outside_the_label():
    link = link_with_emoji("🏁 🏎️ Aetherdrift (DFT) Pod Draft", "https://x/9")

    assert link == "🏁 🏎️ [Aetherdrift (DFT) Pod Draft](https://x/9)"


def test_link_with_emoji_keeps_trailing_emoji_after_the_label():
    link = link_with_emoji("Aetherdrift Pod Draft 🚀", "https://x/9")

    assert link == "[Aetherdrift Pod Draft](https://x/9) 🚀"


def test_link_with_emoji_leaves_emoji_free_names_untouched():
    link = link_with_emoji("FIN Pod Draft #1", "https://x/9")

    assert link == "[FIN Pod Draft #1](https://x/9)"
