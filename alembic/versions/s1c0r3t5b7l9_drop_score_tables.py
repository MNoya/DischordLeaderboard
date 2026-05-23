"""Drop precomputed score tables; views expose aggregates only

Score is computed on the fly in Python (bot) and JS (frontend) from
scoring_buckets.json. The derived tables (player_set_scores,
player_archetype_scores, player_format_archetype_scores) and the score/rank
columns on the public views are removed.

public_leaderboard now exposes per-(player, set) aggregates only — callers
compute score + rank themselves. The two archetype-leaderboard views are
dropped; frontend aggregates from public_player_draft_events instead. The
format-breakdown view's CASE is regenerated from scoring_buckets.json so the
new Arena Open / FIAB / etc. formats bucket correctly.

Revision ID: s1c0r3t5b7l9
Revises: j8c1d2p3r4s5
Create Date: 2026-05-23
"""
import json
from pathlib import Path
from typing import Sequence, Union

from alembic import op


revision: str = "s1c0r3t5b7l9"
down_revision: Union[str, None] = "j8c1d2p3r4s5"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


_AVATAR_URL_SQL = """\
CASE WHEN p.avatar_hash IS NOT NULL AND p.discord_id IS NOT NULL
    THEN 'https://cdn.discordapp.com/avatars/' || p.discord_id || '/' || p.avatar_hash || '.png?size=128'
    ELSE NULL
END"""


def upgrade() -> None:
    op.execute("DROP VIEW IF EXISTS public_player_format_archetype_leaderboard;")
    op.execute("DROP VIEW IF EXISTS public_archetype_leaderboard;")
    op.execute("DROP VIEW IF EXISTS public_leaderboard;")
    op.execute("DROP TABLE IF EXISTS player_format_archetype_scores;")
    op.execute("DROP TABLE IF EXISTS player_archetype_scores;")
    op.execute("DROP TABLE IF EXISTS player_set_scores;")

    op.execute(f"""
        CREATE VIEW public_leaderboard AS
        SELECT
            s.code AS set_code,
            p.slug,
            p.display_name,
            {_AVATAR_URL_SQL} AS avatar_url,
            COALESCE(SUM(ps.events), 0)::int AS events,
            COALESCE(SUM(ps.wins), 0)::int AS wins,
            COALESCE(SUM(ps.losses), 0)::int AS losses,
            COALESCE(SUM(ps.trophies), 0)::int AS trophies,
            MAX(ps.last_fetched_at) AS last_calculated_at
        FROM players p
        JOIN player_stats ps ON ps.player_id = p.id
        JOIN sets s ON s.id = ps.set_id
        WHERE p.active = true
        GROUP BY s.code, p.slug, p.display_name, p.avatar_hash, p.discord_id
        HAVING SUM(ps.events) > 0;
    """)
    op.execute("GRANT SELECT ON public_leaderboard TO anon;")

    op.execute("DROP VIEW IF EXISTS public_player_format_breakdown;")
    op.execute(f"""
        CREATE VIEW public_player_format_breakdown AS
        WITH grouped AS (
            SELECT
                s.code AS set_code,
                p.slug,
                {_format_label_case_from_buckets()} AS format_label,
                SUM(ps.events)::int AS events,
                SUM(ps.wins)::int AS wins,
                SUM(ps.losses)::int AS losses,
                SUM(ps.trophies)::int AS trophies
            FROM player_stats ps
            JOIN players p ON p.id = ps.player_id
            JOIN sets s ON s.id = ps.set_id
            WHERE p.active = true
            GROUP BY s.code, p.slug, {_format_label_case_from_buckets()}
        )
        SELECT set_code, slug, format_label, events, wins, losses, trophies
        FROM grouped
        WHERE format_label IS NOT NULL;
    """)
    op.execute("GRANT SELECT ON public_player_format_breakdown TO anon;")


def downgrade() -> None:
    raise NotImplementedError(
        "Intentionally one-way: dropping precomputed score tables. To roll back, "
        "restore a pre-migration backup and revert the bot/frontend code that "
        "computes scores on the fly."
    )


def _format_label_case_from_buckets() -> str:
    """SQL CASE mapping raw format → group label, sourced from scoring_buckets.json.

    Migration runs once; embedding the case here keeps the JSON the single
    source of truth without runtime SQL dependency on the JSON file.
    """
    buckets_path = Path(__file__).resolve().parents[2] / "scoring_buckets.json"
    config = json.loads(buckets_path.read_text())
    branches = []
    for g in config["groups"]:
        quoted = ", ".join(f"'{fmt}'" for fmt in g["formats"])
        branches.append(f"WHEN ps.format IN ({quoted}) THEN '{g['label']}'")
    return "CASE\n            " + "\n            ".join(branches) + "\n            ELSE NULL\n        END"
