from conection import Connection
from zone import Zone

class Graph:
    def __init__(self) -> None:
        self.start: Zone = None
        self.end: Zone = None
        self.n_drones: int = 0
        self.link_dict: dict = {}
        self.nodes_dict: dict = {}

    def add_node(self, node: Zone) -> None:
        self.nodes_dict[node.name] = node

    def add_link(self, link: Connection) -> None:
        self.link_dict[link.id] = link

    def get_neighbors(self, node: Zone) -> list[str]:
        pass
    
    