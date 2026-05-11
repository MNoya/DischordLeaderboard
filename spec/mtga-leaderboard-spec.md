# MTGA Community Leaderboard — Project Spec

## Overview

A community leaderboard for a Discord MTGA server. Players sign up via a Discord bot using their 17lands profile, and their game data is fetched and displayed on a public React website. The leaderboard is scoped per Magic set, with historical set browsing.

---

## Tech Stack

| Layer | Technology | Hosting |
|---|---|---|
| Frontend | React + Vite | Netlify |
| Database | Supabase (PostgreSQL) | Supabase free tier |
| Discord Bot | Python (discord.py) | Railway |
| ORM | SQLAlchemy + Alembic | — |
| CI/CD | GitHub Actions | GitHub |
| DNS / SSL | Cloudflare (optional) | Cloudflare free tier |

---

## Accounts Required

Set up in this order:

1. **GitHub** — code hosting + CI/CD (already have)
2. **Discord Developer Portal** — bot token (already have)
3. **Supabase** — database, URL + keys
4. **Railway** — bot hosting, connect GitHub repo
5. **Netlify** — frontend hosting, connect GitHub repo
6. **Cloudflare** — DNS only if using a custom domain (optional)

---

## Repository Structure

```
/
├── bot/                    # Python Discord bot
│   ├── main.py
│   ├── commands/
│   │   ├── signup.py
│   │   ├── signout.py
│   │   ├── update_profile.py
│   │   ├── leaderboard.py
│   │   └── refresh.py
│   ├── services/
│   │   ├── supabase_client.py
│   │   └── seventeenlands.py
│   ├── models.py           # SQLAlchemy models
│   ├── database.py         # DB engine + session setup
│   ├── requirements.txt
│   └── tests/
│       ├── test_commands.py
│       └── test_seventeenlands.py
│
├── alembic/                # Database migrations
│   ├── versions/           # Auto-generated migration files
│   ├── env.py              # Alembic config (points to models.py)
│   └── script.py.mako
├── alembic.ini
│
├── frontend/               # React + Vite app
│   ├── src/
│   │   ├── components/
│   │   │   ├── Leaderboard.jsx
│   │   │   ├── PlayerRow.jsx
│   │   │   ├── SetSelector.jsx
│   │   │   └── Podium.jsx
│   │   ├── lib/
│   │   │   └── supabase.js
│   │   ├── App.jsx
│   │   └── main.jsx
│   ├── vite.config.js
│   ├── package.json
│   └── tests/
│
└── .github/
    └── workflows/
        └── ci.yml
```

---

## Database Schema (SQLAlchemy Models + Alembic)

The bot manages the database schema via SQLAlchemy models and Alembic migrations. Raw SQL is never written by hand — models are the source of truth.

### Models (`bot/models.py`)

```python
from sqlalchemy import Column, String, Integer, Float, Boolean, Date, DateTime, ForeignKey, UniqueConstraint
from sqlalchemy.orm import DeclarativeBase, relationship
from sqlalchemy.sql import func

class Base(DeclarativeBase):
    pass

class Player(Base):
    __tablename__ = "players"

    id                   = Column(String, primary_key=True, default=lambda: str(uuid4()))
    discord_id           = Column(String, unique=True, nullable=False)
    discord_username     = Column(String, nullable=False)
    display_name         = Column(String, nullable=False)
    seventeenlands_token = Column(String, nullable=False)
    seventeenlands_url   = Column(String, nullable=False)
    active               = Column(Boolean, default=True)
    joined_at            = Column(DateTime, server_default=func.now())
    updated_at           = Column(DateTime, server_default=func.now(), onupdate=func.now())

    token_invalid    = Column(Boolean, default=False)  # true if 17lands fetch fails — cleared on /update-profile
    stats = relationship("PlayerStats", back_populates="player", cascade="all, delete")


class MagicSet(Base):
    __tablename__ = "sets"

    id         = Column(String, primary_key=True, default=lambda: str(uuid4()))
    code       = Column(String, unique=True, nullable=False)   # e.g. "BLB"
    name       = Column(String, nullable=False)                # e.g. "Bloomburrow"
    start_date = Column(Date, nullable=False)
    end_date   = Column(Date, nullable=True)                   # null = current set
    is_current = Column(Boolean, default=False)

    stats = relationship("PlayerStats", back_populates="set")


class PlayerStats(Base):
    __tablename__ = "player_stats"

    id            = Column(String, primary_key=True, default=lambda: str(uuid4()))
    player_id     = Column(String, ForeignKey("players.id"), nullable=False)
    set_id        = Column(String, ForeignKey("sets.id"), nullable=False)
    format        = Column(String, nullable=False)  # 'PremierDraft', 'TradDraft', 'Sealed', 'TradSealed'
    games_played  = Column(Integer, default=0)
    wins          = Column(Integer, default=0)
    losses        = Column(Integer, default=0)
    trophies      = Column(Integer, default=0)      # 7-0 runs
    rating        = Column(Float, default=0)        # custom ranking formula
    last_fetched_at = Column(DateTime, nullable=True)

    player = relationship("Player", back_populates="stats")
    set    = relationship("MagicSet", back_populates="stats")

    __table_args__ = (
        UniqueConstraint("player_id", "set_id", "format"),
    )
```

