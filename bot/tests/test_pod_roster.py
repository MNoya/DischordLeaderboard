import pytest

from bot.services.pod_draft_manager import PodDraftManager


def _manager(session_users: list[dict], draft_log: dict | None) -> PodDraftManager:
    mgr = PodDraftManager(object(), "evt", "sid", 123, "SOS", 8)
    mgr.session_users = session_users
    if draft_log is not None:
        mgr.draft_logs = {"Ava": draft_log}
    return mgr


_SESSION_WITH_SPECTATOR = [
    {"userID": "1", "userName": "Ava"},
    {"userID": "2", "userName": "Bram"},
    {"userID": "3", "userName": "DisChordBot"},
    {"userID": "4", "userName": "LateSpectator"},
]

_LOG_TWO_SEATS = {"users": {"u1": {"userName": "Ava"}, "u2": {"userName": "Bram"}}}


@pytest.mark.parametrize(
    "session_users, draft_log, expected",
    [
        (_SESSION_WITH_SPECTATOR, _LOG_TWO_SEATS, ["Ava", "Bram"]),
        (_SESSION_WITH_SPECTATOR, None, ["Ava", "Bram", "LateSpectator"]),
        (_SESSION_WITH_SPECTATOR, {"users": {}}, ["Ava", "Bram", "LateSpectator"]),
        (_SESSION_WITH_SPECTATOR, {"users": {"u1": {"userName": ""}, "u2": "junk"}}, ["Ava", "Bram", "LateSpectator"]),
        ([], _LOG_TWO_SEATS, ["Ava", "Bram"]),
        ([], None, []),
    ],
    ids=["log-wins", "no-log-falls-back", "empty-log-users", "malformed-log-users", "log-only", "nothing"],
)
def test_snapshot_tournament_roster(session_users, draft_log, expected):
    mgr = _manager(session_users, draft_log)

    roster = mgr._snapshot_tournament_roster()

    assert roster == expected
