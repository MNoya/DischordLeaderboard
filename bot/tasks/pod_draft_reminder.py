"""APScheduler entry point fired 5 minutes before a pod draft starts.

Milestone 3 ships a minimal stub that logs the firing. Milestone 4 fills in the
real body: re-fetch the sesh embed, resolve attendee Discord IDs via guild
member lookup, post the ping + Draftmancer link in the thread, instantiate
PodDraftManager and connect to the Draftmancer websocket.

Decoupled from the listener so the scheduler holds a stable reference even
across cog reloads.
"""
from __future__ import annotations

import logging


log = logging.getLogger(__name__)


async def fire_reminder(event_id: str) -> None:
    """T-5 callback. Implemented in milestone 4."""
    log.info("pod-draft T-5 reminder fired for event_id=%s (stub)", event_id)
