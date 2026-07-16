import pytest

from bot.commands.pod_queue import notify_role
from bot.services.pod_schedule import EARLY_POD_ROLE_NAME, POD_QUEUE_ROLE_NAME


@pytest.mark.parametrize("choice, expected", [
    (None, POD_QUEUE_ROLE_NAME),
    (POD_QUEUE_ROLE_NAME, POD_QUEUE_ROLE_NAME),
    (EARLY_POD_ROLE_NAME, EARLY_POD_ROLE_NAME),
    ("none", None),
])
def test_notify_role_resolves_choice(choice, expected):
    assert notify_role(choice) == expected
