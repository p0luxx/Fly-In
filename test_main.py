import sys
from Backend import MapParser, Graph

# Importación flexible del Solver (soporta Backend/Solver/solver.py)
try:
    from Backend.Solver.solver import Solver
except ModuleNotFoundError:
    try:
        from Backend.solver import Solver
    except ModuleNotFoundError:
        from solver import Solver

# Importación flexible del Visualizador Pygame
try:
    from Frontend.visualizer import FlyInVisualizer
except ModuleNotFoundError:
    try:
        from Backend.Visualizer.visualizer import FlyInVisualizer
    except ModuleNotFoundError:
        try:
            from visualizer import FlyInVisualizer
        except ModuleNotFoundError:
            FlyInVisualizer = None  # type: ignore


def main() -> None:
    args = [arg for arg in sys.argv[1:] if arg != "--no-gui"]
    use_gui = "--no-gui" not in sys.argv[1:]

    if len(args) == 1:
        try:
            name: str = args[0]
            content: MapParser = MapParser(file_name=name)
            graph: Graph = Graph()

            for node in content.hubs:
                graph.add_node(node)
            for link in content.connections:
                graph.add_link(link)
            graph.n_drones = content.nb_drones

            # 1. Resolver rutas óptimas
            solver: Solver = Solver(graph)
            drones = solver.solve()

            start_name: str = graph.start.name if graph.start else "start"
            end_name: str = graph.end.name if graph.end else "goal"

            print(f"=== Rutas óptimas asignadas ({graph.n_drones} drones) ===")
            for drone in drones:
                route_nodes = [start_name] + [conn.to_zone for conn in drone.path]
                route_str = " -> ".join(route_nodes)
                schedule = solver.schedules.get(drone.id, [])
                arrival_turn = schedule[-1].turn if schedule else 0
                print(f"{drone.id}: {route_str} (Llega en el turno {arrival_turn})")

            print("\n=== Simulación por turnos ===")
            simulation_output = solver.format_solution(show_turn_prefix=True)
            if simulation_output:
                print(simulation_output)
            else:
                print("No se requieren movimientos.")

            print("\n=== Resumen ===")
            print(
                f"Número total de turnos en llegar a la meta ('{end_name}'): "
                f"{solver.total_turns}"
            )

            # 2. Lanzar la visualización en Pygame
            if use_gui:
                if FlyInVisualizer is None:
                    print(
                        "\n[Aviso] No se encontró 'visualizer.py' o Pygame no está instalado.",
                        file=sys.stderr,
                    )
                else:
                    print("\nIniciando visualizador Pygame...")
                    visualizer = FlyInVisualizer(graph=graph, solver=solver)
                    visualizer.run()

        except (ValueError, FileNotFoundError, PermissionError, RuntimeError) as e:
            print(e, file=sys.stderr)
            sys.exit(1)

    elif len(args) > 1:
        print(
            f"Se proporcionaron más archivos de los requeridos\n"
            f"Uso correcto: python3 {sys.argv[0]} 'archivo.txt' [--no-gui]",
            file=sys.stderr,
        )
        sys.exit(1)
    else:
        print(
            f"Uso incorrecto, faltan argumentos\n"
            f"Uso correcto: python3 {sys.argv[0]} 'archivo.txt' [--no-gui]",
            file=sys.stderr,
        )
        sys.exit(1)


if __name__ == "__main__":
    main()