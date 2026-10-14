from typing import Optional
from pydantic import BaseModel, Field, model_validator

# --- Estructuras de datos puras ---
# Pydantic se encargará de validar que x, y, o max_drones sean enteros.
class Node(BaseModel):
    nombre: str
    tipo: str
    x: int
    y: int
    color: Optional[str] = None
    max_drones: Optional[int] = None

class Edge(BaseModel):
    origen: str
    destino: str
    max_link_capacity: Optional[int] = None

class MapParser(BaseModel):
    file_name: str 
    content: list[str] = Field(default_factory=list, exclude=True) # exclude=True oculta esto si exportas a JSON
    nb_drones: int = 0
    hubs: list[Node] = Field(default_factory=list)
    connections: list[Edge] = Field(default_factory=list)

    @model_validator(mode='after')
    def procesar_archivo_automaticamente(self) -> 'MapParser':
        self._read_file()
        self._parse_and_route()
        return self

    def _read_file(self):
        try:
            with open(self.file_name, 'r', encoding="utf-8") as f:
                raw_lines = f.readlines()
        except PermissionError as e:
            raise PermissionError(f"Ocurrió un error de permisos: {e}")
        except FileNotFoundError as e:
            raise FileNotFoundError(f"No se ha encontrado el archivo {self.file_name}: {e}")
        self.content = [s.strip() for s in raw_lines if not s.strip().startswith("#") and len(s.strip()) > 0]

    def _parse_and_route(self):
        for linea_limpia in self.content:
            if ':' not in linea_limpia:
                raise ValueError(f"Sintaxis inválida (falta ':'): {linea_limpia}")
            
            clave, valor = [parte.strip() for parte in linea_limpia.split(':', 1)]

            match clave:
                case "nb_drones":
                    self._procesar_drones(valor)
                case "start_hub" | "hub" | "end_hub":
                    self._procesar_hub(clave, valor)
                case "connection":
                    self._procesar_conexion(valor)
                case _:
                    raise ValueError(f"Directiva desconocida en el mapa: {clave}")

    def _procesar_drones(self, valor: str):
        self.nb_drones = int(valor)

    def _procesar_hub(self, tipo: str, valor: str):
        partes = valor.split('[')
        coords = partes[0].split()
        nombre = coords[0]
        x = coords[1]
        y = coords[2]

        atributos_extra = {}
        if len(partes) > 1:
            extras_str = partes[1].replace(']', '')
            for par in extras_str.split():
                k, v = par.split('=')
                atributos_extra[k] = v
        nuevo_nodo = Node(
            nombre=nombre,
            tipo=tipo,
            x=x,
            y=y,
            **atributos_extra
        )
        self.hubs.append(nuevo_nodo)

    def _procesar_conexion(self, valor: str):
        partes = valor.split('[')
        nodos = partes[0].strip().split('-')        
        atributos_extra = {}
        if len(partes) > 1:
            extras_str = partes[1].replace(']', '')
            for par in extras_str.split():
                k, v = par.split('=')
                atributos_extra[k] = v
        nueva_conexion = Edge(
            origen=nodos[0],
            destino=nodos[1],
            **atributos_extra
        )
        self.connections.append(nueva_conexion)