from uuid import uuid4

from sqlalchemy import (
    Boolean,
    Column,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    LargeBinary,
    PrimaryKeyConstraint,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import ARRAY, JSONB, UUID
from sqlalchemy.orm import DeclarativeBase, relationship
from sqlalchemy.sql import func, text


class Base(DeclarativeBase):
    pass


class P0P1Entry(Base):
    __tablename__ = "p0p1_entries"

    user_id    = Column(UUID(as_uuid=True), nullable=False)
    set_code   = Column(Text, nullable=False)
    slot       = Column(Text, nullable=False)
    card_name  = Column(Text, nullable=False)
    updated_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())

    __table_args__ = (
        PrimaryKeyConstraint("user_id", "set_code", "slot"),
    )


class Player(Base):
    __tablename__ = "players"

    id                   = Column(String, primary_key=True, default=lambda: str(uuid4()))
    # URL-safe handle derived from display_name at /join, frozen post-creation.
    # Used by the frontend for /player/{slug} routing
    slug                 = Column(String, unique=True, nullable=False)
    discord_id           = Column(String, unique=True, nullable=False)
    discord_username     = Column(String, nullable=True)
    display_name         = Column(String, nullable=False)
    arena_name           = Column(String, nullable=True)
    arena_aliases        = Column(ARRAY(String), nullable=False, server_default="{}")
    # Discord avatar hash (the asset key, not the full URL). The leaderboard
    # view computes the CDN URL server-side so discord_id never leaves the DB
    avatar_hash          = Column(String, nullable=True)
    seventeenlands_token = Column(String, nullable=True)
    active               = Column(Boolean, nullable=False, default=True)
    joined_at            = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at           = Column(DateTime(timezone=True), nullable=False, server_default=func.now(),
                                  onupdate=func.now())
    token_invalid        = Column(Boolean, nullable=False, default=False)
    leaderboard_opt_in   = Column(Boolean, nullable=False, default=True)

    stats = relationship(
        "PlayerStats",
        back_populates="player",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )


class MagicSet(Base):
    __tablename__ = "sets"

    id         = Column(String, primary_key=True, default=lambda: str(uuid4()))
    code       = Column(String, unique=True, nullable=False)
    name       = Column(String, nullable=False)
    start_date = Column(Date, nullable=False)
    end_date   = Column(Date, nullable=True)
    last_refreshed_at = Column(DateTime(timezone=True), nullable=True)

    stats = relationship("PlayerStats", back_populates="set")


class PlayerStats(Base):
    __tablename__ = "player_stats"

    id              = Column(String, primary_key=True, default=lambda: str(uuid4()))
    player_id       = Column(String, ForeignKey("players.id", ondelete="CASCADE"), nullable=False)
    set_id          = Column(String, ForeignKey("sets.id"), nullable=False)
    format          = Column(String, nullable=False)
    # Raw 17lands expansion code (e.g. "ECL", "Y26ECL"). Multiple expansions
    # roll up under one set for the leaderboard but stay separable for player
    # detail views
    expansion       = Column(String, nullable=False)
    events          = Column(Integer, nullable=False, default=0)
    games_played    = Column(Integer, nullable=False, default=0)
    wins            = Column(Integer, nullable=False, default=0)
    losses          = Column(Integer, nullable=False, default=0)
    trophies        = Column(Integer, nullable=False, default=0)
    last_fetched_at = Column(DateTime(timezone=True), nullable=True)

    player = relationship("Player", back_populates="stats")
    set    = relationship("MagicSet", back_populates="stats")

    __table_args__ = (
        UniqueConstraint(
            "player_id", "set_id", "format", "expansion",
            name="uq_player_set_format_expansion",
        ),
    )


