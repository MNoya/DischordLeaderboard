---
name: new-set
description: Add a new MTG set to the DischordLeaderboard rotation. Takes a 3-4 letter set code (e.g. MSH). Looks up the official name and Arena release date, updates bot/sets.py, runs seed + refresh against the local DATABASE_URL, and creates a commit. User pushes manually.
---

# new-set

Rotate a new Magic set onto the leaderboard.

## Argument

A 3- or 4-letter MTG Arena set code in `$ARGUMENTS`, e.g. `MSH`.

If no argument is given, ask the user for the code and stop.

## Workflow

### 1. Validate

- Strip whitespace and uppercase `$ARGUMENTS`. Must match `^[A-Z]{3,4}$`. Otherwise abort.
- Read `bot/sets.py`. If the code already appears in `ALL_SETS`, abort with `set <CODE> already exists in bot/sets.py`. Do not proceed.

### 2. Look up name and Arena release date

WebSearch for the new set's official name and **MTG Arena** release date (not tabletop). Prefer these sources:

- magic.wizards.com
- mtg.fandom.com (MTG Wiki)
- mtga.untapped.gg
- draftsim.com
- cardgamebase.com

If the search yields a confident, single answer, use it. If results are ambiguous (multiple plausible dates, conflicting set names) or no result, stop and ask the user for:

- Set name (full official, e.g. `Marvel Super Heroes`)
- MTG Arena release date (`YYYY-MM-DD`)

### 3. Edit `bot/sets.py`

Make the following edits in order:

1. Locate the entry in `ALL_SETS` whose `code` equals the current `ACTIVE_SET_CODE` (the **previous** active set).
2. If that entry's `end_date` is `None` or is `>=` the new release date, change its `end_date` to `(new release date - 1 day)`.
3. Append a new `SetSeed(...)` row to `ALL_SETS` immediately after the previous-active entry. Use `end_date=None`.
4. Change `ACTIVE_SET_CODE = "<NEW CODE>"`.
5. Preserve the column-aligned formatting of surrounding rows (visually align the constructor arguments).

### 4. Show diff

Run `git diff bot/sets.py` and display it to the user.

### 5. Run scripts against the local DATABASE_URL (mode B)

Sanity-check `DATABASE_URL`:

- Run `echo "$DATABASE_URL"`. Confirm it is set.
- If it points at `localhost` or `127.0.0.1`, warn the user that the changes will only land in their local Postgres and ask whether to proceed anyway (they may be testing).

Then run, in order:

```
python -m bot.scripts.seed_sets
python -m bot.scripts.refresh_stats --set-code <NEW CODE>
```

If either fails, stop. Do not commit. Report the error verbatim and let the user fix it.

### 6. Commit (do not push)

After both scripts succeed:

```
git add bot/sets.py
git commit -m "Add <NEW CODE> set"
```

Commit subject **must start with uppercase** (memory: `feedback_commit_subject_uppercase.md`).

If the previous active set's `end_date` was adjusted, use this subject instead:

```
Add <NEW CODE> set and close <PREV CODE>
```

### 7. Report

Tell the user:

- The new commit's short SHA and subject.
- `Push when ready: git push` — Railway redeploys on master push, and the bot rotates the leaderboard automatically because `ACTIVE_SET_CODE` changed.

Never push automatically.

## Notes

- Dates are MTG Arena release dates, not tabletop release dates.
- Set name is the full official name (e.g. `Marvel Super Heroes`, not `Marvel`).
- The seed script is idempotent and updates `name` / `end_date` on existing rows, so re-running is safe if anything went sideways.
- If `DATABASE_URL` is unset, ask the user for it rather than guessing.
