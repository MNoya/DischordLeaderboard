from uuid import uuid4

from sqlalchemy import (
    Boolean,
    Column,
    Date,
    DateTime,
    Float,
    ForeignKey,
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
    discord_id           = Column(String, unique=True, nullable=True)
    discord_username     = Column(String, nullable=True)
    display_name         = Column(String, nullable=False)
    seventeenlands_token = Column(String, nullable=False)
    seventeenlands_url   = Column(String, nullable=False)
    active               = Column(Boolean, nullable=False, default=True)
    joined_at            = Column(DateTime, nullable=False, server_default=func.now())
    updated_at           = Column(DateTime, nullable=False, server_default=func.now(), onupdate=func.now())
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
    last_fetched_at = Column(DateTime, nullable=True)

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
    last_calculated_at = Column(DateTime, nullable=False, server_default=func.now(), onupdate=func.now())

    __table_args__ = (
        UniqueConstraint("player_id", "set_id", name="uq_player_set_score"),
    )


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

    started_at  = Column(DateTime, nullable=True)
    finished_at = Column(DateTime, nullable=True)

    fetched_at = Column(DateTime, nullable=False, server_default=func.now(), onupdate=func.now())

    __table_args__ = (
        UniqueConstraint("player_id", "seventeenlands_event_id",
                         name="uq_draft_event_per_player"),
    )