class LeaderboardMessage(Base):
    """Tracks every bot-posted leaderboard embed per (channel, set).

    Multiple rows per (channel, set) are allowed: a pinned message stays
    tracked alongside any newer bottom-fresh post. !refresh edits each tracked
    message in place; /leaderboard deletes the unpinned prior posts and leaves
    pinned ones alone.
    """
    __tablename__ = "leaderboard_messages"

    id               = Column(String, primary_key=True, default=lambda: str(uuid4()))
    channel_id       = Column(String, nullable=False)
    set_id           = Column(String, ForeignKey("sets.id"), nullable=False)
    message_id       = Column(String, nullable=False)
    # Filter applied at post-time. NULL = unfiltered (overall); 'format' or 'color'
    # → filter_value holds the queue label or archetype code respectively.
    filter_type      = Column(String, nullable=True)
    filter_value     = Column(String, nullable=True)
    last_rendered_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now())


class DraftEvent(Base):
    """One row per individual 17lands draft event for a player.

    Captured per event (not aggregated) so future features — favorite deck by
    color, trophy streaks, mythic-rank leaderboards, ALCQ tracking — can derive
    everything from per-event data. The DB is derived state; 17lands stays the
    source of truth, and refresh re-fetches every few hours to stay current.
    """
    __tablename__ = "draft_events"

    id                      = Column(String, primary_key=True, default=lambda: str(uuid4()))
    player_id               = Column(String, ForeignKey("players.id", ondelete="CASCADE"), nullable=False)
    # Nullable so drafts in not-yet-registered sets can persist; claimed when /add-set adds the parent set
    set_id                  = Column(String, ForeignKey("sets.id"), nullable=True)
    # 17lands' own event ID — upsert key so re-fetches stay idempotent
    seventeenlands_event_id = Column(String, nullable=False)

    format     = Column(String, nullable=False)
    expansion  = Column(String, nullable=False)

    wins       = Column(Integer, nullable=False)
    losses     = Column(Integer, nullable=False)
    is_trophy  = Column(Boolean, nullable=False)

    # 17lands case-encodes splash: uppercase = main color, lowercase = splash
    # (e.g. "WBg" = WB main with green splash). Null for sealed / unfinished events
    colors     = Column(String, nullable=True)
    start_rank = Column(String, nullable=True)
    end_rank   = Column(String, nullable=True)
    account_id = Column(Integer, ForeignKey("player_accounts.id", ondelete="SET NULL"), nullable=True)

    started_at  = Column(DateTime(timezone=True), nullable=True)
    finished_at = Column(DateTime(timezone=True), nullable=True)

    fetched_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now())

    __table_args__ = (
        UniqueConstraint("player_id", "seventeenlands_event_id",
                         name="uq_draft_event_per_player"),
    )


class PlayerAccount(Base):
    """One MTGA account seen under a player's 17lands token.

    A single token can hold several accounts, so ``DraftEvent.account_id`` points here to keep
    per-account stats (the climb award) from stitching a low rank on one account to Mythic on
    another. Integer PK rather than the usual UUID so the per-row foreign key stays compact.
    """
    __tablename__ = "player_accounts"

    id        = Column(Integer, primary_key=True, autoincrement=True)
    player_id = Column(String, ForeignKey("players.id", ondelete="CASCADE"), nullable=False)
    name      = Column(String, nullable=False)

    __table_args__ = (
        UniqueConstraint("player_id", "name", name="uq_player_account"),
    )


class PodDraftEvent(Base):
    __tablename__ = "pod_draft_events"

    id                  = Column(String, primary_key=True, default=lambda: str(uuid4()))
    event_date          = Column(Date, nullable=False)
    event_time          = Column(DateTime(timezone=True), nullable=False)
    set_id              = Column(String, ForeignKey("sets.id"), nullable=True)
    set_code            = Column(String, nullable=False)
    format_label        = Column(String, nullable=True)
    name                = Column(String, nullable=False)
    draftmancer_session = Column(String, nullable=False)
    discord_thread_id   = Column(String, nullable=False)
    sesh_message_id     = Column(String, nullable=True)
    socket_status       = Column(String, nullable=False)
    kind                = Column(String, nullable=False, server_default="tournament")
    pairing_mode        = Column(String, nullable=False, server_default="bracket")
    seating_mode        = Column(String, nullable=False, server_default="random")
    current_round       = Column(Integer, nullable=True)
    draft_log_gz        = Column(LargeBinary, nullable=True)
    draft_log           = Column(JSONB, nullable=True)
    created_at          = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    finalized_at        = Column(DateTime(timezone=True), nullable=True)
    championship_posted_at = Column(DateTime(timezone=True), nullable=True)

    participants = relationship(
        "PodDraftParticipant",
        back_populates="event",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )
    matches = relationship(
        "PodDraftMatch",
        back_populates="event",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )


