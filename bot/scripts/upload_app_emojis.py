"""Generate and upload Discord application emojis from the keyrune / mana icon fonts.

Each argument is ``source:glyph[:name]`` — source is ``keyrune`` or ``mana``, glyph is the icon's
filename in that font's ``svg/`` directory, name is the application-emoji name (defaults to the
glyph with non-alphanumeric characters stripped). Glyphs are recolored white and rasterized like
the site's set symbols, then uploaded to the application DISCORD_BOT_TOKEN belongs to, so the same
invocation seeds the test and production apps. An emoji whose name already exists is skipped;
pass ``--force`` to replace it.

Example:
    python -m bot.scripts.upload_app_emojis keyrune:8ed mana:dfc-day:dfcday mana:dfc-night:dfcnight
"""
from __future__ import annotations

import base64
import re
import shutil
import sys
import tempfile
import urllib.error
import urllib.request
from pathlib import Path

import requests

from bot.config import settings
from bot.scripts.generate_set_symbols import rasterize, squarify

API_BASE = "https://discord.com/api/v10"
SVG_URLS = {
    "keyrune": "https://cdn.jsdelivr.net/gh/andrewgioia/keyrune@latest/svg/{glyph}.svg",
    "mana": "https://cdn.jsdelivr.net/gh/andrewgioia/mana@latest/svg/{glyph}.svg",
}
EMOJI_PX = 128


def upload(specs: list[tuple[str, str, str]], force: bool) -> int:
    token = settings.discord_bot_token.get_secret_value() if settings.discord_bot_token else None
    if not token:
        print("DISCORD_BOT_TOKEN is not set", file=sys.stderr)
        return 1
    headers = {"Authorization": f"Bot {token}"}
    app_id = requests.get(f"{API_BASE}/applications/@me", headers=headers, timeout=20).json()["id"]
    emoji_url = f"{API_BASE}/applications/{app_id}/emojis"
    existing = {
        e["name"]: e["id"]
        for e in requests.get(emoji_url, headers=headers, timeout=20).json()["items"]
    }

    failures = 0
    for source, glyph, name in specs:
        if name in existing:
            if not force:
                print(f"{name}: already exists, skipped (use --force to replace)")
                continue
            requests.delete(f"{emoji_url}/{existing[name]}", headers=headers, timeout=20)
        png = _render_glyph(source, glyph, name)
        if png is None:
            print(f"{name}: no {source} glyph named {glyph!r}", file=sys.stderr)
            failures += 1
            continue
        image = f"data:image/png;base64,{base64.b64encode(png).decode('ascii')}"
        response = requests.post(emoji_url, headers=headers, json={"name": name, "image": image}, timeout=20)
        if response.ok:
            print(f"{name}: uploaded ({source}:{glyph})")
        else:
            print(f"{name}: upload failed — {response.status_code} {response.text}", file=sys.stderr)
            failures += 1
    return 1 if failures else 0


def _render_glyph(source: str, glyph: str, name: str) -> bytes | None:
    url = SVG_URLS[source].format(glyph=glyph)
    try:
        with urllib.request.urlopen(url, timeout=20) as resp:
            raw = resp.read().decode("utf-8")
    except urllib.error.HTTPError as e:
        if e.code == 404:
            return None
        raise
    svg = squarify(raw.replace("#444", "#ffffff"))
    workdir = Path(__file__).resolve().parent
    with tempfile.TemporaryDirectory(dir=workdir) as tmp:
        png_path = Path(tmp) / f"{name}.png"
        rasterize(svg, png_path, EMOJI_PX)
        return png_path.read_bytes()


def parse_spec(arg: str) -> tuple[str, str, str] | None:
    parts = arg.split(":")
    if len(parts) not in (2, 3) or parts[0] not in SVG_URLS:
        return None
    source, glyph = parts[0], parts[1]
    name = parts[2] if len(parts) == 3 else re.sub(r"[^A-Za-z0-9_]", "", glyph)
    return source, glyph, name


def main(argv: list[str]) -> int:
    force = "--force" in argv
    args = [arg for arg in argv if arg != "--force"]
    if not args:
        print("usage: upload_app_emojis [--force] source:glyph[:name] ...", file=sys.stderr)
        return 1
    if shutil.which("inkscape") is None:
        print("inkscape not found on PATH", file=sys.stderr)
        return 1
    specs = []
    for arg in args:
        spec = parse_spec(arg)
        if spec is None:
            print(f"bad spec {arg!r}; expected source:glyph[:name] with source keyrune|mana", file=sys.stderr)
            return 1
        specs.append(spec)
    return upload(specs, force)


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
