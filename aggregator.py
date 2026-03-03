import requests

from collections import defaultdict
from typing import Callable, Iterable

START_DATE = "2026-01-20"  # ECL start date
SET_CODE = "ECL"  # Alchemy: Y26ECL


def get_draft_data(user_id):
    url = f"https://www.17lands.com/user/data/{user_id}?start_date={START_DATE}"
    response = requests.get(url)
    return response.json()['drafts']


class DraftAggregator:
    def __init__(self, events: Iterable[dict]):
        self.events = events

    def aggregate(self, key: str, predicate: Callable[[dict], bool] | None = None):
        result = defaultdict(lambda: {
            "events": 0,
            "wins": 0,
            "losses": 0,
            "games": 0,
            "winrate": 0,
            "avg_wins": 0,
            "trophies": 0,
            "trophy_rate": 0,
        })

        events = self._filtered(predicate)

        for e in events:
            value = e.get(key)
            value = value or "Unknown"

            r = result[value]
            r["events"] += 1
            r["wins"] += e["wins"]
            r["losses"] += e["losses"]
            r["games"] += e["wins"] + e["losses"]

            if e["event_wins"]:
                r["trophies"] += 1

        for stats in result.values():
            if stats["games"]:
                stats["winrate"] = round(stats["wins"] / stats["games"], 3)
            if stats["events"]:
                stats["avg_wins"] = round(stats["wins"] / stats["events"], 2)
                stats["trophy_rate"] = round(stats["trophies"] / stats["events"], 3)

        return dict(result)

    def overall(self, predicate: Callable[[dict], bool] | None = None):
        events = self._filtered(predicate)

        total_events = len(events)
        total_wins = sum(e["wins"] for e in events)
        total_losses = sum(e["losses"] for e in events)
        total_games = total_wins + total_losses
        trophies = sum(1 for e in events if e["wins"] == 7)

        return {
            "events": total_events,
            "wins": total_wins,
            "losses": total_losses,
            "games": total_games,
            "winrate": round(total_wins / total_games, 3) if total_games else 0,
            "avg_wins": round(total_wins / total_events, 2) if total_events else 0,
            "trophies": trophies,
            "trophy_rate": round(trophies / total_events, 3) if total_events else 0,
        }

    # -------------------------
    # Convenience Filters
    # -------------------------
    def overall_ECL(self):
        return self.overall(lambda e: "ECL" in e['expansion'])

    def aggregate_ECL(self):
        return self.aggregate("format", lambda e: "ECL" in e["expansion"])

    def expansion(self, expansion_code: str):
        return self.overall(lambda e: e["expansion"] == expansion_code)

    def format(self, format_name: str):
        return self.overall(lambda e: e["format"] == format_name)

    def account(self, account_name: str):
        return self.overall(lambda e: e["account"] == account_name)

    # -------------------------
    # Helpers
    # -------------------------
    def _filtered(self, predicate: Callable[[dict], bool] | None):
        return [e for e in self.events if predicate(e)] if predicate else self.events
