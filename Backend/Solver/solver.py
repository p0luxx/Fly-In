"""Public solver API for planning collision-free drone routes."""
from __future__ import annotations

from collections import defaultdict

from Backend.Drones.drone import Drone
from Backend.Solver.models import ScheduledStep
from Backend.Solver.pathfinding import _Pathfinding
from Backend.Solver.solution_output import _SolutionOutput
from Backend.Zones.conection import Connection
from Backend.Zones.graph import Graph
from Backend.Zones.hub import Hub
from Backend.Zones.hub_type import HubType

__all__ = [
    "Connection",
    "Drone",
    "Graph",
    "Hub",
    "HubType",
    "ScheduledStep",
    "Solver",
]


class Solver(_Pathfinding, _SolutionOutput):
    """
    Plan optimal routes for multiple drones on a Fly-In graph.

    Combines reverse Dijkstra heuristics with space-time A* and capacity
    reservations for hubs and connections.
    """

    def __init__(self, graph: Graph, max_turns_limit: int = 5000) -> None:
        self.graph: Graph = graph
        self.max_turns_limit: int = max_turns_limit
        self.heuristics: dict[str, int] = {}
        self.drones: list[Drone] = []
        self.schedules: dict[str, list[ScheduledStep]] = {}
        self.hub_reservations: dict[str, dict[int, int]] = defaultdict(
            lambda: defaultdict(int)
        )
        self.link_reservations: dict[str, dict[int, int]] = defaultdict(
            lambda: defaultdict(int)
        )
        self.total_turns: int = 0

    def solve(
        self,
        include_waits_in_path: bool = False,
        drone_prefix: str = "D",
    ) -> list[Drone]:
        """
        Find an optimal path for each drone and return the created drones.

        Args:
            include_waits_in_path: Include wait steps and restricted-transit
                steps in each drone's path. When false, paths contain only
                completed connections from start to end.
            drone_prefix: Prefix for drone IDs, such as ``"D"`` for ``"D1"``.
        """
        self._validate_graph()
        self.drones.clear()
        self.schedules.clear()
        self.hub_reservations.clear()
        self.link_reservations.clear()
        self.total_turns = 0

        if self.graph.n_drones == 0:
            return []

        self._compute_backward_heuristics()

        for i in range(1, self.graph.n_drones + 1):
            drone_id = f"{drone_prefix}{i}"
            trajectory = self._find_optimal_trajectory_for_drone()
            self._reserve_trajectory(trajectory)
            self.schedules[drone_id] = list(trajectory)

            if trajectory:
                self.total_turns = max(self.total_turns, trajectory[-1].turn)

            if include_waits_in_path:
                drone_path = [step.connection for step in trajectory]
            else:
                drone_path = [
                    step.connection
                    for step in trajectory
                    if not step.is_wait and not step.is_restricted_transit
                ]

            self.drones.append(Drone(id=drone_id, path=drone_path))

        return self.drones