### DB Session (`bot/database.py`)

```python
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from alembic.config import Config
from alembic import command
import os, logging

DATABASE_URL = os.environ["DATABASE_URL"]  # Supabase Postgres connection string

engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(bind=engine)

def run_migrations():
    """Run Alembic migrations on bot startup. Crashes loudly on failure."""
    try:
        alembic_cfg = Config("alembic.ini")
        command.upgrade(alembic_cfg, "head")
        logging.info("✅ Migrations applied successfully.")
    except Exception as e:
        logging.critical(f"❌ Migration failed: {e}")
        raise SystemExit(1)  # Crash the bot — do not start with a broken schema
```

### Startup (`bot/main.py`)

```python
from database import run_migrations

# First thing on startup — before bot connects to Discord
run_migrations()

# Then start the bot normally...
```

### Adding a New Stat (workflow)

1. Add the column to the model in `models.py`
2. Run: `alembic revision --autogenerate -m "add_my_new_stat"`
3. Review the generated file in `alembic/versions/`
4. Commit — Railway redeploys the bot, migrations run automatically on startup

```python
# Alembic auto-generates this — you don't write it manually
def upgrade():
    op.add_column('player_stats',
        sa.Column('avg_pick_position', sa.Float(), nullable=True, server_default='0')
    )

def downgrade():
    op.drop_column('player_stats', 'avg_pick_position')
```

### Row Level Security (RLS)

RLS is configured manually in Supabase dashboard (one-time setup), since it's a Supabase-specific feature outside SQLAlchemy's scope:

```sql
-- Run once in Supabase SQL editor
alter table players enable row level security;
alter table player_stats enable row level security;
alter table sets enable row level security;

create policy "Public read" on players for select using (true);
create policy "Public read" on player_stats for select using (true);
create policy "Public read" on sets for select using (true);

-- Bot connects via DATABASE_URL with full access, bypasses RLS
```

---

## Environment Variables

### Bot (Railway)
```env
DISCORD_BOT_TOKEN=
DISCORD_GUILD_ID=
SUPABASE_URL=
SUPABASE_SERVICE_ROLE_KEY=    # Full access, server-side only — never expose publicly
DATABASE_URL=                 # Supabase Postgres connection string (for SQLAlchemy/Alembic)
                              # Format: postgresql://user:password@host:port/dbname
```

### Frontend (Netlify)
```env
VITE_SUPABASE_URL=
VITE_SUPABASE_ANON_KEY=       # Public key, safe for frontend — protected by RLS
```

---

## Discord Bot — Commands

All commands are slash commands (`/command`).

---

### `/signup`

**Who:** Any server member  
**Description:** Registers the user on the leaderboard. Token is collected via DM for privacy.

**Flow:**
1. Bot checks if the user is already registered — if so, reply ephemerally with error.
2. Bot replies in the channel (ephemeral): *"📬 I've sent you a DM with instructions to complete your signup!"*
3. Bot DMs the user with instructions:

