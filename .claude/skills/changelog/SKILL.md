---
name: changelog
description: Draft and append a player-facing changelog entry, in the LLU patch-notes format, to the single root CHANGELOG.md. Covers both bot and website changes. Gathers recent changes, shows a draft for the user to accept or refine, then writes the dated section. Does not commit.
---

# changelog

Produce a short, player-facing changelog entry (game patch-notes style) and append it to the project's single changelog. Covers both the **bot** and the **website** in one file.

## Argument

`$ARGUMENTS` is an optional scope/focus hint, not a file selector — everything lands in one changelog. Examples: `bot`, `website`, `pod drafts`, `` (empty = whatever changed across the project).

All entries are written to a single **`CHANGELOG.md` at the repo root**. Create it with the title line `# LLU Updates` if it does not exist. The hint only narrows which changes to summarize; bot and website changes share the file and can sit in the same dated section.

## Format (do not deviate)

Match the existing entries exactly:

```
# LLU Updates

## Jun 13, 2026
🪑 Live seeding table now updates instantly as players join, no refresh needed
✅ Added a Ready Check nudge once 8 linked players are in the lobby
🔁 Tournaments survive a bot restart, rounds and results stay safe
```

Rules:

- **Date heading** `## <Mon D, YYYY>` — short month, no leading zero on the day. Get today with `date +"%b %-d, %Y"`. Keep the format identical to existing headings.
- **One line per change**, led by a single emoji that acts as the bullet. **No `-` bullet markers.**
- **Terse** — one line each, no trailing description sentences. Player-facing and non-technical: say what a player notices, never how it works internally.
- **Patch-notes voice** — mix proactive phrasings (`Added …`, `Fixed …`, `No more …`, `<thing> now …`). Do **not** force "now" onto every line; vary it.
- **No emdashes.** Avoid semicolons.
- **Only player-visible changes.** Omit internal refactors, tests, CI, migrations, infra, and deploy fixes.
- Pick an emoji that fits each change; keep them varied and meaningful.

## Workflow

### 1. Gather what changed

Read `CHANGELOG.md`'s most recent `## <date>` heading. Collect commits since that date:

```
git log --since="<that date>" --pretty="%h %s" -- <paths>
```

Scope `<paths>` to the hint: `bot/` for bot, `frontend/` for website, both when there's no hint. If the file is new or has no dated entry, take the last ~15 commits on those paths. Translate the player-visible ones into the format above; drop everything internal.

### 2. Show the draft

Render the proposed dated section as plain text (the exact lines that will be written) so the user sees precisely what gets posted to Discord.

### 3. Accept or refine (use AskUserQuestion)

Ask with options:

- **Accept and save** — write it as-is.
- **Refine** — the user adjusts wording, order, which items to include, or the emoji.

Tell the user they can type specific edits via the "Other" field. On any refinement, revise and re-show the draft, then ask again. Loop until accepted. Do not write the file until the user accepts.

### 4. Write

Insert the accepted `## <date>` section directly under the title line, above the previous most-recent entry (newest first). Preserve a blank line between the title and the first section and between sections. Do not touch older entries.

If today already has a `## <date>` section, append the new lines to it rather than creating a duplicate heading.

### 5. Report

Confirm the file written and show the final section. Do **not** commit — leave it for the user to version-control alongside the related change. Mention the file path so they can post it to Discord or commit it.

## Notes

- This is the player-facing history, not a developer changelog. ISO dates (`YYYY-MM-DD`) are the dev-changelog convention; this audience gets the friendlier `Mon D, YYYY`.
- Headings (`#`, `##`) render in a normal Discord message but show literally inside a code block — post as plain text.
- Keep entries scannable. If a release has many small changes, group or cut to the few players actually notice.