class PodDraftParticipant(Base):
    __tablename__ = "pod_draft_participants"

    id               = Column(String, primary_key=True, default=lambda: str(uuid4()))
    event_id         = Column(String, ForeignKey("pod_draft_events.id", ondelete="CASCADE"), nullable=False)
    # Null for guests not yet registered; populated retroactively by /join or /link-arena
    player_id        = Column(String, ForeignKey("players.id"), nullable=True)
    display_name     = Column(String, nullable=False)
    draftmancer_name = Column(String, nullable=True)
    seat_index          = Column(Integer, nullable=True)
    placement           = Column(Integer, nullable=True)
    record              = Column(String, nullable=True)
    eliminated_round    = Column(Integer, nullable=True)
    draft_log_url       = Column(String, nullable=True)
    deck_colors             = Column(String, nullable=True)
    deck_screenshot_url     = Column(String, nullable=True)
    deck_screenshot_caption = Column(String, nullable=True)
    wants_draft_review      = Column(Boolean, nullable=True)

    event  = relationship("PodDraftEvent", back_populates="participants")
    player = relationship("Player")

    __table_args__ = (
        Index(
            "uq_pod_participant_event_player",
            "event_id", "player_id",
            unique=True,
            postgresql_where=text("player_id IS NOT NULL"),
        ),
    )


class PodDraftMatch(Base):
    __tablename__ = "pod_draft_matches"

    id             = Column(String, primary_key=True, default=lambda: str(uuid4()))
    event_id       = Column(String, ForeignKey("pod_draft_events.id", ondelete="CASCADE"), nullable=False)
    round          = Column(Integer, nullable=False)
    pairing_index  = Column(Integer, nullable=False, default=0)
    player_a_name  = Column(String, nullable=False)
    player_b_name  = Column(String, nullable=False)
    winner_name    = Column(String, nullable=True)
    score          = Column(String, nullable=True)
    reported_at    = Column(DateTime(timezone=True), nullable=True)

    event = relationship("PodDraftEvent", back_populates="matches")


class PodDraftDmMessage(Base):
    __tablename__ = "pod_draft_dm_messages"

    id             = Column(String, primary_key=True, default=lambda: str(uuid4()))
    event_id       = Column(String, ForeignKey("pod_draft_events.id", ondelete="CASCADE"), nullable=False)
    participant_id = Column(String, ForeignKey("pod_draft_participants.id", ondelete="CASCADE"), nullable=False)
    kind           = Column(String, nullable=False)
    round_num      = Column(Integer, nullable=True)
    match_id       = Column(String, ForeignKey("pod_draft_matches.id", ondelete="CASCADE"), nullable=True)
    dm_channel_id  = Column(String, nullable=False)
    dm_message_id  = Column(String, nullable=False)
    created_at     = Column(DateTime(timezone=True), nullable=False, server_default=func.now())

    __table_args__ = (
        UniqueConstraint("participant_id", "kind", "round_num", name="uq_pod_dm_msg_participant_kind_round"),
        Index("ix_pod_dm_msg_match_kind", "match_id", "kind"),
        Index("ix_pod_dm_msg_event", "event_id"),
    )


