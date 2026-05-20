"""public_player_format_breakdown: add Qualifier Weekend + Play-In Trad Sealed formats

17lands ships three SOS Sealed variants the original CASE didn't enumerate:
Qualifier_D1_Sealed, Qualifier_D2_Sealed, QualifierPlayInTradSealed. Extend
the IN list so leaderboard scoring picks them up. Mirrors the Python-side
addition to ``DEFAULT_QUEUE_GROUPS["Sealed"]``.

Revision ID: d1w2x3y4z5a6
Revises: c0v1w2x3y4z5
Create Date: 2026-05-19
"""
from typing import Sequence, Union

from alembic import op


revision: str = "d1w2x3y4z5a6"
down_revision: Union[str, None] = "c0v1w2x3y4z5"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


_FORMAT_LABEL_CASE_NEW = """\
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


_FORMAT_LABEL_CASE_OLD = """\
CASE
    WHEN ps.format = 'PremierDraft' THEN 'Premier'
    WHEN ps.format = 'TradDraft' THEN 'Trad'
    WHEN ps.format IN ('Sealed', 'TradSealed', 'ArenaDirect_Sealed', 'QualifierPlayInSealed') THEN 'Sealed'
    WHEN ps.format IN ('QuickDraft', 'PickTwoDraft', 'Emblem_QuickDraft') THEN 'Quick'
    WHEN ps.format = 'LimitedChampionshipQualifier_Draft1' THEN 'LCQ Draft 1'
    WHEN ps.format = 'LimitedChampionshipQualifier_Draft2' THEN 'LCQ Draft 2'
    ELSE NULL
END"""


def _create_view(label_case: str) -> None:
    op.execute(f"""
        CREATE OR REPLACE VIEW public_player_format_breakdown AS
        WITH grouped AS (
            SELECT
                s.code AS set_code,
                p.slug,
                {label_case} AS format_label,
                SUM(ps.events)::int AS events,
                SUM(ps.wins)::int AS wins,
                SUM(ps.losses)::int AS losses,
                SUM(ps.trophies)::int AS trophies
            FROM player_stats ps
            JOIN players p ON p.id = ps.player_id
            JOIN sets s ON s.id = ps.set_id
            WHERE p.active = true
            GROUP BY s.code, p.slug, {label_case}
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


def upgrade() -> None:
    _create_view(_FORMAT_LABEL_CASE_NEW)


def downgrade() -> None:
    _create_view(_FORMAT_LABEL_CASE_OLD)
