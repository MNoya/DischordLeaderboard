"""Single source of truth for shared user-facing message strings, used across multiple commands and listeners."""

MSG_JOINED_LEADERBOARD = "🎉 Welcome aboard! Run `/help` to see what you can do."
MSG_NOT_REGISTERED = "You're not on the leaderboard yet. Run `/join` or `/link-17lands` first."
MSG_NOT_ON_BOARD = "You're not on the leaderboard."
MSG_NOW_HIDDEN = "🕵️ Your rank is now hidden. Your profile and trophies stay visible."
MSG_ALREADY_HIDDEN = "You're already off the rankings. Run `/join` to be ranked again."
MSG_RANKED_AGAIN = "👋 You're ranked again. Your stats are back in the standings."
MSG_ADMIN_ONLY = "This command is reserved for the bot admin."

MSG_MOCK_NOT_TEXT_CHANNEL = "Run `/mock-draft` in a server text channel — the thread is created there."
MSG_MOCK_UNKNOWN_SET = "Unknown set `{code}`. Pick one from the suggestions, or use a registered cube format."
MSG_MOCK_ALREADY_ACTIVE = "A mock draft is already running in {thread}. Finish or cancel it before starting another."
MSG_MOCK_LOBBY_OPEN = (
    "{draftmancer_emoji} **{event_name}** lobby is open!\n"
    "**Join the Draftmancer session:** <{url}>\n"
    "-# Use your Discord name so the bot can match you. No matches are played. When the draft ends, "
    "the table and draft logs will be posted on the site."
)
MSG_MOCK_COMPLETE = "✅ **Mock draft complete!** Draft Recap is now [on the site]({url}) {manat}"
