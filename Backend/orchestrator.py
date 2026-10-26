"""Coordinate map loading, route planning, output, and optional visualization."""
from __future__ import annotations

from pathlib import Path

from Backend.Parser.map_parser import MapParser
from Backend.Drones.drone import Drone
from Backend.Solver.solver import Solver
from Backend.Zones.graph import Graph


class Orchestrator:
    """Run the central Fly-In application workflow."""

    def run(self, map_file: str | Path, use_gui: bool = True) -> None:
        """Load a map, plan drone routes, print results, and optionally show the GUI."""
        content = MapParser(file_name=str(map_file))
        graph = self._build_graph(content)
        solver = Solver(graph)
        drones = solver.solve()
        self._print_results(graph, solver, drones)

        if use_gui:
            from Frontend.visualizer import FlyInVisualizer

            print("\nInitializing visualizer...")
            FlyInVisualizer(graph=graph, solver=solver).run()

    @staticmethod
    def _build_graph(content: MapParser) -> Graph:
        graph = Graph()
        for hub in content.hubs:
            graph.add_node(hub)
        for connection in content.connections:
            graph.add_link(connection)
        graph.n_drones = content.nb_drones
        return graph

    @staticmethod
    def _print_results(graph: Graph, solver: Solver, drones: list[Drone]) -> None:
        start_name = graph.start.name if graph.start else "start"
        end_name = graph.end.name if graph.end else "goal"

        print(f"=== Optimal routes assigned ({graph.n_drones} drones) ===")
        for drone in drones:
            route_nodes = [start_name] + [
                connection.to_zone for connection in drone.path
            ]
            route = " -> ".join(route_nodes)
            schedule = solver.schedules.get(drone.id, [])
            arrival_turn = schedule[-1].turn if schedule else 0
            print(f"{drone.id}: {route} (arrives on turn {arrival_turn})")

        print("\n=== Turn-by-turn simulation ===")
        simulation_output = solver.format_solution(show_turn_prefix=True)
        print(
            simulation_output
            if simulation_output
            else "No moves are required."
        )

        print("\n=== Summary ===")
        print(
            f"Total turns to reach the goal ('{end_name}'): {solver.total_turns}"
        )
