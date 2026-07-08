"""Single source of truth for shared user-facing message strings, used across multiple commands and listeners."""

MSG_JOINED_LEADERBOARD = "🎉 Welcome aboard! Run `/help` to see what you can do."
MSG_NOT_REGISTERED = "You're not on the leaderboard. Run `/join` to get started."
MSG_NOT_ON_BOARD = "You're not on the leaderboard."
MSG_NOW_HIDDEN = (
    "🕵️ Your rank is now hidden. [Your profile]({profile_url}) and trophies stay visible. "
    "Run `/join` anytime to show your rank again."
)
MSG_ALREADY_HIDDEN = "Your rank is already hidden. Run `/join` to show it again."
MSG_RANKED_AGAIN = "👋 Your rank is back in the standings."
MSG_TOKEN_INVALIDATED = (
    "⚠️ Your 17lands token appears to be invalid (possibly regenerated). "
    "Please use `/link-17lands` to provide your new token."
)
MSG_ADMIN_ONLY = "This command is reserved for the bot admin."

MSG_MOCK_NOT_TEXT_CHANNEL = "Run `/mock-draft` in a server text channel — the thread is created there."
MSG_MOCK_UNKNOWN_SET = "Unknown set `{code}`. Pick one from the suggestions, or use a registered cube format."
MSG_MOCK_ALREADY_ACTIVE = "A mock draft is already running in {thread}. Finish or cancel it before starting another."
MSG_MOCK_LOBBY_OPEN = (
    "{draftmancer_emoji} **{event_name}** lobby is open!{counter}\n"
    "**Join the Draftmancer session:** <{url}>\n"
    "-# Use your Discord name so the bot can match you. No matches are played. When the draft ends, "
    "the table and draft logs will be posted on the site."
)
MSG_MOCK_COMPLETE = "✅ **{event_name} complete!** [Draft Recap here](<{url}>) {manat}"
MSG_MOCK_LOBBY_COUNTER = " 👥 {count}/8"
MSG_LOBBY_FULL_PROMPT = "8️⃣ Players locked in! Initiate Ready Check?"
MSG_BOT_RECONNECTED = "🤖 Bot reconnected — back to managing the lobby."

MSG_SPLIT_NO_SOURCE = "Run `/pod-split` in a pod-draft thread, or pass an `event` to pick the pod to split."
MSG_SPLIT_UNKNOWN_EVENT = "No pod-draft event named `{event}`."
MSG_SPLIT_INTRO = "Second table for anyone not already in the first draft."
MSG_SPLIT_GATHERING = "New thread and Draftmancer lobby will be created once {threshold} players join."
MSG_SPLIT_CREATED = "{name} created"
MSG_SPLIT_JOINED = "Players ({count})"
MSG_SPLIT_BUTTON = "Join Table {table}"
MSG_SPLIT_GOTO = "Go to Table {table}"
MSG_SPLIT_LOBBY_STARTER = "{draftmancer_emoji} **{event_name}** created."
