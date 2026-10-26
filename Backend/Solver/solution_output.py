"""Formatting of solver schedules for command-line and textual output."""
from __future__ import annotations

from collections import defaultdict

from Backend.Drones.drone import Drone
from Backend.Zones.graph import Graph

__all__ = ["_SolutionOutput"]


class _SolutionOutput:
    """Schedule formatting behavior mixed into the public solver."""

    schedules: dict
    graph: Graph
    total_turns: int

    def solve(
        self,
        include_waits_in_path: bool = False,
        drone_prefix: str = "D",
    ) -> list[Drone]:
        raise NotImplementedError

    def get_turns_output(self) -> list[str]:
        """
        Generate the standard turn-by-turn Fly-In output:
        - Normal or priority move: `D1-destination`
        - Restricted transit (first turn): `D1-origin-destination`
        - Restricted arrival (second turn): `D1-destination`
        """
        if not self.schedules and self.graph.n_drones > 0:
            self.solve()

        turns_dict: dict[int, list[str]] = defaultdict(list)
        for drone_id, steps in self.schedules.items():
            for step in steps:
                if step.is_wait:
                    continue
                if step.is_restricted_transit:
                    turns_dict[step.turn].append(
                        f"{drone_id}-{step.from_zone}-{step.to_zone}"
                    )
                else:
                    turns_dict[step.turn].append(f"{drone_id}-{step.to_zone}")

        return [
            " ".join(turns_dict[t])
            for t in range(1, self.total_turns + 1)
            if turns_dict[t]
        ]

    def format_solution(self, show_turn_prefix: bool = False) -> str:
        """Return the complete turn-by-turn simulation as a string."""
        lines = self.get_turns_output()
        if show_turn_prefix:
            return "\n".join(
                f"Turn {idx}: {line}" for idx, line in enumerate(lines, start=1)
            )
        return "\n".join(lines)
