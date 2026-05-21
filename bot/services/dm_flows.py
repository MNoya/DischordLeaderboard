"""Shared in-flight tracker for DM-driven token flows (/join, /relink).

The auto-link DM listener checks this set to avoid double-handling a reply
that an active wait_for in a slash command will already consume.
"""
from __future__ import annotations

from contextlib import contextmanager

IN_FLIGHT_DM_FLOWS: set[str] = set()


@contextmanager
def dm_flow(discord_id: str):
    IN_FLIGHT_DM_FLOWS.add(discord_id)
    try:
        yield
    finally:
        IN_FLIGHT_DM_FLOWS.discard(discord_id)


def is_in_flight(discord_id: str) -> bool:
    return discord_id in IN_FLIGHT_DM_FLOWS
