from uuid import uuid4

from sqlalchemy import (
    Boolean,
    Column,
    Date,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    LargeBinary,
    String,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import ARRAY
from sqlalchemy.orm import DeclarativeBase, relationship
from sqlalchemy.sql import func, text


class Base(DeclarativeBase):
    pass


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
    updated_at           = Column(DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now())
    token_invalid        = Column(Boolean, nullable=False, default=False)

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


class PlayerSetScore(Base):
    """Pre-computed total score per (player, set), refreshed alongside PlayerStats.

    /leaderboard reads from this table so the formula isn't re-run on every read.
    Bucket/weight changes only require a recompute, not a 17lands re-fetch.
    """
    __tablename__ = "player_set_scores"

    id                 = Column(String, primary_key=True, default=lambda: str(uuid4()))
    player_id          = Column(String, ForeignKey("players.id", ondelete="CASCADE"), nullable=False)
    set_id             = Column(String, ForeignKey("sets.id"), nullable=False)
    score              = Column(Float, nullable=False, default=0)
    trophies           = Column(Integer, nullable=False, default=0)
    last_calculated_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now())

    __table_args__ = (
        UniqueConstraint("player_id", "set_id", name="uq_player_set_score"),
    )


class PlayerArchetypeScore(Base):
    """Pre-computed score per (player, set, archetype). Parallels PlayerSetScore.

    Backs the per-archetype leaderboard. Score is `compute_score` re-run on the
    player's `draft_events` restricted to this archetype — subset replay.
    Refreshed alongside PlayerSetScore in `!refresh`.
    """
    __tablename__ = "player_archetype_scores"

    id                 = Column(String, primary_key=True, default=lambda: str(uuid4()))
    player_id          = Column(String, ForeignKey("players.id", ondelete="CASCADE"), nullable=False)
    set_id             = Column(String, ForeignKey("sets.id"), nullable=False)
    # WUBRG-sorted main colors only; '' for colorless
    archetype          = Column(String, nullable=False)
    score              = Column(Float, nullable=False, default=0)
    trophies           = Column(Integer, nullable=False, default=0)
    events             = Column(Integer, nullable=False, default=0)
    wins               = Column(Integer, nullable=False, default=0)
    losses             = Column(Integer, nullable=False, default=0)
    last_calculated_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now())

    __table_args__ = (
        UniqueConstraint("player_id", "set_id", "archetype", name="uq_player_set_archetype_score"),
    )


class PlayerFormatArchetypeScore(Base):
    __tablename__ = "player_format_archetype_scores"

    id                 = Column(String, primary_key=True, default=lambda: str(uuid4()))
    player_id          = Column(String, ForeignKey("players.id", ondelete="CASCADE"), nullable=False)
    set_id             = Column(String, ForeignKey("sets.id"), nullable=False)
    format_label       = Column(String, nullable=False)
    archetype          = Column(String, nullable=False)
    score              = Column(Float, nullable=False, default=0)
    trophies           = Column(Integer, nullable=False, default=0)
    events             = Column(Integer, nullable=False, default=0)
    wins               = Column(Integer, nullable=False, default=0)
    losses             = Column(Integer, nullable=False, default=0)
    last_calculated_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now())

    __table_args__ = (
        UniqueConstraint(
            "player_id", "set_id", "format_label", "archetype",
            name="uq_player_set_format_label_archetype_score",
        ),
        Index("ix_pfas_set_format_archetype", "set_id", "format_label", "archetype"),
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
    set_id                  = Column(String, ForeignKey("sets.id"), nullable=False)
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

    started_at  = Column(DateTime(timezone=True), nullable=True)
    finished_at = Column(DateTime(timezone=True), nullable=True)

    fetched_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now())

    __table_args__ = (
        UniqueConstraint("player_id", "seventeenlands_event_id",
                         name="uq_draft_event_per_player"),
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
    draftmancer_url     = Column(String, nullable=False)
    discord_thread_id   = Column(String, nullable=False)
    sesh_message_id     = Column(String, nullable=False)
    socket_status       = Column(String, nullable=False)
    current_round       = Column(Integer, nullable=True)
    draft_log_gz        = Column(LargeBinary, nullable=True)
    created_at          = Column(DateTime(timezone=True), nullable=False, server_default=func.now())

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
    # Null for guests not yet registered; populated retroactively by /join or /pod-link-arena
    player_id        = Column(String, ForeignKey("players.id"), nullable=True)
    display_name     = Column(String, nullable=False)
    draftmancer_name = Column(String, nullable=True)
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
