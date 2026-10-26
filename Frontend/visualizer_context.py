"""Typed shared state for the visualizer's runtime and rendering layers."""
from __future__ import annotations

from collections import deque
from typing import ClassVar

import pygame

from Backend.Solver.models import ScheduledStep
from Backend.Solver.solver import Solver
from Backend.Zones.graph import Graph
from Frontend.visualizer_support import (
    DroneRenderState,
    GlowCache,
    OrganicLabelEngine,
    Shockwave,
    SmoothCamera2D,
)


class _VisualizerContext:
    """State and operations shared by the visualizer's focused mixins."""

    BG_TOP: ClassVar[tuple[int, int, int]]
    BG_BOTTOM: ClassVar[tuple[int, int, int]]
    PANEL_BG: ClassVar[tuple[int, int, int, int]]
    PANEL_BORDER: ClassVar[tuple[int, int, int, int]]
    TEXT_BRIGHT: ClassVar[tuple[int, int, int]]
    TEXT_SOFT: ClassVar[tuple[int, int, int]]
    TEXT_ACCENT: ClassVar[tuple[int, int, int]]

    graph: Graph
    solver: Solver
    width: int
    height: int
    sim_time: float
    playing: bool
    turns_per_sec: float
    show_node_names: bool
    drone_label_mode: int
    selected_hub: str | None
    selected_drone: str | None
    hovered_hub: str | None
    hovered_drone: str | None
    step_map: dict[str, dict[int, ScheduledStep]]
    arrival_turns: dict[str, int]
    departure_turns: dict[str, int]
    drone_colors: dict[str, tuple[int, int, int]]
    trails: dict[str, deque[tuple[float, float]]]
    shockwaves: list[Shockwave]
    _triggered_arrivals: set[str]
    glow: GlowCache
    camera: SmoothCamera2D
    label_engine: OrganicLabelEngine
    _node_text_cache: dict[str, pygame.Surface]
    _drone_text_cache: dict[str, pygame.Surface]
    _bg_surface: pygame.Surface | None
    stars: list[tuple[float, float, float, float, float]]

    def _init_simulation_structures(self) -> None: ...

    def _drone_zone_at_turn(self, drone_id: str, turn_idx: int) -> str:
        raise NotImplementedError

    def _compute_drone_kinematics(
        self, drone_id: str, sim_t: float
    ) -> tuple[float, float, float, str, str, bool, bool]:
        raise NotImplementedError

    def _compute_all_drones_render_state(
        self, elapsed: float
    ) -> tuple[list[DroneRenderState], dict[str, list[str]]]:
        raise NotImplementedError
