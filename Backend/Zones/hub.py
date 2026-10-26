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
