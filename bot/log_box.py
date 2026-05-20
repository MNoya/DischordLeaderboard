from __future__ import annotations

import unicodedata


def display_width(s: str) -> int:
    return sum(2 if unicodedata.east_asian_width(c) in ("W", "F") else 1 for c in s)


def log_box(rows: list[str], centered: frozenset[int] = frozenset()) -> str:
    """Return a ╔═══╗ box string suitable for a single log.info() call.

    Rows whose index appears in ``centered`` are horizontally centred; all
    others are left-aligned. Leading blank line included so the box starts on
    its own line after the log prefix of the first entry.
    """
    w = max(display_width(r) for r in rows) + 4

    def _row(i: int, text: str) -> str:
        if i in centered:
            total = w - 4 - display_width(text)
            left = total // 2
            return f"║  {' ' * left}{text}{' ' * (total - left)}  ║"
        return f"║  {text}{' ' * (w - 4 - display_width(text))}  ║"

    return "\n".join(["", f"╔{'═' * w}╗", *[_row(i, r) for i, r in enumerate(rows)], f"╚{'═' * w}╝"])
