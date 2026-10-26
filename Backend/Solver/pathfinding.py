"""Graph validation, capacity reservations, and space-time route search."""
from __future__ import annotations

import heapq

from Backend.Solver.models import ScheduledStep, _SearchNode
from Backend.Zones.conection import Connection
from Backend.Zones.hub import Hub
from Backend.Zones.hub_type import HubType
from Backend.Zones.graph import Graph

__all__ = ["_Pathfinding"]


class _Pathfinding:
    """Route-search behavior mixed into the public solver."""

    graph: Graph
    heuristics: dict[str, int]
    hub_reservations: dict[str, dict[int, int]]
    link_reservations: dict[str, dict[int, int]]
    max_turns_limit: int

    def _validate_graph(self) -> tuple[Hub, Hub]:
        if self.graph.start is None or self.graph.end is None:
            raise ValueError(
                "The graph must define both a 'start_hub' and an 'end_hub'."
            )
        if self.graph.n_drones < 0:
            raise ValueError("The number of drones cannot be negative.")
        if (
            self.graph.start.zone == HubType.BLOCKED
            or self.graph.end.zone == HubType.BLOCKED
        ):
            raise ValueError("The start or end hub is blocked (BLOCKED).")
        return self.graph.start, self.graph.end

    @staticmethod
    def _canonical_link_id(link: Connection) -> str:
        """Return a direction-independent identifier for a connection."""
        a, b = sorted((link.from_zone, link.to_zone))
        return f"{a}<->{b}"

    @staticmethod
    def _orient_connection(
        link: Connection, from_zone: str, to_zone: str
    ) -> Connection:
        """Orient a connection in the direction of travel."""
        if link.from_zone == from_zone and link.to_zone == to_zone:
            return link
        return Connection(
            from_zone=from_zone,
            to_zone=to_zone,
            max_link_capacity=link.max_link_capacity,
        )

    def _compute_backward_heuristics(self) -> None:
        """Compute the admissible minimum-turn distance to the end hub."""
        start_hub, end_hub = self._validate_graph()
        dist: dict[str, int] = {end_hub.name: 0}
        pq: list[tuple[int, str]] = [(0, end_hub.name)]

        while pq:
            current_cost, current_name = heapq.heappop(pq)
            if current_cost > dist.get(current_name, float("inf")):
                continue

            current_hub = self.graph.nodes_dict[current_name]
            step_cost = 2 if current_hub.zone == HubType.RESTRICTED else 1

            for link in self.graph.get_neighbors(current_name):
                if link.max_link_capacity <= 0:
                    continue
                neighbor_name = link.get_destination(current_name)
                neighbor_hub = self.graph.nodes_dict.get(neighbor_name)
                if neighbor_hub is None or neighbor_hub.zone == HubType.BLOCKED:
                    continue
                if neighbor_name != start_hub.name and neighbor_hub.max_drones <= 0:
                    continue

                new_cost = current_cost + step_cost
                if new_cost < dist.get(neighbor_name, float("inf")):
                    dist[neighbor_name] = new_cost
                    heapq.heappush(pq, (new_cost, neighbor_name))

        self.heuristics = dist
        if start_hub.name not in self.heuristics:
            raise ValueError(
                f"No valid route exists between '{start_hub.name}' "
                f"and '{end_hub.name}'."
            )

    def _can_occupy_hub(self, hub_name: str, turn: int) -> bool:
        """Check whether a hub has capacity available on the given turn."""
        start_hub, end_hub = self._validate_graph()
        if hub_name in (start_hub.name, end_hub.name):
            return True
        hub = self.graph.nodes_dict[hub_name]
        return self.hub_reservations[hub_name][turn] < hub.max_drones

    def _can_use_link(self, link: Connection, turn: int) -> bool:
        """Check whether a connection has capacity available on the given turn."""
        canon_id = self._canonical_link_id(link)
        return self.link_reservations[canon_id][turn] < link.max_link_capacity

    def _reserve_trajectory(self, steps: tuple[ScheduledStep, ...]) -> None:
        """Record the hubs and connections used by a drone."""
        start_hub, end_hub = self._validate_graph()
        for step in steps:
            if not step.is_wait:
                canon_id = self._canonical_link_id(step.connection)
                self.link_reservations[canon_id][step.turn] += 1
            if not step.is_restricted_transit:
                if step.to_zone not in (start_hub.name, end_hub.name):
                    self.hub_reservations[step.to_zone][step.turn] += 1

    def _find_optimal_trajectory_for_drone(self) -> tuple[ScheduledStep, ...]:
        """Find a collision-free route while respecting earlier reservations."""
        start_hub, end_hub = self._validate_graph()
        start_h = self.heuristics[start_hub.name]

        initial_node = _SearchNode(
            f_score=(start_h, 0, 0, 0, start_hub.name),
            g_turn=0,
            current_zone=start_hub.name,
            departure_turn=None,
            priority_count=0,
            hops=0,
            steps=(),
        )

        open_heap: list[_SearchNode] = [initial_node]
        # Keep the best (-priority_count, active_time, hops) for each zone and turn.
        best_seen: dict[tuple[str, int], tuple[int, int, int]] = {}

        while open_heap:
            node = heapq.heappop(open_heap)
            u = node.current_zone
            t = node.g_turn

            if u == end_hub.name:
                return node.steps

            if t >= self.max_turns_limit:
                continue

            active_time = (
                0 if node.departure_turn is None else t - node.departure_turn
            )
            state_key = (u, t)
            state_quality = (-node.priority_count, active_time, node.hops)
            if state_key in best_seen and best_seen[state_key] <= state_quality:
                continue
            best_seen[state_key] = state_quality

            # 1. Explore moves along neighboring connections.
            for link in self.graph.get_neighbors(u):
                if link.max_link_capacity <= 0:
                    continue
                v = link.get_destination(u)
                if v not in self.heuristics:
                    continue

                v_hub = self.graph.nodes_dict[v]
                move_cost = 2 if v_hub.zone == HubType.RESTRICTED else 1
                arrival_turn = t + move_cost

                if move_cost == 1:
                    if not self._can_use_link(link, t + 1):
                        continue
                    if not self._can_occupy_hub(v, t + 1):
                        continue
                    oriented = self._orient_connection(link, u, v)
                    new_steps = node.steps + (
                        ScheduledStep(
                            turn=t + 1,
                            from_zone=u,
                            to_zone=v,
                            connection=oriented,
                        ),
                    )
                else:
                    # Restricted transit uses t+1 and reaches the hub on t+2.
                    if not (
                        self._can_use_link(link, t + 1)
                        and self._can_use_link(link, t + 2)
                    ):
                        continue
                    if not self._can_occupy_hub(v, t + 2):
                        continue
                    oriented = self._orient_connection(link, u, v)
                    new_steps = node.steps + (
                        ScheduledStep(
                            turn=t + 1,
                            from_zone=u,
                            to_zone=v,
                            connection=oriented,
                            is_restricted_transit=True,
                        ),
                        ScheduledStep(
                            turn=t + 2,
                            from_zone=u,
                            to_zone=v,
                            connection=oriented,
                        ),
                    )

                new_departure = (
                    t if node.departure_turn is None else node.departure_turn
                )
                new_priority = node.priority_count + (
                    1 if v_hub.zone == HubType.PRIORITY else 0
                )
                new_hops = node.hops + 1
                est_arrival = arrival_turn + self.heuristics[v]
                est_active = est_arrival - new_departure

                next_node = _SearchNode(
                    f_score=(est_arrival, -new_priority, est_active, new_hops, v),
                    g_turn=arrival_turn,
                    current_zone=v,
                    departure_turn=new_departure,
                    priority_count=new_priority,
                    hops=new_hops,
                    steps=new_steps,
                )
                heapq.heappush(open_heap, next_node)

            # 2. Explore waiting for one turn at the current hub.
            if self._can_occupy_hub(u, t + 1):
                wait_conn = Connection(from_zone=u, to_zone=u, max_link_capacity=0)
                new_steps = node.steps + (
                    ScheduledStep(
                        turn=t + 1,
                        from_zone=u,
                        to_zone=u,
                        connection=wait_conn,
                        is_wait=True,
                    ),
                )
                if node.departure_turn is None and u == start_hub.name:
                    dep = None
                    est_active = self.heuristics[u]
                else:
                    dep = 0 if node.departure_turn is None else node.departure_turn
                    est_active = (t + 1) + self.heuristics[u] - dep

                est_arrival = (t + 1) + self.heuristics[u]
                wait_node = _SearchNode(
                    f_score=(
                        est_arrival,
                        -node.priority_count,
                        est_active,
                        node.hops,
                        u,
                    ),
                    g_turn=t + 1,
                    current_zone=u,
                    departure_turn=dep,
                    priority_count=node.priority_count,
                    hops=node.hops,
                    steps=new_steps,
                )
                heapq.heappush(open_heap, wait_node)

        raise RuntimeError(
            "Could not find a collision-free route within the turn limit."
        )
