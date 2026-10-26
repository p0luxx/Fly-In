"""Main simulation state and public entry point for the Fly-In frontend."""
from __future__ import annotations

import math
import random
from collections import deque

import pygame

from Backend.Solver.solver import ScheduledStep, Solver
from Backend.Zones.graph import Graph
from Frontend.visualizer_runtime import _PygameRuntime
from Frontend.visualizer_support import (
    DREAM_PALETTE,
    DroneRenderState,
    GlowCache,
    OrganicLabelEngine,
    Shockwave,
    SmoothCamera2D,
    SmoothLabelState,
    clamp,
    ease_in_out_sine,
    exp_decay,
    golden_angle_drone_color,
    resolve_color,
    smoothstep,
)

__all__ = [
    "DREAM_PALETTE",
    "DroneRenderState",
    "FlyInVisualizer",
    "GlowCache",
    "OrganicLabelEngine",
    "Shockwave",
    "SmoothCamera2D",
    "SmoothLabelState",
    "clamp",
    "ease_in_out_sine",
    "exp_decay",
    "golden_angle_drone_color",
    "resolve_color",
    "smoothstep",
]


class FlyInVisualizer(_PygameRuntime):
    """Simulation state and orchestration for the interactive visualizer."""

    BG_TOP = (8, 10, 22)
    BG_BOTTOM = (18, 23, 46)
    PANEL_BG = (14, 18, 36, 218)
    PANEL_BORDER = (95, 125, 190, 115)
    TEXT_BRIGHT = (240, 245, 255)
    TEXT_SOFT = (165, 182, 218)
    TEXT_ACCENT = (115, 228, 255)

    def __init__(
        self,
        graph: Graph,
        solver: Solver,
        width: int = 1420,
        height: int = 860,
    ) -> None:
        self.graph = graph
        self.solver = solver
        self.width = width
        self.height = height

        # Continuous simulation clock
        self.sim_time: float = 0.0
        self.playing: bool = True
        self.turns_per_sec: float = 1.15

        # Label modes:
        # drone_label_mode: 0 = Smart (active), 1 = All, 2 = Hidden
        self.show_node_names: bool = True
        self.drone_label_mode: int = 0

        # Interactive selection and inspection
        self.selected_hub: str | None = None
        self.selected_drone: str | None = None
        self.hovered_hub: str | None = None
        self.hovered_drone: str | None = None

        # Indexed simulation structures
        self.step_map: dict[str, dict[int, ScheduledStep]] = {}
        self.arrival_turns: dict[str, int] = {}
        self.departure_turns: dict[str, int] = {}
        self.drone_colors: dict[str, tuple[int, int, int]] = {}
        self.trails: dict[str, deque[tuple[float, float]]] = {}
        self.shockwaves: list[Shockwave] = []
        self._triggered_arrivals: set[str] = set()
        self._init_simulation_structures()

        # Auxiliary engines
        self.glow = GlowCache()
        self.camera = SmoothCamera2D(width, height)
        self.camera.fit_graph(graph, instant=True)
        self.label_engine = OrganicLabelEngine(graph)

        # Cache text surfaces to avoid rerendering fonts every frame
        self._node_text_cache: dict[str, pygame.Surface] = {}
        self._drone_text_cache: dict[str, pygame.Surface] = {}
        self._bg_surface: pygame.Surface | None = None

        # Starfield with multilayer parallax
        rng = random.Random(42)
        self.stars = [
            (
                rng.uniform(0, 2000),
                rng.uniform(0, 1400),
                rng.uniform(1.0, 2.5),
                rng.uniform(0.08, 0.35),  # Parallax factor
                rng.uniform(0.0, math.pi * 2.0),  # Twinkle phase
            )
            for _ in range(85)
        ]

    def _init_simulation_structures(self) -> None:
        for idx, drone in enumerate(self.solver.drones):
            self.drone_colors[drone.id] = golden_angle_drone_color(idx)
            steps = self.solver.schedules.get(drone.id, [])
            self.step_map[drone.id] = {s.turn: s for s in steps}
            self.arrival_turns[drone.id] = steps[-1].turn if steps else 0

            dep = 0
            for s in steps:
                if not s.is_wait:
                    dep = s.turn - 1
                    break
            self.departure_turns[drone.id] = dep
            self.trails[drone.id] = deque(maxlen=22)

    def _drone_zone_at_turn(self, drone_id: str, turn_idx: int) -> str:
        start_name = self.graph.start.name if self.graph.start else ""
        end_name = self.graph.end.name if self.graph.end else ""
        if turn_idx <= 0:
            return start_name
        arrival = self.arrival_turns.get(drone_id, 0)
        if arrival > 0 and turn_idx >= arrival:
            return end_name
        step = self.step_map.get(drone_id, {}).get(turn_idx)
        return step.to_zone if step is not None else start_name

    def _compute_drone_kinematics(
        self, drone_id: str, sim_t: float
    ) -> tuple[float, float, float, str, str, bool, bool]:
        """
        Calculate the continuous position (wx, wy), heading angle, group key,
        readable status, and activity flags.
        """
        start_hub = self.graph.start
        end_hub = self.graph.end
        assert start_hub is not None and end_hub is not None

        if sim_t <= 0.0:
            return (
                float(start_hub.x),
                float(start_hub.y),
                -math.pi * 0.5,
                f"hub:{start_hub.name}",
                f"At start ({start_hub.name})",
                False,
                False,
            )

        arrival_t = self.arrival_turns.get(drone_id, 0)
        if arrival_t == 0 or sim_t >= float(arrival_t):
            return (
                float(end_hub.x),
                float(end_hub.y),
                -math.pi * 0.5,
                f"hub:{end_hub.name}",
                f"At goal ({end_hub.name})",
                False,
                False,
            )

        current_turn = int(math.floor(sim_t)) + 1
        raw_alpha = sim_t - math.floor(sim_t)

        d_steps = self.step_map.get(drone_id, {})
        step = d_steps.get(current_turn)

        if step is None or step.is_wait:
            zone_name = (
                step.from_zone
                if step is not None
                else self._drone_zone_at_turn(drone_id, current_turn - 1)
            )
            hub = self.graph.nodes_dict[zone_name]
            is_active = zone_name not in (start_hub.name, end_hub.name)
            status = (
                f"Waiting at {zone_name}"
                if is_active
                else f"Ready at {zone_name}"
            )
            return (
                float(hub.x),
                float(hub.y),
                -math.pi * 0.5,
                f"hub:{zone_name}",
                status,
                is_active,
                False,
            )

        u = self.graph.nodes_dict[step.from_zone]
        v = self.graph.nodes_dict[step.to_zone]
        heading = math.atan2(-(v.y - u.y), float(v.x - u.x))

        # Check whether the drone was moving on the previous turn or will continue
        # on the next one, so it can maintain speed through intermediate hubs.
        prev_step = d_steps.get(current_turn - 1)
        next_step = d_steps.get(current_turn + 1)
        continuous_entry = (
            prev_step is not None
            and not prev_step.is_wait
            and prev_step.to_zone == step.from_zone
        )
        continuous_exit = (
            next_step is not None
            and not next_step.is_wait
            and next_step.from_zone == step.to_zone
        )

        if continuous_entry and continuous_exit:
            # Blend linear and sine easing to preserve momentum through a hub.
            alpha = 0.45 * raw_alpha + 0.55 * ease_in_out_sine(raw_alpha)
        else:
            alpha = ease_in_out_sine(raw_alpha)

        # Case 1: First turn entering a RESTRICTED hub (first half of the edge).
        if step.is_restricted_transit:
            frac = 0.5 * ease_in_out_sine(raw_alpha)
            return (
                u.x + (v.x - u.x) * frac,
                u.y + (v.y - u.y) * frac,
                heading,
                f"edge:{u.name}->{v.name}:1",
                f"Restricted transit {u.name} → {v.name} (1/2)",
                True,
                True,
            )

        # Case 2: Second turn entering a RESTRICTED hub (second half of the edge).
        if prev_step is not None and prev_step.is_restricted_transit:
            frac = 0.5 + 0.5 * ease_in_out_sine(raw_alpha)
            return (
                u.x + (v.x - u.x) * frac,
                u.y + (v.y - u.y) * frac,
                heading,
                f"edge:{u.name}->{v.name}:2",
                f"Landing at {v.name} [RESTRICTED] (2/2)",
                True,
                True,
            )

        # Case 3: Standard transit (1 turn).
        return (
            u.x + (v.x - u.x) * alpha,
            u.y + (v.y - u.y) * alpha,
            heading,
            f"edge:{u.name}->{v.name}",
            f"Flying {u.name} → {v.name}",
            True,
            False,
        )

    def _compute_all_drones_render_state(
        self, elapsed: float
    ) -> tuple[list[DroneRenderState], dict[str, list[str]]]:
        """Calculate drones' screen positions and orbital formations."""
        raw: list[tuple[str, float, float, float, str, str, bool, bool]] = []
        groups: dict[str, list[str]] = {}

        for drone in self.solver.drones:
            wx, wy, heading, gkey, status, is_active, in_rest = (
                self._compute_drone_kinematics(drone.id, self.sim_time)
            )
            raw.append((drone.id, wx, wy, heading, gkey, status, is_active, in_rest))
            groups.setdefault(gkey, []).append(drone.id)

            # Detect arrival at the goal and launch a harmonic shockwave.
            arr_t = self.arrival_turns.get(drone.id, 0)
            if arr_t > 0 and self.sim_time >= float(arr_t):
                if drone.id not in self._triggered_arrivals and self.graph.end:
                    self._triggered_arrivals.add(drone.id)
                    self.shockwaves.append(
                        Shockwave(
                            x=float(self.graph.end.x),
                            y=float(self.graph.end.y),
                            color=self.drone_colors[drone.id],
                        )
                    )
            else:
                self._triggered_arrivals.discard(drone.id)

        states: list[DroneRenderState] = []
        for did, wx, wy, heading, gkey, status, is_active, in_rest in raw:
            sx, sy = self.camera.to_screen_float(wx, wy)
            members = groups[gkey]
            if len(members) > 1:
                idx = members.index(did)
                angle = (2.0 * math.pi * idx) / len(members) + elapsed * 0.85
                orbit_px = min(22.0, 6.5 + len(members) * 1.15)
                sx += math.cos(angle) * orbit_px
                sy += math.sin(angle) * orbit_px

            states.append(
                DroneRenderState(
                    drone_id=did,
                    wx=wx,
                    wy=wy,
                    sx=sx,
                    sy=sy,
                    heading_rad=heading,
                    group_key=gkey,
                    status_text=status,
                    is_active=is_active,
                    in_restricted=in_rest,
                )
            )

            if self.playing and is_active:
                self.trails[did].append((wx, wy))

        return states, groups
