"""Data structures used by the drone route planner."""
from __future__ import annotations

from dataclasses import dataclass, field

from Backend.Zones.conection import Connection


@dataclass(frozen=True)
class ScheduledStep:
    """A drone action scheduled for a specific simulation turn."""

    turn: int
    from_zone: str
    to_zone: str
    connection: Connection
    is_wait: bool = False
    is_restricted_transit: bool = False


@dataclass(order=True)
class _SearchNode:
    """A* search node in space-time."""

    f_score: tuple[int, int, int, int, str]
    g_turn: int = field(compare=False)
    current_zone: str = field(compare=False)
    departure_turn: int | None = field(compare=False)
    priority_count: int = field(compare=False)
    hops: int = field(compare=False)
    steps: tuple[ScheduledStep, ...] = field(compare=False, default_factory=tuple)
