*This project has been created as part of the 42 curriculum by gorkgall.*

# Fly-In

## Description
Fly-In is a route-planning and visualization application for multiple drones. The primary goal is to design an efficient drone routing system that navigates a fleet of drones from a central start location to a target end location in the fewest possible simulation turns. The system strictly adheres to movement constraints, zone capacities, and link limits. The map is modeled as a graph of hubs (nodes) and connections (edges). The planner searches for optimal routes while dynamically accounting for hub types (normal, restricted, priority, blocked), hub and connection capacities, and the specific turn durations of certain moves.

## Instructions

### Requirements
- Python **3.10 or newer**.
- Pygame for the visualizer.
- Pydantic 2 for map loading and validation.
- `make` is required to use the Makefile targets on Unix.

### Installation
From the repository root, install dependencies into a virtual environment:
```sh
python3 -m venv venv
source venv/bin/activate
python -m pip install --upgrade pip
python -m pip install pydantic pygame flake8 mypy pytest
```
Alternatively, on Unix systems, simply run:
```sh
make install
```

### Execution
Run a map with the graphical interface (enabled by default):
```sh
python fly_in.py maps/easy/01_linear_path.txt
```
To print the plan without opening the Pygame visualizer:
```sh
python fly_in.py maps/easy/01_linear_path.txt --no-gui
```
To display capacity usage information during the simulation (turn-by-turn):
```sh
python fly_in.py maps/easy/01_linear_path.txt --capacity-info
```

## Algorithm Choices and Implementation Strategy
The core pathfinding relies on a **Space-Time A*** algorithm guided by reverse Dijkstra heuristics.
- **Heuristics:** A reverse search computes the minimum turn distance from the goal to all other hubs, considering restricted zones (which cost 2 turns) and regular zones (1 turn).
- **Space-Time Search:** Drones are planned sequentially. The A* search explores nodes in both space (current hub) and time (current turn) to find the most efficient path without conflicts.
- **Reservation System:** To coordinate multiple drones and prevent collisions, a per-turn reservation table tracks and limits hub and connection capacities. Once a drone's path is found, its footprint (occupied hubs and links per turn) is registered so subsequent drones route around it or wait.
- **Zone Types:** `normal` and `priority` hubs take one turn to cross; `restricted` takes two turns (occupying the incoming connection on the first turn); `blocked` hubs are excluded from all routes. `priority` zones participate in the search's preference ordering to resolve ties.

## Visual Representation
The application features a minimalist, interactive 2D visualizer built with Pygame.

**Visual Features & UX Enhancements:**
- **Dynamic Scaling:** The view automatically computes the bounding box of the graph and scales the nodes to fit the screen size perfectly, maintaining the aspect ratio regardless of window resizing.
- **Turn-by-turn Playback:** Users can scrub through the timeline using the arrow keys, allowing deep, frame-by-frame inspection of complex bottlenecks.
- **AABB Label Positioning:** Node labels intelligently position themselves using a greedy Axis-Aligned Bounding Box (AABB) collision algorithm to prevent text overlapping. This makes dense maps highly readable.
- **Live Capacity Display:** Hubs and drones glow, and connections change colors to indicate active usage during transit.

**Controls:**
- `Space`: Pause or resume.
- `←` / `→`: Step backward or forward by one turn.
- `F`: Toggle fullscreen.
- `N`: Show or hide hub names.
- `Esc`: Close the visualizer.

## Example Input and Expected Output

**Example Input (`map.txt`):**
```text
nb_drones: 2
start_hub: start 0 0
hub: waypoint 1 0 [zone=normal max_drones=1]
end_hub: goal 2 0
connection: start-waypoint
connection: waypoint-goal
```

**Expected Output:**
```text
=== Optimal routes assigned (2 drones) ===
D1: start -> waypoint -> goal (arrives on turn 2)
D2: start -> waypoint -> goal (arrives on turn 3)

=== Turn-by-turn simulation ===
Turn 1: D1-waypoint
Turn 2: D1-goal D2-waypoint
Turn 3: D2-goal

=== Summary ===
Total turns to reach the goal ('goal'): 3
```

## Resources
- **Pathfinding & Graph Theory:** "Multi-Agent Path Finding" (MAPF) literature and standard Space-Time A* algorithms on graphs.
- **Libraries:** [Pygame Documentation](https://www.pygame.org/docs/), [Pydantic Documentation](https://docs.pydantic.dev/).
- **AI Usage:** AI (Large Language Models) was utilized during the development of this project for:
  - Brainstorming architectural approaches for the backend.
  - Refactoring the Pygame frontend into a minimalist, single-file `Renderer` class to comply with strict norm/linting requirements.
  - Implementing the AABB label collision avoidance algorithm for the visualizer.
  - Generating boilerplate code for the Makefile and parsing logic.
  - Consulting on edge cases and optimal heuristic generation in space-time A* search.