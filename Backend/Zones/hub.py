from dataclasses import dataclass
from Backend.Zones.hub_type import HubType

@dataclass
class Hub:
    directive: str
    name: str
    x: int
    y: int
    zone: HubType = HubType.NORMAL
    max_drones: int = 1
    color: str = "white"


"""
if __name__ == "__main__":
    n_zone = Zone(name="start_node", x=0, y=0, zone_type=ZoneType.NORMAL, max_drones=99, color="green")
    print(n_zone)
"""