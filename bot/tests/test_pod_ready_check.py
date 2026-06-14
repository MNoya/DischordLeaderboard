import asyncio

from bot.services.pod_draft_manager import PodDraftManager


def _ready_manager(user_ids: list[str]) -> tuple[PodDraftManager, list[bool]]:
    mgr = PodDraftManager(object(), "evt", "sid", 123, "SOS", len(user_ids))
    mgr.session_users = [{"userID": uid, "userName": uid} for uid in user_ids]
    mgr.expected_user_ids = set(user_ids)
    mgr.ready_users = set(user_ids)
    mgr.ready_check_active = True
    completed: list[bool] = []

    async def _record_complete():
        completed.append(True)
        mgr.ready_check_active = False

    mgr._complete_ready_check = _record_complete
    return mgr, completed


def test_completes_when_all_present_and_ready():
    mgr, completed = _ready_manager([str(i) for i in range(8)])

    asyncio.run(mgr._maybe_complete_ready_check())

    assert completed == [True]


def test_holds_when_a_readied_player_left_and_prunes_them():
    mgr, completed = _ready_manager([str(i) for i in range(8)])
    mgr.session_users = [u for u in mgr.session_users if u["userID"] != "7"]

    asyncio.run(mgr._maybe_complete_ready_check())

    assert completed == []
    assert "7" not in mgr.ready_users


def test_completes_after_the_player_returns_and_re_readies():
    mgr, completed = _ready_manager([str(i) for i in range(8)])
    mgr.session_users = [u for u in mgr.session_users if u["userID"] != "7"]
    asyncio.run(mgr._maybe_complete_ready_check())

    mgr.session_users.append({"userID": "7", "userName": "7"})
    mgr.ready_users.add("7")
    asyncio.run(mgr._maybe_complete_ready_check())

    assert completed == [True]
