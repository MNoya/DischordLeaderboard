from bot.services.pod_team_vote import (
    TEAM_VOTE_PROMPT,
    build_team_vote_offer_embed,
    team_vote_needed,
)


def test_team_vote_needed_is_a_majority_of_the_pod():
    assert team_vote_needed(4) == 3
    assert team_vote_needed(6) == 4
    assert team_vote_needed(8) == 5
    assert team_vote_needed(10) == 6


def test_offer_embed_states_the_vote_target_and_has_no_votes_field_yet():
    embed = build_team_vote_offer_embed([], needed=4)

    assert embed.title == TEAM_VOTE_PROMPT
    assert "4" in embed.description
    assert embed.fields == []


def test_offer_embed_lists_voters_in_a_votes_field():
    embed = build_team_vote_offer_embed(["Ava", "Bram", "Cara"], needed=4)

    field = embed.fields[0]
    assert field.name == "Votes (3)"
    assert field.value == "Ava, Bram, Cara"
