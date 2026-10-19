from pydantic import BaseModel, Field, model_validator
from typing import Any
from Backend.Zones.hub import Hub
from Backend.Zones.conection import Connection
from Backend.Zones.hub_type import HubType

class MapParser(BaseModel):
    file_name: str
    content: list[str] = Field(default_factory=list, exclude=True)
    nb_drones: int = 0
    hubs: list[Hub] = Field(default_factory=list)
    connections: list[Connection] = Field(default_factory=list)

    @model_validator(mode='after')
    def procesar_archivo_automaticamente(self) -> 'MapParser':
        self._read_file()
        self._parse_and_route()
        start_hub: bool = sum(1 for x in self.hubs if x.directive == "start_hub") == 1
        end_hub: bool = sum(1 for y in self.hubs if y.directive == "end_hub") == 1
        if start_hub and end_hub:
            return self
        else:
            raise ValueError("Error: start or end hub syntax directive not founded!")

    def _read_file(self) -> None:
        try:
            with open(self.file_name, 'r', encoding="utf-8") as f:
                raw_lines = f.readlines()
        except PermissionError as e:
            raise PermissionError(f"Ocurrió un error de permisos: {e}")
        except FileNotFoundError as e:
            raise FileNotFoundError(f"No se ha encontrado el archivo {self.file_name}: {e}")
        
        self.content = [
            s.strip() for s in raw_lines 
            if not s.strip().startswith("#") and len(s.strip()) > 0
        ]

    def _parse_and_route(self) -> None:
        try:
            for line in self.content:
                if ":" not in line:
                    raise ValueError("Invalid Syntax")
                key, value = [part.strip() for part in line.split(":", 1)]
                match key:
                    case "nb_drones":
                        self._drone_processing(value)
                    case "start_hub" | "hub" | "end_hub":
                        self._hub_processor(key, value)
                    case "connection":
                        self._connection_processor(value)
                    case _:
                        raise ValueError(f"Unknown directive on the map: {key}")
        except ValueError as e:
            raise ValueError(f"Error: {e}")

    def _drone_processing(self, value: str) -> None:
        self.nb_drones = int(value)

    def _hub_processor(self, directive: str, value: str) -> str | None:
            dir: str = directive
            cl: list[str] = value.split("[", 1)
            parts: list[str] = cl[0].split()
            if len(parts) != 3:
                raise ValueError("Missing name, x, or y coordinates.")
            name, x_str, y_str = parts
            
            # Cambiado de dict[str, str] a dict[str, Any] para permitir tipos mixtos
            extras: dict[str, Any] = {}
            if len(cl) > 1:
                extra_raw = cl[1].strip()
                if not extra_raw.endswith("]"):
                    raise ValueError("Syntax error: ']' not found")
                extra_content = extra_raw[:-1]
                for text in extra_content.split():
                    k, v = text.split("=", 1)
                    # Convertimos a entero si es numérico para alinear con lo que espera Hub (ej. int)
                    try:
                        if v.lstrip('-').isnumeric():
                            extras[k] = int(v)
                        elif k == "zone":
                            extras[k] = HubType[v.upper()]
                        else:
                            extras[k] = v
                    except KeyError:
                        raise ValueError("Invalid value: Likely in type_zone parametter!")
            
            new_hub: Hub = Hub(
                directive=dir,
                name=name, 
                x=int(x_str), 
                y=int(y_str), 
                **extras
            )
            self.hubs.append(new_hub)
            return None

    def _connection_processor(self, value: str) -> None:
        value = value.strip()
        parts: list[str] = value.split("[", 1)
        route_str: str = parts[0].strip()
        if "-" not in route_str:
            raise ValueError(f"Sintaxis de conexión inválida (falta '-'): '{route_str}'")
        route_parts: list[str] = route_str.split("-", 1)
        from_zone: str = route_parts[0].strip()
        to_zone: str = route_parts[1].strip()
        if not from_zone or not to_zone:
            raise ValueError(f"Falta un nodo de origen o destino en: '{route_str}'")
        capacity: int = 1
        if len(parts) > 1:
            extra_raw: str = parts[1].strip()
            if not extra_raw.endswith("]"):
                raise ValueError(f"Error de sintaxis: Falta ']' al final de la conexión '{value}'")
            extra_content: str = extra_raw[:-1]
            for item in extra_content.split():
                if "=" in item:
                    k, v = item.split("=", 1)
                    if k == "max_link_capacity":
                        if v.isdigit():
                            capacity = int(v)
                        else:
                            raise ValueError(f"Valor inválido para max_link_capacity: '{v}' (debe ser entero positivo)")

        new_link: Connection = Connection(
            from_zone=from_zone, 
            to_zone=to_zone, 
            max_link_capacity=capacity
        )
        self.connections.append(new_link)

"""
    def test(self) -> None:
        while True:
            val: str = input("nb_drones | start_hub_end | connection -> ").lower()
            match val:
                case "nb_drones":
                    print(self.nb_drones)
                case "start_hub" | "hub" | "end_hub":
                    for zone in self.hubs:
                        print(f"{zone.directive}-> {zone}")
                case "connection":
                    print(self.connections)
                case "content":
                    print(self.content)
                case _:
                    continue
"""