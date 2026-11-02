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

    hub_reservations: dict[str, dict[int, int]]
    link_reservations: dict[str, dict[int, int]]
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

    def test(self, turn: int) -> str:
        out: list[str] = []
        for name, node in self.graph.nodes_dict.items():
            used = self.hub_reservations[name][turn]
            if used:
                out.append(f"Node name: {name} Capacity={used}/{node.max_drones}")
        for link in self.graph.link_dict.values():
            cot = self._canonical_link_id(link)
            used = self.link_reservations[cot][turn]
            if used:
                out.append(f"Connection:  {cot} -> {used}/{link.max_link_capacity} capacity used")
        if out:
            return f", ".join(out)
        return ""
