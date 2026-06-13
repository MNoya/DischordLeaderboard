"""Generate white-on-transparent set-symbol PNGs for the leaderboard from keyrune.

Keyrune ships each set glyph as a monochrome ``#444`` SVG; the leaderboard renders
white symbols on dark surfaces (Discord unfurls, the site), so each glyph is
recolored to white and rasterized to PNG. Run with no args to (re)generate every
set in ``bot.sets.ALL_SETS``, or pass specific codes (e.g. ``MSH SOS``).

Requires ``inkscape`` (rasterizer) and ``pngquant`` (optional optimization) on PATH.
"""
from __future__ import annotations

import shutil
import subprocess
import sys
import urllib.error
import urllib.request
from pathlib import Path

from bot.sets import ALL_SETS

KEYRUNE_SVG_URL = "https://cdn.jsdelivr.net/gh/andrewgioia/keyrune@latest/svg/{code}.svg"
OUTPUT_DIR = Path(__file__).resolve().parents[2] / "frontend" / "public" / "set-symbols"
SYMBOL_PX = 256


def generate(codes: list[str]) -> tuple[list[str], list[str]]:
    """Generate a PNG for each code; return ``(generated, missing)`` where missing codes have no keyrune glyph."""
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    generated: list[str] = []
    missing: list[str] = []
    for code in codes:
        svg = _fetch_white_svg(code)
        if svg is None:
            missing.append(code)
            continue
        _rasterize(code, svg)
        generated.append(code)
    if generated:
        _optimize([OUTPUT_DIR / f"{code.lower()}.png" for code in generated])
    return generated, missing


def _fetch_white_svg(code: str) -> str | None:
    url = KEYRUNE_SVG_URL.format(code=code.lower())
    try:
        with urllib.request.urlopen(url, timeout=20) as resp:
            raw = resp.read().decode("utf-8")
    except urllib.error.HTTPError as e:
        if e.code == 404:
            return None
        raise
    return raw.replace("#444", "#ffffff")


def _rasterize(code: str, svg: str) -> None:
    """Snap-confined inkscape only resolves absolute paths, so OUTPUT_DIR stays fully resolved."""
    src = OUTPUT_DIR / f"_src_{code.lower()}.svg"
    png = OUTPUT_DIR / f"{code.lower()}.png"
    src.write_text(svg, encoding="utf-8")
    try:
        subprocess.run(
            ["inkscape", str(src), "--export-type=png", f"--export-filename={png}",
             "-w", str(SYMBOL_PX), "-h", str(SYMBOL_PX)],
            check=True, capture_output=True,
        )
    finally:
        src.unlink(missing_ok=True)


def _optimize(paths: list[Path]) -> None:
    if shutil.which("pngquant") is None:
        return
    subprocess.run(
        ["pngquant", "--quality=80-100", "--force", "--ext", ".png", "--strip", *map(str, paths)],
        check=False, capture_output=True,
    )


def main(argv: list[str]) -> int:
    if shutil.which("inkscape") is None:
        print("inkscape not found on PATH; install it to rasterize set symbols", file=sys.stderr)
        return 1
    codes = [arg.upper() for arg in argv] or [s.code for s in ALL_SETS]
    generated, missing = generate(codes)
    print(f"generated {len(generated)}: {', '.join(generated) or '(none)'}")
    if missing:
        print(f"no keyrune glyph, skipped: {', '.join(missing)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