class PodDraftReplay(Base):
    __tablename__ = "pod_draft_replays"

    id             = Column(String, primary_key=True, default=lambda: str(uuid4()))
    event_id       = Column(String, ForeignKey("pod_draft_events.id", ondelete="CASCADE"), nullable=False)
    player_id      = Column(String, ForeignKey("players.id", ondelete="CASCADE"), nullable=False)
    game_id        = Column(String, nullable=False)
    link           = Column(String, nullable=False)
    game_time      = Column(DateTime(timezone=True), nullable=False)
    won            = Column(Boolean, nullable=False)
    turns          = Column(Integer, nullable=True)
    on_play        = Column(Boolean, nullable=True)
    inferred_round = Column(Integer, nullable=True)

    __table_args__ = (
        UniqueConstraint("event_id", "player_id", "game_id", name="uq_pod_draft_replay_event_player_game"),
        Index("ix_pod_draft_replays_event_player", "event_id", "player_id"),
        Index("ix_pod_draft_replays_event_time", "event_id", "game_time"),
    )


class SelfReportedTrophy(Base):
    """A trophy a player posted in trophy-hype and logged to their profile via /trophy.

    Unverified self-report: showcase only, never scored. The source_url links back to the
    original public post for accountability. Unique per (player_id, source_message_id) so
    re-running /trophy on the same post updates rather than duplicates.
    """
    __tablename__ = "self_reported_trophies"

    id                = Column(String, primary_key=True, default=lambda: str(uuid4()))
    player_id         = Column(String, ForeignKey("players.id", ondelete="CASCADE"), nullable=False)
    # Nullable so a trophy in a not-yet-registered set still persists, mirroring draft_events
    set_id            = Column(String, ForeignKey("sets.id"), nullable=True)
    set_code          = Column(String, nullable=False)
    record            = Column(String, nullable=False)
    # WUBRG-normalized (uppercase main, lowercase splash); null when the player left it unknown
    colors            = Column(String, nullable=True)
    platform          = Column(String, nullable=False)
    # The player's original post text, kept as a memory to show alongside the deck on their profile
    caption           = Column(Text, nullable=True)
    # Discord CDN attachment URL (dim-stripped), refreshed browser-side via the message ref when its
    # signed expiry lapses — same treatment as pod deck screenshots
    screenshot_url    = Column(String, nullable=True)
    source_channel_id = Column(String, nullable=False)
    source_message_id = Column(String, nullable=False)
    source_url        = Column(String, nullable=False)
    reported_at       = Column(DateTime(timezone=True), nullable=False, server_default=func.now())

    player = relationship("Player")

    __table_args__ = (
        UniqueConstraint("player_id", "source_message_id", name="uq_self_trophy_player_message"),
    )


class Episode(Base):
    """One row per published piece of content — a podcast episode, a YouTube video, or both
    when a video matches its episode.

    Synced from the Libsyn RSS feed and the YouTube channel; ``category`` and ``set_code``
    come from the channel's curated playlists, falling back to title inference for podcast-only
    entries with no matching video. Derived state, rebuilt on each sync — the feeds stay the
    source of truth. ``playlists`` keeps the raw membership so a future manual override has
    something to correct against, and transcripts can land as a new column without reshaping.
    """
    __tablename__ = "episodes"

    id               = Column(String, primary_key=True, default=lambda: str(uuid4()))
    guid             = Column(String, nullable=False, unique=True)
    kind             = Column(String, nullable=False)
    number           = Column(Integer, nullable=True)

    title            = Column(String, nullable=False)
    link             = Column(String, nullable=False)
    summary          = Column(Text, nullable=True)
    image            = Column(String, nullable=True)
    published_at     = Column(DateTime(timezone=True), nullable=False)
    duration_seconds = Column(Integer, nullable=False, server_default="0")

    audio_url        = Column(String, nullable=True)
    youtube_id       = Column(String, nullable=True)

    category         = Column(String, nullable=False)
    set_code         = Column(String, nullable=True)
    set_name         = Column(String, nullable=True)
    set_released_at  = Column(Date, nullable=True)
    playlists        = Column(JSONB, nullable=True)

    synced_at        = Column(DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now())

    __table_args__ = (
        Index("ix_episodes_published_at", "published_at"),
        Index("ix_episodes_set_code", "set_code"),
    )
