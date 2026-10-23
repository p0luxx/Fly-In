from __future__ import annotations

import heapq
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Generator

try:
    from Backend.Zones.conection import Connection
    from Backend.Zones.hub import Hub
    from Backend.Zones.hub_type import HubType
    from Backend.Zones.graph import Graph
except ModuleNotFoundError:
    try:
        from Zones.conection import Connection
        from Zones.hub import Hub
        from Zones.hub_type import HubType
        from Zones.graph import Graph
    except ModuleNotFoundError:
        from conection import Connection  # type: ignore
        from hub import Hub  # type: ignore
        from hub_type import HubType  # type: ignore
        from graph import Graph  # type: ignore

try:
    from Backend.Drones.drone import Drone
except ModuleNotFoundError:
    try:
        from Drones.drone import Drone
    except ModuleNotFoundError:
        try:
            from drone import Drone  # type: ignore
        except ModuleNotFoundError:
            class Drone:  # type: ignore
                def __init__(self, id: str, path: list[Connection]) -> None:
                    self.id = id
                    self.path = path
                    self.steps: Generator = self._next_step()
                    self.c_pos: Connection | None = None

                def _next_step(self) -> Generator[Connection, None, None]:
                    for step in self.path:
                        self.c_pos = step
                        yield step


@dataclass(frozen=True)
class ScheduledStep:
    """Representa la acción de un dron en un turno concreto de la simulación."""
    turn: int
    from_zone: str
    to_zone: str
    connection: Connection
    is_wait: bool = False
    is_restricted_transit: bool = False


@dataclass(order=True)
class _SearchNode:
    """Nodo de búsqueda para A* en espacio-tiempo (Space-Time A*)."""
    f_score: tuple[int, int, int, int, str]
    g_turn: int = field(compare=False)
    current_zone: str = field(compare=False)
    departure_turn: int | None = field(compare=False)
    priority_count: int = field(compare=False)
    hops: int = field(compare=False)
    steps: tuple[ScheduledStep, ...] = field(compare=False, default_factory=tuple)


