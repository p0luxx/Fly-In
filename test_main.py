from Backend import MapParser, Graph
import sys

if __name__ == "__main__":
    if len(sys.argv) == 2:
        try:
            name: str = sys.argv[1]
            content: MapParser = MapParser(file_name=name)
            graph: Graph = Graph()
            for node in content.hubs:
                    graph.add_node(node)
            for link in content.connections:
                    graph.add_link(link)
            graph.n_drones = content.nb_drones
            #futura llamada al solver aqui.
            print(graph.adj)
        except ValueError as e:
            print(e)
            sys.exit(1)
    elif len(sys.argv) > 2:
        print(f"Se proporcionaron mas archivos de los requeridos\n"
              f"Uso correcto: {sys.argv[0]} 'archivo.txt'")
        sys.exit(1)
    else:
        print(f"Uso incorrecto, faltan argumentos\nUso correcto: {sys.argv[0]} 'archivo.txt'")
        sys.exit(1)