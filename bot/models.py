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
    String,
    UniqueConstraint,
)
from sqlalchemy.orm import DeclarativeBase, relationship
from sqlalchemy.sql import func


class Base(DeclarativeBase):
    pass


class Player(Base):
    __tablename__ = "players"

    id                   = Column(String, primary_key=True, default=lambda: str(uuid4()))
    # URL-safe handle derived from display_name at /join, frozen post-creation.
    # Used by the frontend for /player/{slug} routing
    slug                 = Column(String, unique=True, nullable=False)
    discord_id           = Column(String, unique=True, nullable=True)
    discord_username     = Column(String, nullable=True)
    display_name         = Column(String, nullable=False)
    # Discord avatar hash (the asset key, not the full URL). The leaderboard
    # view computes the CDN URL server-side so discord_id never leaves the DB
    avatar_hash          = Column(String, nullable=True)
    seventeenlands_token = Column(String, nullable=False)
    seventeenlands_url   = Column(String, nullable=False)
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
