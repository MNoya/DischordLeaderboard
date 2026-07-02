"""Fetch 17lands card ratings for the P0P1 contest and write the frontend ratings JSON.

Usage:
    python -m bot.scripts.fetch_p0p1_ratings --set-code MSH [--phase midway|final] [--end-date YYYY-MM-DD]

Writes frontend/src/data/fixtures/p0p1-ratings-{set_code_lower}.json. Commit the result
and redeploy to flip the contest into midway or final phase. dateRange is the exact
17lands query window (start_date/end_date), not decorative.
"""
from __future__ import annotations

import argparse
import json
from datetime import date
from pathlib import Path

from bot.services.seventeenlands import SeventeenLandsClient
from bot.sets import ALL_SETS

FORMAT = "PremierDraft"
FIXTURES_DIR = Path(__file__).parent.parent.parent / "frontend/src/data/fixtures"

GIHWR_FIELD = "ever_drawn_win_rate"
GIH_FIELD = "drawn_game_count"


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--set-code", required=True, help="17lands expansion code, e.g. MSH")
    parser.add_argument("--phase", choices=["midway", "final"], default="midway")
    parser.add_argument(
        "--end-date",
        default=date.today().isoformat(),
        help="End date of the 17lands data window (default: today)",
    )
    args = parser.parse_args()

    set_code = args.set_code.upper()
    matched = next((s for s in ALL_SETS if s.code == set_code), None)
    if matched is None:
        raise SystemExit(f"Unknown set code {set_code!r}. Add it to bot/sets.py first.")

    start = matched.start_date.isoformat()
    end = args.end_date
    output = FIXTURES_DIR / f"p0p1-ratings-{set_code.lower()}.json"

    client = SeventeenLandsClient()
    print(f"Fetching {set_code} {FORMAT} card ratings from 17lands...")
    raw = client.fetch_card_ratings(set_code, FORMAT, start_date=start, end_date=end)
    print(f"Received {len(raw)} card rows")

    cards = []
    missing = 0
    for row in raw:
        name = row.get("name")
        gihwr = row.get(GIHWR_FIELD)
        gih = row.get(GIH_FIELD) or 0
        if not name:
            missing += 1
            continue
        cards.append({
            "card_name": name,
            "gihwr": round(float(gihwr), 5) if gihwr is not None else None,
            "gih": int(gih),
        })

    if missing:
        print(f"Skipped {missing} rows with no card name")

    payload = {
        "setCode": set_code,
        "phase": args.phase,
        "dateRange": {"start": start, "end": end},
        "cards": cards,
    }
    output.write_text(json.dumps(payload, indent=2) + "\n")
    print(f"Wrote {len(cards)} cards → {output}")
    print(f"phase={args.phase!r}  dateRange={start} → {end}")


if __name__ == "__main__":
    main()
