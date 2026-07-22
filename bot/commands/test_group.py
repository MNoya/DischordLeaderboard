"""Owner-only `!test <word>` prefix group.

Manual test triggers register here as subcommands and reuse the production builders they
exercise, so test output can't drift from what the real flow sends. Words that match no
subcommand fall through to the testlobby state handler when it's registered.
invoke_without_command=True means group checks don't run for subcommands — each
subcommand carries its own @commands.is_owner().
"""
from __future__ import annotations

from typing import Awaitable, Callable

from discord.ext import commands


HALL_OF_FAME = (
    "Finkel", "LSV", "The Hump", "Paolo", "Shota", "Reid", "Chapin", "JED",
    "Nassif", "Huey", "Kibler", "Levy", "Nakamura", "Karsten", "Juza", "Owen",
)

TestFallback = Callable[[commands.Context, str, str], Awaitable[None]]

_fallback: TestFallback | None = None


def register_test_fallback(handler: TestFallback) -> None:
    global _fallback
    _fallback = handler


@commands.group(name="test", invoke_without_command=True)
@commands.is_owner()
async def test_group(ctx: commands.Context, state: str = "", extra: str = "") -> None:
    if _fallback is not None:
        await _fallback(ctx, state, extra)
        return
    names = ", ".join(sorted(f"`!test {command.name}`" for command in test_group.commands))
    await ctx.send(f"Available tests: {names}")


async def setup(bot: commands.Bot) -> None:
    bot.add_command(test_group)
