from dataclasses import dataclass
from zone_type import ZoneType

@dataclass
class Zone:
    name: str
    x: int
    y: int
    zone_type: ZoneType = ZoneType.NORMAL
    max_drones: int = 1
    color: str = "white"


"""
if __name__ == "__main__":
    n_zone = Zone(name="start_node", x=0, y=0, zone_type=ZoneType.NORMAL, max_drones=99, color="green")
    print(n_zone)
"""