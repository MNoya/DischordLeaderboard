"""Shared builder for the post-refresh bot-spam report.

Used by both the in-bot fallback tick and the standalone refresh cron job so the
bot-spam message reads identically regardless of which path ran the refresh.
"""
from __future__ import annotations


def format_elapsed(seconds: float) -> str:
    if seconds < 60:
        return f"{seconds:.1f}s"
    minutes, sec = divmod(int(round(seconds)), 60)
    return f"{minutes}m {sec}s"


def build_refresh_report(summary: dict, trigger: str) -> str:
    per_player = summary.get("per_player", [])
    n_players = len(per_player)
    elapsed = format_elapsed(summary.get("elapsed_s", 0.0))
    avg = f"{summary['elapsed_s'] / n_players:.1f}s avg" if n_players else ""
    label = trigger.title()

    body = f"🔄 {label} refresh complete · {elapsed} · {n_players} players"
    if avg:
        body += f" · {avg}"
    if summary["errors"]:
        body += (
            f"\nUpdated: {summary['updated']} · "
            f"Invalidated: {summary['invalidated']} · "
            f"Errors: {summary['errors']}"
        )
    unknown = summary.get("unknown_formats") or {}
    if unknown:
        tally = ", ".join(f"`{fmt}` ×{n}" for fmt, n in sorted(unknown.items(), key=lambda kv: (-kv[1], kv[0])))
        body += f"\n⚠️ New format(s) observed (stored, not scoring): {tally}"
    unrouted = summary.get("unrouted_expansions") or {}
    if unrouted:
        tally = ", ".join(f"`{exp}` ×{n}" for exp, n in sorted(unrouted.items(), key=lambda kv: (-kv[1], kv[0])))
        body += f"\n⚠️ Unrouted expansion(s) — events stored without a set (add to bot/sets.py): {tally}"
    return body