class Solver:
    """
    Resuelve el enrutamiento óptimo de múltiples drones sobre un Graph (Fly-in).

    Combina:
    1. Reverse Dijkstra desde `end_hub` para calcular la heurística exacta de
       turnos mínimos restantes (`h(u)`), podar callejones sin salida (`dead_end`)
       y excluir zonas `HubType.BLOCKED`.
    2. Búsqueda A* en Espacio-Tiempo (Space-Time A*) con tabla de reservas para
       planificar el camino de cada dron respetando:
       - `Hub.max_drones` (capacidad simultánea de cada nodo intermedio).
       - `Connection.max_link_capacity` (capacidad simultánea de cada enlace por turno).
       - `HubType.RESTRICTED` (coste de 2 turnos al entrar: 1 en tránsito + 1 de llegada).
       - `HubType.PRIORITY` (preferencia en caso de empate en turnos totales).
       - `HubType.BLOCKED` (zonas intransitables).
    """

    def __init__(self, graph: Graph, max_turns_limit: int = 5000) -> None:
        self.graph: Graph = graph
        self.max_turns_limit: int = max_turns_limit
        self.heuristics: dict[str, int] = {}
        self.drones: list[Drone] = []
        self.schedules: dict[str, list[ScheduledStep]] = {}
        self.hub_reservations: dict[str, dict[int, int]] = defaultdict(lambda: defaultdict(int))
        self.link_reservations: dict[str, dict[int, int]] = defaultdict(lambda: defaultdict(int))
        self.total_turns: int = 0

    def _validate_graph(self) -> tuple[Hub, Hub]:
        if self.graph.start is None or self.graph.end is None:
            raise ValueError("Error: El grafo debe tener un 'start_hub' y un 'end_hub' definidos.")
        if self.graph.n_drones < 0:
            raise ValueError("Error: El número de drones no puede ser negativo.")
        if (
            self.graph.start.zone == HubType.BLOCKED
            or self.graph.end.zone == HubType.BLOCKED
        ):
            raise ValueError("Error: El nodo de inicio o fin está bloqueado (BLOCKED).")
        return self.graph.start, self.graph.end

    @staticmethod
    def _canonical_link_id(link: Connection) -> str:
        """Identificador canónico independiente del sentido para reservar capacidad."""
        a, b = sorted((link.from_zone, link.to_zone))
        return f"{a}<->{b}"

    @staticmethod
    def _orient_connection(link: Connection, from_zone: str, to_zone: str) -> Connection:
        """Devuelve una Connection orientada en el sentido real del movimiento."""
        if link.from_zone == from_zone and link.to_zone == to_zone:
            return link
        return Connection(
            from_zone=from_zone,
            to_zone=to_zone,
            max_link_capacity=link.max_link_capacity,
        )

    def _compute_backward_heuristics(self) -> None:
        """
        Calcula para cada Hub el número mínimo teórico de turnos hasta `end_hub`
        ignorando congestión (heurística admisible y consistente para A*).
        """
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
                f"Error: No existe ningún camino válido entre '{start_hub.name}' "
                f"y '{end_hub.name}'."
            )

    def _can_occupy_hub(self, hub_name: str, turn: int) -> bool:
        """Comprueba si un Hub tiene capacidad disponible en el turno dado."""
        if hub_name in (self.graph.start.name, self.graph.end.name):
            return True
        hub = self.graph.nodes_dict[hub_name]
        return self.hub_reservations[hub_name][turn] < hub.max_drones

    def _can_use_link(self, link: Connection, turn: int) -> bool:
        """Comprueba si una Connection tiene capacidad disponible en el turno dado."""
        canon_id = self._canonical_link_id(link)
        return self.link_reservations[canon_id][turn] < link.max_link_capacity

    def _reserve_trajectory(self, steps: tuple[ScheduledStep, ...]) -> None:
        """Registra en las tablas de reserva los nodos y enlaces usados por un dron."""
        for step in steps:
            if not step.is_wait:
                canon_id = self._canonical_link_id(step.connection)
                self.link_reservations[canon_id][step.turn] += 1
            if not step.is_restricted_transit:
                if step.to_zone not in (self.graph.start.name, self.graph.end.name):
                    self.hub_reservations[step.to_zone][step.turn] += 1

    def _find_optimal_trajectory_for_drone(self) -> tuple[ScheduledStep, ...]:
        """
        Ejecuta Space-Time A* para encontrar la trayectoria óptima de un dron
        respetando las reservas de los drones previos.
        """
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
        # best_seen[(zone_name, turn)] guarda el mejor (-priority_count, active_time, hops)
        best_seen: dict[tuple[str, int], tuple[int, int, int]] = {}

        while open_heap:
            node = heapq.heappop(open_heap)
            u = node.current_zone
            t = node.g_turn

            if u == end_hub.name:
                return node.steps

            if t >= self.max_turns_limit:
                continue

            active_time = 0 if node.departure_turn is None else (t - node.departure_turn)
            state_key = (u, t)
            state_quality = (-node.priority_count, active_time, node.hops)
            if state_key in best_seen and best_seen[state_key] <= state_quality:
                continue
            best_seen[state_key] = state_quality

            # 1. Explorar movimientos a través de las conexiones vecinas
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
                    # Zona RESTRICTED: turno t+1 en tránsito por el enlace, turno t+2 llega al hub
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
                            is_restricted_transit=False,
                        ),
                    )

                new_departure = t if node.departure_turn is None else node.departure_turn
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

            # 2. Explorar acción de espera (1 turno en el Hub actual)
            if self._can_occupy_hub(u, t + 1):
                wait_conn = Connection(from_zone=u, to_zone=u, max_link_capacity=0)
                if node.departure_turn is None and u == start_hub.name:
                    new_steps = node.steps + (
                        ScheduledStep(
                            turn=t + 1,
                            from_zone=u,
                            to_zone=u,
                            connection=wait_conn,
                            is_wait=True,
                        ),
                    )
                    est_arrival = (t + 1) + self.heuristics[u]
                    est_active = self.heuristics[u]
                    wait_node = _SearchNode(
                        f_score=(est_arrival, -node.priority_count, est_active, node.hops, u),
                        g_turn=t + 1,
                        current_zone=u,
                        departure_turn=None,
                        priority_count=node.priority_count,
                        hops=node.hops,
                        steps=new_steps,
                    )
                    heapq.heappush(open_heap, wait_node)
                else:
                    new_steps = node.steps + (
                        ScheduledStep(
                            turn=t + 1,
                            from_zone=u,
                            to_zone=u,
                            connection=wait_conn,
                            is_wait=True,
                        ),
                    )
                    dep = 0 if node.departure_turn is None else node.departure_turn
                    est_arrival = (t + 1) + self.heuristics[u]
                    est_active = est_arrival - dep
                    wait_node = _SearchNode(
                        f_score=(est_arrival, -node.priority_count, est_active, node.hops, u),
                        g_turn=t + 1,
                        current_zone=u,
                        departure_turn=dep,
                        priority_count=node.priority_count,
                        hops=node.hops,
                        steps=new_steps,
                    )
                    heapq.heappush(open_heap, wait_node)

        raise RuntimeError(
            "No fue posible encontrar una trayectoria libre de colisiones dentro del límite de turnos."
        )

    def solve(
        self,
        include_waits_in_path: bool = False,
        drone_prefix: str = "D",
    ) -> list[Drone]:
        """
        Calcula el camino óptimo para cada dron y devuelve la lista de instancias `Drone`.

        Args:
            include_waits_in_path:
                - `False` (por defecto): `drone.path` contiene únicamente la secuencia limpia
                  de objetos `Connection` desde `start_hub` hasta `end_hub`.
                - `True`: `drone.path` contiene un `Connection` por cada turno de la simulación
                  (incluyendo esperas como `Connection(u, u)` y los 2 turnos de zonas `RESTRICTED`),
                  ideal si se consume `next(drone.steps)` directamente en cada turno sin un
                  gestor de colisiones externo.
            drone_prefix: Prefijo para el ID de cada dron (por defecto `"D"` -> `"D1"`, `"D2"`, ...).
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

    def get_turns_output(self) -> list[str]:
        """
        Genera la salida turno a turno en el formato estándar de Fly-in:
        - Movimiento normal/prioritario: `D1-destino`
        - En tránsito hacia zona restringida (1er turno): `D1-origen-destino`
        - Llegada a zona restringida (2º turno): `D1-destino`
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
        """Devuelve un string con la simulación completa turno por turno."""
        lines = self.get_turns_output()
        if show_turn_prefix:
            return "\n".join(
                f"Turn {idx}: {line}" for idx, line in enumerate(lines, start=1)
            )
        return "\n".join(lines)