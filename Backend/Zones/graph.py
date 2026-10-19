from Backend.Zones.conection import Connection
from Backend.Zones.hub import Hub

class Graph:
    def __init__(self) -> None:
        self.start: Hub | None = None
        self.end: Hub | None = None
        self.n_drones: int = 0
        self.link_dict: dict = {}
        self.nodes_dict: dict = {}

    def test(self):
        print("Link dict:")
        for item in self.link_dict.items():
            print(item)
        print("Nodes dict")
        for item in self.nodes_dict.items():
            print(item)

    def add_node(self, node: Hub) -> None:
        self.nodes_dict[node.name] = node

    def add_link(self, link: Connection) -> None:
        self.link_dict[link.id] = link

    def get_neighbors(self, zone_name: str) -> list[str]:
        neighbors: list[str] = []
        for value in self.link_dict.values():
            if value.from_zone == zone_name:
                neighbors.append(value.to_zone)
            elif value.to_zone == zone_name:
                neighbors.append(value.from_zone)
        return neighbors

"""
if __name__ == "__main__":
    g = Graph()
    zone_1 = Zone(name="zone_1", x=0, y=0, zone_type="Normal")
    zone_2 = Zone(name="zone_2", x=1, y=0, zone_type="Normal")
    zone_3 = Zone(name="zone_3", x=2, y=0, zone_type="Nomal")
    dead_zone = Zone(name="dead_zone", x=2, y= 1, zone_type="Restricted")
    zone_end = Zone(name="end_zone", x=3, y=0, zone_type="Restricted", color="red")    
    zone_1_to_zone_2 = Connection(from_zone=zone_1.name, to_zone=zone_2.name)
    zone_2_to_zone_3 = Connection(from_zone=zone_2.name, to_zone=zone_3.name)
    zone_2_to_dead_zone = Connection(from_zone=zone_2.name, to_zone=dead_zone.name)
    zone_3_to_end = Connection(from_zone=zone_3.name, to_zone=zone_end.name)
    #print(f"No add -> {g.test()}")
    #adding nodes
    g.add_node(zone_1)
    g.add_node(zone_2)
    g.add_node(zone_3)
    g.add_node(dead_zone)
    g.add_node(zone_end)

    g.add_link(zone_1_to_zone_2)
    g.add_link(zone_2_to_zone_3)
    g.add_link(zone_2_to_dead_zone)
    g.add_link(zone_3_to_end)
    #print(f"Added Nodes -> {g.test()}")

    print(f"zone_1 neigbors -> {g.get_neighbors(zone_2.name)}")
"""