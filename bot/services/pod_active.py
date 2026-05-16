"""Registry of active PodDraftManagers keyed by event_id.

Lives in its own module so pod_draft_manager and pod_tournament can both import it without a circular dependency.
"""
from __future__ import annotations

ACTIVE_POD_MANAGERS = {}
