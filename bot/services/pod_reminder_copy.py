"""Every user-facing string in a pod's reminder timeline, in one place so the voice stays aligned.

A pod hits these in order: the recruiting nudge across its states, the launcher slot fire ping, the
roster reminder, the lobby-open post, and the fired record. The inline reminder lines share one shape:

    {hello}**{name}** {state} <t:{unix}:R> {manat} [**{cta}**]({url})

The manat emoji separates the status from the action link. Builders in pod_schedule.py,
pod_daily_poll.py and pod_draft_reminder.py format these constants; new reminder copy belongs here, next
to its siblings, not back in those modules.
"""

RECRUITING_NEEDS_MORE = (
    "{hello}**{name}** looking for **{needed} more player{plural}** <t:{unix}:R> {manat} "
    "[**Sign up here**]({jump_url})"
)

RECRUITING_READY = (
    "{hello}**{name}** is ready to draft <t:{unix}:R> {manat} [**Sign up here**]({jump_url})"
)

RECRUITING_OVERFLOW = (
    "{hello}**{name}** is ready to draft <t:{unix}:R>\n"
    "✅ {yes} 🤷 {maybe}{split} {manat} [**Sign up here**]({jump_url})"
)

RECRUITING_OVERFLOW_SPLIT = ", with {latest} locked for {seticon} and {flashback} {flashback_emoji}"

SLOT_FIRE_PING = "{mention} starts <t:{unix}:R>"

ROSTER_REMINDER_TITLE = "🔔 Pod Draft Starting Soon"
ROSTER_REMINDER_LINE = "**{name}** starts <t:{unix}:R>"

LOBBY_OPEN_HEADLINE = "Lobby opened!"
LOBBY_OPEN = (
    "{draftmancer} {headline}\n"
    "**Join the Draftmancer session:** <{url}>\n\n"
    "Set your **Arena name** (like `YourName#12345`) as your Draftmancer name or use **Join Draft** "
    "below for your personal link."
    "{mentions}"
)

DRAFT_STARTED = (
    "{hello}**{name}** started with **{count} {players}** {manat} [**Event Thread**]({thread_url})"
)
