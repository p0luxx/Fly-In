from typing import Optional
from pydantic import BaseModel, Field, model_validator
from ..Zones.zone import Zone
from ..Zones.conection import Connection

# --- Tu Parser Evolucionado ---
class MapParser(BaseModel):
    file_name: str
    content: list[str] = Field(default_factory=list, exclude=True) # exclude=True oculta esto si exportas a JSON
    nb_drones: int = 0
    hubs: list[Zone] = Field(default_factory=list)
    connections: list[Connection] = Field(default_factory=list)

    @model_validator(mode='after')
    def procesar_archivo_automaticamente(self) -> 'MapParser':
        # Primero, ejecutamos tu lógica para poblar self.content
        self._read_file()
        
        # Segundo, desempaquetamos esos strings y los enrutamos
        self._parse_and_route()
        
        return self

    # Tu método original, ahora como un método interno de soporte
    def _read_file(self):
        try:
            with open(self.file_name, 'r', encoding="utf-8") as f:
                raw_lines = f.readlines()
        except PermissionError as e:
            raise PermissionError(f"Ocurrió un error de permisos: {e}")
        except FileNotFoundError as e:
            raise FileNotFoundError(f"No se ha encontrado el archivo {self.file_name}: {e}")
        
        # Tu misma lógica de limpieza: sin comentarios y sin líneas vacías
        self.content = [s.strip() for s in raw_lines if not s.strip().startswith("#") and len(s.strip()) > 0]

    # 3. El Enrutador: Aquí ocurre el desempaquetado y la delegación de responsabilidades
    def _parse_and_route(self):
        for linea_limpia in self.content:
            # Dividimos la línea en dos partes: "comando" y "argumentos"
            # ej: "hub: junction 1 0 [color=yellow]" -> ["hub", "junction 1 0 [color=yellow]"]
            if ':' not in linea_limpia:
                raise ValueError(f"Sintaxis inválida (falta ':'): {linea_limpia}")
            
            clave, valor = [parte.strip() for parte in linea_limpia.split(':', 1)]

            # Usamos match-case para dirigir los argumentos a su método correspondiente
            match clave:
                case "nb_drones":
                    self._procesar_drones(valor)
                case "start_hub" | "hub" | "end_hub":
                    self._procesar_hub(clave, valor)
                case "connection":
                    self._procesar_conexion(valor)
                case _:
                    # Aquí usarías tu ParsingError personalizado
                    raise ValueError(f"Directiva desconocida en el mapa: {clave}")

    # --- Los métodos de procesamiento (La lógica de negocio real) ---

    def _procesar_drones(self, valor: str):
        # Pydantic hará la conversión a int por nosotros si lo asignamos al modelo, 
        # pero como estamos operando sobre la instancia ya creada, lo convertimos.
        self.nb_drones = int(valor)

    def _procesar_hub(self, tipo: str, valor: str):
        # Desempaquetado simple de un string: "junction 1 0 [color=yellow max_drones=2]"
        partes = valor.split('[')
        coords = partes[0].split()
        nombre = coords[0]
        x = coords[1]
        y = coords[2]

        atributos_extra = {}
        if len(partes) > 1:
            # Limpiamos el ']' final y extraemos los extras
            extras_str = partes[1].replace(']', '')
            for par in extras_str.split():
                k, v = par.split('=')
                atributos_extra[k] = v

        # Delegamos a Pydantic la creación y validación final del nodo
        nuevo_nodo = Zone(
            nombre=nombre,
            tipo=tipo,
            x=x, # Le pasamos strings, Node(BaseModel) los convierte a enteros de forma segura
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

        nueva_conexion = Connection(
            origen=nodos[0],
            destino=nodos[1],
            **atributos_extra
        )
        self.connections.append(nueva_conexion)