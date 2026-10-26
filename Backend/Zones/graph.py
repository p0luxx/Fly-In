from Backend.Zones.conection import Connection
from Backend.Zones.hub import Hub


class Graph:
    def __init__(self) -> None:
        self.start: Hub | None = None
        self.end: Hub | None = None
        self.n_drones: int = 0
        self.link_dict: dict[str, Connection] = {}
        self.nodes_dict: dict[str, Hub] = {}
        self.adj: dict[str, list[Connection]] = {}

    def test(self):
        print("Link dict:")
        for item in self.link_dict.items():
            print(item)
        print("Nodes dict")
        for item in self.nodes_dict.items():
            print(item)

    def add_node(self, node: Hub) -> None:
        if node.directive == "start_hub":
            self.start = node
        elif node.directive == "end_hub":
            self.end = node
        self.nodes_dict[node.name] = node
        self.adj[node.name] = []

    def add_link(self, link: Connection) -> None:
        if link.from_zone in self.nodes_dict and link.to_zone in self.nodes_dict:
            if link.from_zone != link.to_zone:
                self.link_dict[link.id] = link
                self.adj[link.from_zone].append(link)
                self.adj[link.to_zone].append(link)
            else:
                raise ValueError(
                    "A node connected to itself in a bidirectional manner "
                    "has been detected.\nClosing Fly-In..."
                )
        else:
            raise ValueError(
                "An orphaned node has been detected.\nClosing Fly-In..."
            )

    def get_neighbors(self, zone_name: str) -> list[Connection]:
        return self.adj.get(zone_name, [])
