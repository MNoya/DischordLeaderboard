import pytest

from bot.services.media_sync import classify_category


@pytest.mark.parametrize(
    "playlists,title,kind,expected",
    [
        ([], "Murders at Karlov Manor Draft! Opening One of the Best Rares!", "video", "Draft"),
        ([], "The Most Underrated Rares in Strixhaven Draft", "video", "Draft"),
        (["Secrets of Strixhaven"], "Resonating Lute Deck | Secrets Of Strixhaven Draft", "video", "Draft"),
        (["Set Review"], "Power Ranking Every Common", "video", "Set Review"),
        ([], "WOE Set Review: Every Uncommon", "video", "Set Review"),
        ([], "Bloomburrow Tier List", "video", "Set Review"),
        ([], "Lorwyn Eclipsed Primer", "video", "First Impressions"),
        ([], "State of the Format: SOS Three Weeks In", "video", "Metagame"),
        ([], "Draft-Along: Reading Every Signal", "video", "Draft"),
        ([], "Top 5 Ways to Use the Wheel", "episode", "Evergreen"),
        (["Draft Videos"], "Set Review: Best Commons", "video", "Draft"),
    ],
)
def test_classify_category(playlists, title, kind, expected):
    assert classify_category(playlists, title, kind) == expected


def test_set_review_no_longer_steals_draft_titles_mentioning_rarities():
    rarity_draft_titles = [
        "These Lorwyn Uncommons are Being Underhyped!",
        "Please Read All the Words on Your Rares",
        "The one card that beats rares they DON'T want you to know about | Bloomburrow Draft",
    ]

    categories = [classify_category([], title, "video") for title in rarity_draft_titles]

    assert categories == ["Draft", "Draft", "Draft"]
