# Fly-In

> **Idiomas / Languages:** [Español](#español) · [English](#english)

## Español

Fly-In es una aplicación de planificación y visualización de rutas para varios
drones. El mapa se representa como un grafo de hubs (nodos) y conexiones
(aristas). El planificador busca rutas teniendo en cuenta los tipos y la
capacidad de los hubs, la capacidad de las conexiones y la duración de ciertos
movimientos. Después, la aplicación muestra el plan en la terminal y, de forma
predeterminada, abre un visualizador interactivo con Pygame.

### Características

- Carga mapas de texto con hubs, conexiones, capacidades y tipos de zona.
- Planifica rutas con una búsqueda espacio-tiempo guiada por heurísticas.
- Reserva la capacidad de hubs y conexiones por turno para coordinar drones.
- Trata las zonas restringidas como movimientos de dos turnos y las bloqueadas
  como zonas no transitables.
- Muestra el horario de movimientos en la terminal.
- Reproduce y explora la simulación en un visualizador Pygame.
- Permite ejecutar el planificador sin abrir la interfaz gráfica.

### Requisitos

- Python **3.10 o posterior**.
- Pygame para el visualizador.
- Pydantic 2 para validar y cargar los mapas.
- `make` solo es necesario para usar los objetivos del Makefile en Unix.

El repositorio no incluye actualmente un `requirements.txt` ni un
`pyproject.toml`; las instrucciones siguientes instalan las dependencias
directamente en un entorno virtual.

### Instalación y ejecución en Unix

Los comandos siguientes sirven para Linux y macOS. Ejecútalos desde la raíz del
repositorio:

```sh
python3 --version
python3 -m venv venv
source venv/bin/activate
python -m pip install --upgrade pip
python -m pip install pydantic pygame flake8 mypy pytest
```

Ejecuta un mapa con la interfaz gráfica:

```sh
python fly_in.py maps/easy/01_linear_path.txt
```

El modo gráfico está activado de forma predeterminada. Para imprimir el plan
sin abrir Pygame:

```sh
python fly_in.py maps/easy/01_linear_path.txt --no-gui
```

También puedes usar el Makefile disponible en Unix:

```sh
make install
make lint
```

`make install` crea `venv/` si hace falta e instala las dependencias. `make lint`
ejecuta Flake8 y MyPy. `make clean` elimina el entorno virtual y los cachés
generados. El Makefile actual no define un objetivo de pruebas; para ejecutar
las pruebas desde la raíz usa:

```sh
python -m pytest -q
```

Si el comando `python3` no existe en tu sistema, instala Python 3.10+ o cambia
el intérprete del Makefile, por ejemplo con `make install PYTHON=python3.12`.

### Instalación y ejecución en Windows

Abre PowerShell en la raíz del repositorio. El lanzador `py` permite elegir una
versión instalada; también puedes sustituir `py -3.10` por `python` si ese
comando apunta a Python 3.10 o posterior.

```powershell
py -3.10 --version
py -3.10 -m venv .venv
.\.venv\Scripts\python.exe -m pip install --upgrade pip
.\.venv\Scripts\python.exe -m pip install pydantic pygame flake8 mypy pytest
```

No hace falta activar el entorno virtual: los ejemplos llaman directamente a
su intérprete. Para ejecutar un mapa:

```powershell
.\.venv\Scripts\python.exe fly_in.py maps\easy\01_linear_path.txt
```

Para ejecutar solo el planificador:

```powershell
.\.venv\Scripts\python.exe fly_in.py maps\easy\01_linear_path.txt --no-gui
```

Comprobaciones disponibles en Windows:

```powershell
.\.venv\Scripts\flake8.exe .
.\.venv\Scripts\mypy.exe .
.\.venv\Scripts\python.exe -m pytest -q
```

El Makefile usa rutas y comandos propios de Unix (`venv/bin/...`) y no está
preparado para ejecutarse desde PowerShell o el Símbolo del sistema de Windows.
En Windows, usa los comandos anteriores o un entorno Unix como WSL.

### Uso del programa

La sintaxis general de la línea de comandos es:

```text
python fly_in.py <archivo-de-mapa> [--no-gui]
```

- `<archivo-de-mapa>` es obligatorio y puede ser una ruta relativa a la raíz
  del repositorio o una ruta absoluta.
- `--no-gui` omite el visualizador; el programa sigue imprimiendo el resultado.
- Si no se indica `--no-gui`, se abre Pygame después de planificar las rutas.
- Cierra la ventana con `Esc` o con el control de cierre de la ventana.

Algunos mapas de ejemplo están organizados por dificultad en `maps/easy/`,
`maps/medium/`, `maps/hard/` y `maps/challenger/`. Por ejemplo:

```sh
python fly_in.py maps/medium/03_priority_puzzle.txt --no-gui
```

### Formato de los mapas

Cada directiva ocupa una línea. Las líneas vacías y las líneas cuyo primer
carácter no blanco sea `#` se ignoran. Un mapa mínimo tiene este aspecto:

```text
nb_drones: 2

start_hub: start 0 0 [color=green]
hub: waypoint 1 0 [zone=priority max_drones=2 color=blue]
end_hub: goal 2 0 [color=red]

connection: start-waypoint [max_link_capacity=2]
connection: waypoint-goal
```

Directivas admitidas:

| Directiva | Sintaxis | Significado |
|---|---|---|
| Número de drones | `nb_drones: <entero>` | Cantidad de drones a planificar. |
| Hub inicial | `start_hub: <nombre> <x> <y> [atributos]` | Origen común de los drones. Debe haber exactamente uno. |
| Hub intermedio | `hub: <nombre> <x> <y> [atributos]` | Nodo intermedio opcional. |
| Hub final | `end_hub: <nombre> <x> <y> [atributos]` | Destino común. Debe haber exactamente uno. |
| Conexión | `connection: <origen>-<destino> [atributos]` | Conexión bidireccional entre dos hubs declarados. |

Atributos opcionales de hub:

- `zone=normal`, `zone=priority`, `zone=restricted` o `zone=blocked`.
- `max_drones=<entero>` limita cuántos drones pueden ocupar el hub en un turno.
- `color=<nombre>` define el color que utiliza el visualizador.

Atributo opcional de conexión:

- `max_link_capacity=<entero positivo>` limita los drones que pueden usar esa
  conexión en el mismo turno.

Los atributos se separan por espacios dentro de corchetes. Los hubs tienen por
defecto `zone=normal`, `max_drones=1` y `color=white`; las conexiones tienen por
defecto capacidad `1`. Cada conexión debe referirse a hubs existentes y no
puede conectar un hub consigo mismo. Las zonas terminales inicial y final no
están limitadas por `max_drones`.

### Controles del visualizador

| Control | Acción |
|---|---|
| `Espacio` | Pausar o reanudar. Al reanudar desde el final, reinicia la simulación. |
| `R` | Reiniciar la simulación. |
| `←` / `→` | Pausar y retroceder o avanzar un turno. |
| `↑` / `↓` | Aumentar o reducir la velocidad de reproducción. |
| `F` | Ajustar la cámara al grafo. |
| `N` | Mostrar u ocultar los nombres de los hubs. |
| `D` | Alternar los modos de etiquetas de drones: inteligentes, todas u ocultas. |
| `L` | Alternar conjuntamente las etiquetas de hubs y drones. |
| Rueda del ratón | Acercar o alejar la cámara. |
| Arrastrar con el botón izquierdo | Desplazar la cámara. |
| Clic izquierdo en un dron o hub | Seleccionarlo y mostrar su panel de información. |
| Arrastrar en la barra inferior | Desplazarse por la línea de tiempo. |
| `Esc` | Cerrar el visualizador. |

### Decisiones de diseño y arquitectura

- **Punto de entrada delgado:** `fly_in.py` procesa los argumentos de consola y
  delega el flujo principal en `Backend/orchestrator.py`. Así, la interfaz de
  línea de comandos no contiene la lógica de planificación.
- **Responsabilidades del backend:** `Backend/Parser/map_parser.py` carga y
  valida el mapa; `Backend/Zones/` define hubs, conexiones y el grafo;
  `Backend/Solver/` contiene los datos de planificación, la búsqueda y el
  formato del resultado.
- **Planificación con reservas:** el solver calcula distancias heurísticas
  hacia el destino y busca rutas en el espacio y el tiempo. Planifica los drones
  uno por uno y reserva por turno las capacidades de hubs y conexiones ya
  utilizadas.
- **Tipos de zona:** los hubs `normal` y `priority` se atraviesan en un turno;
  `restricted` requiere dos turnos; `blocked` se excluye de las rutas. Las zonas
  `priority` participan en el orden de preferencia de la búsqueda.
- **Frontend separado por función:** `Frontend/visualizer.py` conserva el
  estado de simulación; `visualizer_runtime.py` gestiona eventos y el bucle de
  Pygame; `visualizer_rendering.py` dibuja la escena; `visualizer_support.py`
  reúne utilidades, cámara, etiquetas y efectos. `visualizer_context.py` tipa el
  estado compartido por las capas.
- **Salida y GUI independientes:** el solver puede producir una salida textual
  y el orquestador puede ejecutarse con `--no-gui`, lo que simplifica el uso en
  terminales, automatizaciones y pruebas.

### Pruebas y calidad del código

Desde la raíz del repositorio y con las dependencias instaladas:

```sh
python -m pytest -q
flake8 .
mypy .
```

En Windows, usa las rutas a los ejecutables del entorno virtual indicadas en la
sección de instalación. `make lint` agrupa Flake8 y MyPy en Unix.

## English

Fly-In is a route-planning and visualization application for multiple drones.
It models a map as a graph of hubs (nodes) and connections (edges). The planner
searches for routes while accounting for hub types, hub and connection
capacities, and the duration of certain moves. The application prints the plan
to the terminal and, by default, opens an interactive Pygame visualizer.

### Features

- Loads text maps containing hubs, connections, capacities, and zone types.
- Plans routes with heuristic-guided space-time search.
- Reserves hub and connection capacity per turn to coordinate drones.
- Models restricted zones as two-turn moves and blocked zones as impassable.
- Prints the movement schedule to the terminal.
- Plays and explores the simulation in a Pygame visualizer.
- Supports headless route planning without opening the GUI.

### Requirements

- Python **3.10 or newer**.
- Pygame for the visualizer.
- Pydantic 2 for map loading and validation.
- `make` is only required to use the Makefile targets on Unix.

The repository currently has no `requirements.txt` or `pyproject.toml`; the
instructions below install dependencies directly into a virtual environment.

### Installation and running on Unix

The following commands work on Linux and macOS. Run them from the repository
root:

```sh
python3 --version
python3 -m venv venv
source venv/bin/activate
python -m pip install --upgrade pip
python -m pip install pydantic pygame flake8 mypy pytest
```

Run a map with the graphical interface:

```sh
python fly_in.py maps/easy/01_linear_path.txt
```

The GUI is enabled by default. To print the plan without opening Pygame:

```sh
python fly_in.py maps/easy/01_linear_path.txt --no-gui
```

You can also use the Makefile available on Unix:

```sh
make install
make lint
```

`make install` creates `venv/` if needed and installs the dependencies.
`make lint` runs Flake8 and MyPy. `make clean` removes the virtual environment
and generated caches. The current Makefile does not define a test target; run
the tests from the repository root with:

```sh
python -m pytest -q
```

If `python3` is not available on your system, install Python 3.10+ or override
the Makefile interpreter, for example with
`make install PYTHON=python3.12`.

### Installation and running on Windows

Open PowerShell at the repository root. The `py` launcher can select an
installed Python version; you can replace `py -3.10` with `python` if that
command points to Python 3.10 or newer.

```powershell
py -3.10 --version
py -3.10 -m venv .venv
.\.venv\Scripts\python.exe -m pip install --upgrade pip
.\.venv\Scripts\python.exe -m pip install pydantic pygame flake8 mypy pytest
```

Activating the virtual environment is optional because these examples call its
interpreter directly. Run a map with the GUI:

```powershell
.\.venv\Scripts\python.exe fly_in.py maps\easy\01_linear_path.txt
```

Run route planning without the GUI:

```powershell
.\.venv\Scripts\python.exe fly_in.py maps\easy\01_linear_path.txt --no-gui
```

Available Windows checks:

```powershell
.\.venv\Scripts\flake8.exe .
.\.venv\Scripts\mypy.exe .
.\.venv\Scripts\python.exe -m pytest -q
```

The Makefile uses Unix-specific paths and commands (`venv/bin/...`) and is not
configured for PowerShell or Windows Command Prompt. Use the commands above
on native Windows, or run the Makefile in a Unix-like environment such as WSL.

### Using the application

The general command-line syntax is:

```text
python fly_in.py <map-file> [--no-gui]
```

- `<map-file>` is required and may be relative to the repository root or an
  absolute path.
- `--no-gui` skips the visualizer; the program still prints its results.
- Without `--no-gui`, Pygame opens after route planning.
- Close the visualizer with `Esc` or the window's close control.

Example maps are grouped by difficulty in `maps/easy/`, `maps/medium/`,
`maps/hard/`, and `maps/challenger/`. For example:

```sh
python fly_in.py maps/medium/03_priority_puzzle.txt --no-gui
```

### Map format

Each directive occupies one line. Blank lines and lines whose first
non-whitespace character is `#` are ignored. A minimal map looks like this:

```text
nb_drones: 2

start_hub: start 0 0 [color=green]
hub: waypoint 1 0 [zone=priority max_drones=2 color=blue]
end_hub: goal 2 0 [color=red]

connection: start-waypoint [max_link_capacity=2]
connection: waypoint-goal
```

Supported directives:

| Directive | Syntax | Meaning |
|---|---|---|
| Drone count | `nb_drones: <integer>` | Number of drones to plan for. |
| Start hub | `start_hub: <name> <x> <y> [attributes]` | Shared drone origin. Exactly one is required. |
| Intermediate hub | `hub: <name> <x> <y> [attributes]` | Optional intermediate node. |
| End hub | `end_hub: <name> <x> <y> [attributes]` | Shared destination. Exactly one is required. |
| Connection | `connection: <from>-<to> [attributes]` | Bidirectional connection between two declared hubs. |

Optional hub attributes:

- `zone=normal`, `zone=priority`, `zone=restricted`, or `zone=blocked`.
- `max_drones=<integer>` limits the number of drones that can occupy the hub
  during a turn.
- `color=<name>` sets the color used by the visualizer.

Optional connection attribute:

- `max_link_capacity=<positive integer>` limits the number of drones that can
  use that connection during the same turn.

Separate attributes with spaces inside square brackets. Hubs default to
`zone=normal`, `max_drones=1`, and `color=white`; connections default to
capacity `1`. Every connection must refer to existing hubs and cannot connect
a hub to itself. The start and end terminal hubs are not limited by
`max_drones`.

### Visualizer controls

| Control | Action |
|---|---|
| `Space` | Pause or resume. Resuming after completion restarts the simulation. |
| `R` | Restart the simulation. |
| `←` / `→` | Pause and step backward or forward by one turn. |
| `↑` / `↓` | Increase or decrease playback speed. |
| `F` | Fit the camera to the graph. |
| `N` | Show or hide hub names. |
| `D` | Cycle drone-label modes: smart, all, or hidden. |
| `L` | Toggle hub and drone labels together. |
| Mouse wheel | Zoom in or out. |
| Left-button drag | Pan the camera. |
| Left-click a drone or hub | Select it and show its information panel. |
| Drag the bottom bar | Scrub through the timeline. |
| `Esc` | Close the visualizer. |

### Design decisions and architecture

- **Thin entry point:** `fly_in.py` parses command-line arguments and delegates
  the main workflow to `Backend/orchestrator.py`. Route-planning logic therefore
  stays out of the command-line interface.
- **Backend responsibilities:** `Backend/Parser/map_parser.py` loads and
  validates maps; `Backend/Zones/` defines hubs, connections, and the graph;
  `Backend/Solver/` contains planning data structures, route search, and output
  formatting.
- **Reservation-based planning:** the solver computes heuristic distances to
  the destination and searches in space and time. Drones are planned one at a
  time, reserving the per-turn capacities of hubs and connections already used.
- **Zone types:** `normal` and `priority` hubs take one turn to cross;
  `restricted` takes two turns; `blocked` hubs are excluded from routes.
  `priority` zones participate in the search's preference ordering.
- **Frontend separation:** `Frontend/visualizer.py` owns simulation state;
  `visualizer_runtime.py` handles events and the Pygame loop;
  `visualizer_rendering.py` draws the scene; `visualizer_support.py` contains
  utilities, camera, labels, and effects. `visualizer_context.py` types the
  state shared by these layers.
- **Independent text and GUI output:** the solver can format a textual
  schedule, and the orchestrator supports `--no-gui`, making terminal use,
  automation, and tests easier.

### Tests and code quality

From the repository root, with dependencies installed:

```sh
python -m pytest -q
flake8 .
mypy .
```

On Windows, use the virtual-environment executable paths shown in the
installation section. On Unix, `make lint` runs Flake8 and MyPy together.