> **Welcome to the MTGA Community Leaderboard!**
> To sign up, I need your **17lands profile token**. Here's how to get it:
> 1. Go to [17lands.com](https://17lands.com) and log in.
> 2. Click your username → **User History**.
> 3. Copy the URL — it looks like:
>    `https://www.17lands.com/user_history/10c0f8918a2b4fa7b230448caee0b2ca`
> 4. Reply to this message with the full URL or just the token.
>
> *Your token is stored securely and only used to fetch your game stats for the leaderboard.*

4. Bot waits for the user's DM reply (timeout: 10 minutes). If timeout is reached, bot sends a follow-up DM: *"⏱️ Signup timed out. Run `/signup` in the server whenever you're ready to try again."*
5. Bot extracts and validates the token (32-char hex UUID, parsed from full URL if needed).
6. Bot does a quick fetch to 17lands to verify the token returns valid data.
7. Bot inserts the player into the DB with `active = true`.
8. Bot replies via DM: *"✅ You're signed up! Your stats will appear on the leaderboard within 24 hours."*

**Errors:**
- Already registered → *"You're already signed up. Use `/update-profile` in the server to change your 17lands link."*
- Invalid token format → *"That doesn't look like a valid 17lands token. Please check the URL and try again."*
- Token not found on 17lands → *"I couldn't verify that token with 17lands. Please double-check your URL and try again."*
- User has DMs disabled → Bot replies ephemerally in channel: *"⚠️ I couldn't DM you. Please enable DMs from server members in your privacy settings and try again."*

---

### `/signout`

**Who:** Any registered player  
**Description:** Pauses the user's participation. Sets `active = false` — they stop being tracked and are hidden from the leaderboard. All historical stats are preserved. They can rejoin anytime with `/signup`.

**Flow:**
1. Bot checks the user is registered and active.
2. Sets `active = false` in the DB.
3. Replies (ephemeral): *"✅ You've been removed from the leaderboard. Your stats are saved — use `/signup` anytime to return."*

**Errors:**
- Not registered → *"You're not signed up for the leaderboard."*
- Already inactive → *"You're already signed out. Use `/signup` to return."*

---

### `/update-profile`

**Who:** Any registered player  
**Description:** Updates the player's 17lands profile link. Used when a token has been regenerated on 17lands or was entered incorrectly at signup. Uses the same DM flow as `/signup`.

**Flow:**
1. Bot replies in the channel (ephemeral): *"📬 I've sent you a DM to update your profile."*
2. Bot DMs the user with the same token instructions as `/signup`.
3. Bot waits for DM reply (timeout: 10 minutes, same behaviour as `/signup`).
4. Bot validates the new token and verifies it against 17lands.
5. Bot updates `seventeenlands_token`, `seventeenlands_url`, and `updated_at` in the DB.
6. Bot replies via DM: *"✅ Your 17lands profile has been updated. Stats will refresh on the next nightly run."*

**Errors:** Same as `/signup` (invalid format, unverifiable token, DMs disabled).

---

### `/delete-account`

**Who:** Any registered player  
**Description:** Permanently deletes the player's account and all associated stats from the database. Irreversible.

**Flow:**
1. Bot replies (ephemeral): *"⚠️ This will permanently delete your account and all your stats. This cannot be undone. Reply with `YES` to confirm."*
2. Bot waits for DM reply (timeout: 5 minutes).
3. If user replies `YES` (case-insensitive): bot deletes the player record (cascade deletes all `player_stats` rows via FK).
4. Bot replies: *"🗑️ Your account has been permanently deleted. You're welcome to `/signup` again anytime."*
5. If user replies anything else or times out: *"Deletion cancelled. Your account is unchanged."*

**Errors:**
- Not registered → *"You don't have an account to delete."*

---

### `/leaderboard`

**Who:** Anyone  
**Description:** Shows the current set leaderboard in the channel, visible only to the requesting user (ephemeral).

**Response format (Discord embed):**

```
🏆 Leaderboard — [Current Set Name]
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

🥇 PlayerOne       ████ 87.3 pts
🥈 PlayerTwo       ███  81.1 pts
🥉 PlayerThree     ███  79.4 pts

📊 Your rank: #7 — 61.2 pts

🌐 Full leaderboard: https://your-site.netlify.app
```

**Notes:**
- Response is ephemeral (only visible to the user who triggered it)
- Shows top 3 + the requesting user's rank (if they are signed up)
- If the user is not signed up, omit the personal rank line and add: *"Sign up with `/signup` to appear on the leaderboard!"*
- Includes a link to the public website

---

### `/refresh`

**Who:** Admins only (check Discord role)  
**Description:** Manually triggers a 17lands data fetch for all active players.

**Flow:**
1. Bot replies: *"🔄 Refreshing stats for X players..."*
2. Iterates active players, fetches 17lands data using the existing rate-limited fetch logic (adapted from existing Python codebase), updates `player_stats`.
3. If a player's token returns a 404 or invalid response from 17lands, marks them as `token_invalid = true` in the DB and sends them a DM: *"⚠️ Your 17lands token appears to be invalid (possibly regenerated). Please use `/update-profile` to provide your new token."*
4. Replies with a summary: *"✅ Refresh complete. X players updated, Y tokens flagged as invalid."*

**Note:** Players with `token_invalid = true` are skipped on subsequent fetch runs until they update their token via `/update-profile`, which resets the flag.

---

## 17lands Data Fetching

### Fetch Strategy

- **Scheduled:** Nightly cron job (Railway cron or APScheduler in the bot) — fetches all active players.
- **On demand:** `/refresh` admin command.

### 17lands API

The token from the profile URL (`/user_history/{token}`) can be used to query player history. Key endpoint pattern:

```
https://www.17lands.com/user_history/{token}
```

Fetch and parse events for all supported formats:
- `PremierDraft`
- `TradDraft`
- `Sealed`
- `TradSealed`

Filter events by set code to populate per-set stats. Apply the existing rating/ranking formula to compute the `rating` field in `player_stats`.

**Existing Python codebase:** The rate limiting logic and ranking/minimum games threshold calculation already exist and will be adapted for this project. Claude Code should expect to receive this code separately and integrate it into `bot/services/seventeenlands.py` rather than writing it from scratch.

---


## Magic Set Management

### `/new-set` (Admin only)

New sets are registered manually by an admin when a new Magic format launches (every few months). Admins are identified by a configurable Discord role ID stored in env vars.

**Usage:** `/new-set code:BLB name:Bloomburrow start_date:2024-08-13`

**Flow:**
1. Bot validates the user has the admin role.
2. Bot sets the current set's `end_date` to today and `is_current = false`.
3. Bot inserts the new set with `is_current = true`.
4. Bot replies (ephemeral): *"✅ New set registered: Bloomburrow (BLB). Leaderboard is now tracking the new set."*
5. Bot posts to `#bot-logs`: *"🆕 New set started: Bloomburrow (BLB) — registered by @AdminName."*

**Errors:**
- Set code already exists → *"A set with code BLB already exists."*
- No admin role → *"You don't have permission to use this command."*

---

## Frontend — React Website

### Pages

**`/` — Current Set Leaderboard**
- Set selector dropdown at the top (all sets, most recent first, current set pre-selected)
- Podium component for top 3 (trophy icons, names, scores)
- Full ranked table below with columns: Rank, Player, Wins, Losses, Trophies, Win Rate, Rating
- Format filter tabs: All | Premier Draft | Traditional Draft | Sealed | Traditional Sealed
- Auto-refreshes data every 5 minutes via Supabase
- Fully mobile responsive — community members frequently check from phones

**Set Selector behavior:**
- Dropdown lists all sets from the `sets` table
- Current set is labeled with a `🟢 Current` badge
- Selecting a historical set reloads the leaderboard for that set

### Supabase Client
```javascript
// src/lib/supabase.js
import { createClient } from '@supabase/supabase-js'

export const supabase = createClient(
  import.meta.env.VITE_SUPABASE_URL,
  import.meta.env.VITE_SUPABASE_ANON_KEY
)
```

---

## CI/CD — GitHub Actions

```yaml
# .github/workflows/ci.yml
name: CI

on:
  push:
    branches: [master]
  pull_request:
    branches: [master]

jobs:
  test-bot:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v4
        with:
          python-version: '3.11'
      - run: pip install -r bot/requirements.txt
      - run: pytest bot/tests/ -v

  test-frontend:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-node@v4
        with:
          node-version: '20'
      - run: npm install
        working-directory: frontend
      - run: npm run test
        working-directory: frontend
      - run: npm run build
        working-directory: frontend

# Netlify and Railway deploy automatically on master push
# after these jobs pass (configure in each platform's dashboard)
```

---

## Test Coverage

### Bot (pytest)

- `test_signup.py` — valid token, duplicate signup, invalid token format
- `test_signout.py` — active player, unregistered user
- `test_update_profile.py` — valid update, unregistered user
- `test_leaderboard.py` — registered user with rank, unregistered user
- `test_seventeenlands.py` — token extraction from URL, mock API response parsing
- `test_models.py` — FK constraints, unique constraints, cascade deletes, token_invalid flag reset on update
- `test_migrations.py` — Alembic `upgrade head` and `downgrade -1` run cleanly against a test DB

### Frontend (Vitest + React Testing Library)

- `Leaderboard.test.jsx` — renders with mock data, correct sort order
- `SetSelector.test.jsx` — renders set list, triggers correct data load
- `PlayerRow.test.jsx` — displays rank, name, stats correctly
- `Podium.test.jsx` — shows top 3 with correct medals

---

## Deployment Checklist

- [ ] Create Supabase project, grab `DATABASE_URL` from project settings
- [ ] Run `alembic upgrade head` locally against Supabase to apply initial schema
- [ ] Enable RLS and create read policies in Supabase SQL editor (one-time)
- [ ] Add all env vars to Railway (including `DATABASE_URL`)
- [ ] Add Supabase anon key + URL to Netlify env vars
- [ ] Connect GitHub repo to Railway (bot folder)
- [ ] Connect GitHub repo to Netlify (frontend folder)
- [ ] Configure Netlify and Railway to only deploy if CI passes
- [ ] Seed `sets` table with current Magic set
- [ ] Invite bot to test server and verify all slash commands
- [ ] Test full flow: signup → 17lands fetch → leaderboard display

---

## Future Considerations

- Per-player profile page on the website (`/player/{discord_id}`)
- Season summaries across sets
- Discord notifications when a player earns a trophy (7-0)
- Admin dashboard for managing players and sets
