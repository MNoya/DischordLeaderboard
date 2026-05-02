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
