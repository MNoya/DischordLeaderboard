import asyncio

from bot.services import pod_draft_manager
from bot.services.lobby_embed import ready_cancel_notice, ready_check_unlinked_text, ready_status_banner
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


def test_initiate_blocks_odd_player_count():
    mgr, _ = _ready_manager([str(i) for i in range(7)])
    mgr.ready_check_active = False
    mgr.sio = type("_Sio", (), {"connected": True})()

    err = asyncio.run(mgr.initiate_ready_check(object()))

    assert err is not None
    assert "even" in err


def test_leaving_arms_grace_without_immediate_cancel():
    mgr, _ = _ready_manager([str(i) for i in range(8)])
    mgr.bot_user_id = "bot"
    aborts: list[str] = []

    async def _record(kind, *, decliner_name=None, detail=None):
        aborts.append(kind)

    async def _async_noop(*args, **kwargs):
        return None

    mgr._invalidate_ready_check = _record
    mgr._refresh_lobby_status = _async_noop
    mgr._refresh_mock_lobby = lambda *args, **kwargs: None
    mgr._sync_leaderboard_seeding = lambda *args, **kwargs: None

    remaining = [{"userID": str(i), "userName": str(i)} for i in range(7)]
    asyncio.run(mgr._on_session_users(remaining))

    assert aborts == []
    assert mgr.ready_check_active is True
    assert mgr._ready_grace_task is not None


def test_grace_aborts_when_player_stays_gone(monkeypatch):
    monkeypatch.setattr(pod_draft_manager, "_READY_GRACE_S", 0)
    mgr, _ = _ready_manager([str(i) for i in range(8)])
    mgr.expected_user_names = {str(i): f"p{i}" for i in range(8)}
    mgr.session_users = [u for u in mgr.session_users if u["userID"] != "7"]
    aborts: list[str] = []

    async def _record(kind, *, decliner_name=None, detail=None):
        aborts.append(detail)
        mgr.ready_check_active = False

    mgr._invalidate_ready_check = _record
    asyncio.run(mgr._ready_grace_countdown())

    assert len(aborts) == 1
    assert "p7" in aborts[0]


def test_grace_resumes_when_player_returns(monkeypatch):
    monkeypatch.setattr(pod_draft_manager, "_READY_GRACE_S", 0)
    mgr, _ = _ready_manager([str(i) for i in range(8)])
    aborts: list[str] = []

    async def _record(kind, *, decliner_name=None, detail=None):
        aborts.append(detail)

    mgr._invalidate_ready_check = _record
    asyncio.run(mgr._ready_grace_countdown())

    assert aborts == []


def test_roster_change_detail_pluralizes():
    assert "`Ada`" in pod_draft_manager._roster_change_detail(["Ada"], "joined")
    assert "2 players" in pod_draft_manager._roster_change_detail(["Ada", "Bo"], "left")
    assert pod_draft_manager._roster_change_detail([], "left")


def test_ready_cancel_notice_links_button_and_names_players():
    joined = ready_cancel_notice("joined", detail="`Ada` joined the lobby", retry_url="https://d/1")
    no_link = ready_cancel_notice("timeout", retry_url=None)

    assert "https://d/1" in joined and "Ada" in joined
    assert "http" not in no_link


def test_declined_banner_carries_initiator():
    lines, color = ready_status_banner("notready", decliner_name="Bob#1", initiated_by="Alice#2")

    assert any("Bob#1" in line for line in lines)
    assert any("Alice#2" in line for line in lines)


def test_blocker_passes_even_count_regardless_of_linking():
    mgr, _ = _ready_manager([str(i) for i in range(8)])
    mgr.ready_check_active = False
    mgr.sio = type("_Sio", (), {"connected": True})()

    assert mgr.ready_check_blocker() is None


def test_unlinked_confirm_text_names_the_seats():
    text = ready_check_unlinked_text(["Stranger#12345", "Wanderer#77"])

    assert "Stranger#12345" in text
    assert "Wanderer#77" in text
