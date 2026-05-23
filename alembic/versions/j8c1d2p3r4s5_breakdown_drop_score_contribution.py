"""public_player_format_breakdown: drop score_contribution, add ContenderDraft

The view's score_contribution column had drifted from bot/scoring.py — it used
Trad=9 / Quick=3 instead of the canonical 8 / 4, so the breakdown numbers on
the player page didn't sum to the headline score. Score is now computed
client-side from the bucket aggregates using the same formula as the rest of
the app, eliminating the third sync point.

Also folds ContenderDraft (new SOS format) into the Premier bucket.

Revision ID: j8c1d2p3r4s5
Revises: i7m8w9k0l1n2
Create Date: 2026-05-23
"""
from typing import Sequence, Union

from alembic import op


revision: str = "j8c1d2p3r4s5"
down_revision: Union[str, None] = "i7m8w9k0l1n2"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


_FORMAT_LABEL_CASE_NEW = """\
CASE
    WHEN ps.format IN ('PremierDraft', 'ContenderDraft') THEN 'Premier'
    WHEN ps.format = 'TradDraft' THEN 'Trad'
    WHEN ps.format IN (
        'Sealed',
        'TradSealed',
        'ArenaDirect_Sealed',
        'QualifierPlayInSealed',
        'QualifierPlayInTradSealed',
        'Qualifier_D1_Sealed',
        'Qualifier_D2_Sealed'
    ) THEN 'Sealed'
    WHEN ps.format IN ('QuickDraft', 'PickTwoDraft', 'Emblem_QuickDraft') THEN 'Quick'
    WHEN ps.format = 'LimitedChampionshipQualifier_Draft1' THEN 'LCQ Draft 1'
    WHEN ps.format = 'LimitedChampionshipQualifier_Draft2' THEN 'LCQ Draft 2'
    ELSE NULL
END"""


_FORMAT_LABEL_CASE_OLD = """\
CASE
    WHEN ps.format = 'PremierDraft' THEN 'Premier'
    WHEN ps.format = 'TradDraft' THEN 'Trad'
    WHEN ps.format IN (
        'Sealed',
        'TradSealed',
        'ArenaDirect_Sealed',
        'QualifierPlayInSealed',
        'QualifierPlayInTradSealed',
        'Qualifier_D1_Sealed',
        'Qualifier_D2_Sealed'
    ) THEN 'Sealed'
    WHEN ps.format IN ('QuickDraft', 'PickTwoDraft', 'Emblem_QuickDraft') THEN 'Quick'
    WHEN ps.format = 'LimitedChampionshipQualifier_Draft1' THEN 'LCQ Draft 1'
    WHEN ps.format = 'LimitedChampionshipQualifier_Draft2' THEN 'LCQ Draft 2'
    ELSE NULL
END"""


def upgrade() -> None:
    op.execute("DROP VIEW IF EXISTS public_player_format_breakdown;")
    op.execute(f"""
        CREATE VIEW public_player_format_breakdown AS
        WITH grouped AS (
            SELECT
                s.code AS set_code,
                p.slug,
                {_FORMAT_LABEL_CASE_NEW} AS format_label,
                SUM(ps.events)::int AS events,
                SUM(ps.wins)::int AS wins,
                SUM(ps.losses)::int AS losses,
                SUM(ps.trophies)::int AS trophies
            FROM player_stats ps
            JOIN players p ON p.id = ps.player_id
            JOIN sets s ON s.id = ps.set_id
            WHERE p.active = true
            GROUP BY s.code, p.slug, {_FORMAT_LABEL_CASE_NEW}
        )
        SELECT set_code, slug, format_label, events, wins, losses, trophies
        FROM grouped
        WHERE format_label IS NOT NULL;
    """)
    op.execute("GRANT SELECT ON public_player_format_breakdown TO anon;")


def downgrade() -> None:
    op.execute("DROP VIEW IF EXISTS public_player_format_breakdown;")
    op.execute(f"""
        CREATE VIEW public_player_format_breakdown AS
        WITH grouped AS (
            SELECT
                s.code AS set_code,
                p.slug,
                {_FORMAT_LABEL_CASE_OLD} AS format_label,
                SUM(ps.events)::int AS events,
                SUM(ps.wins)::int AS wins,
                SUM(ps.losses)::int AS losses,
                SUM(ps.trophies)::int AS trophies
            FROM player_stats ps
            JOIN players p ON p.id = ps.player_id
            JOIN sets s ON s.id = ps.set_id
            WHERE p.active = true
            GROUP BY s.code, p.slug, {_FORMAT_LABEL_CASE_OLD}
        )
        SELECT
            set_code,
            slug,
            format_label,
            events,
            wins,
            losses,
            trophies,
            ROUND(
                CASE
                    WHEN format_label = 'LCQ Draft 2' AND (wins + losses) > 0 AND wins > 0
                        THEN wins::numeric * (wins::numeric / (wins + losses)) * 10
                    WHEN format_label IN ('Premier','Trad','Sealed','Quick','LCQ Draft 1')
                         AND trophies > 0 AND events > 0
                        THEN trophies::numeric
                             * (CASE format_label
                                    WHEN 'Premier' THEN 10
                                    WHEN 'Trad' THEN 9
                                    WHEN 'Sealed' THEN 8
                                    WHEN 'Quick' THEN 3
                                    WHEN 'LCQ Draft 1' THEN 30
                                END)
                             * (trophies::numeric / events)
                             * (trophies::numeric / (trophies + 2))
                    ELSE 0
                END,
                2
            ) AS score_contribution
        FROM grouped
        WHERE format_label IS NOT NULL;
    """)
    op.execute("GRANT SELECT ON public_player_format_breakdown TO anon;")
