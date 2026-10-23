from __future__ import annotations

import colorsys
import math
from typing import TYPE_CHECKING

import pygame

if TYPE_CHECKING:
    from Backend.Solver.solver import ScheduledStep, Solver
    from Backend.Zones.conection import Connection
    from Backend.Zones.graph import Graph
    from Backend.Zones.hub import Hub

try:
    from Backend.Zones.hub_type import HubType
except ModuleNotFoundError:
    try:
        from Zones.hub_type import HubType
    except ModuleNotFoundError:
        from hub_type import HubType  # type: ignore


# Diccionario extendido de colores para soportar todos los mapas (incluido 'rainbow')
NAMED_COLORS: dict[str, tuple[int, int, int]] = {
    "white": (235, 240, 245),
    "black": (45, 50, 60),
    "red": (230, 65, 65),
    "darkred": (150, 30, 35),
    "crimson": (220, 20, 60),
    "maroon": (140, 40, 70),
    "green": (46, 204, 113),
    "blue": (52, 152, 219),
    "yellow": (241, 196, 15),
    "gold": (255, 215, 0),
    "orange": (230, 126, 34),
    "purple": (155, 89, 182),
    "violet": (180, 110, 230),
    "brown": (160, 100, 60),
    "cyan": (26, 188, 156),
    "gray": (149, 165, 166),
}


def resolve_color(color_name: str, time_sec: float = 0.0) -> tuple[int, int, int]:
    """Convierte el atributo `Hub.color` en una tupla RGB válida para Pygame."""
    clean = color_name.strip().lower()
    if clean == "rainbow":
        r, g, b = colorsys.hsv_to_rgb((time_sec * 0.35) % 1.0, 0.85, 1.0)
        return int(r * 255), int(g * 255), int(b * 255)
    if clean in NAMED_COLORS:
        return NAMED_COLORS[clean]
    try:
        c = pygame.Color(clean)
        return c.r, c.g, c.b
    except ValueError:
        return NAMED_COLORS["white"]


def drone_distinct_color(index: int, total: int) -> tuple[int, int, int]:
    """Genera un color único y brillante para cada dron usando el círculo cromático HSV."""
    hue = (index / max(1, total)) % 1.0
    r, g, b = colorsys.hsv_to_rgb(hue, 0.75, 1.0)
    return int(r * 255), int(g * 255), int(b * 255)


class Camera2D:
    """Gestiona la transformación entre coordenadas lógicas del grafo y píxeles de pantalla."""

    def __init__(self, width: int, height: int) -> None:
        self.width = width
        self.height = height
        self.offset_x = 0.0
        self.offset_y = 0.0
        self.zoom = 100.0

    def fit_graph(self, graph: Graph, margin_px: int = 130) -> None:
        if not graph.nodes_dict:
            return
        xs = [node.x for node in graph.nodes_dict.values()]
        ys = [node.y for node in graph.nodes_dict.values()]
        min_x, max_x = min(xs), max(xs)
        min_y, max_y = min(ys), max(ys)

        span_x = max(1.0, float(max_x - min_x))
        span_y = max(1.0, float(max_y - min_y))

        usable_w = max(200, self.width - 2 * margin_px)
        usable_h = max(200, self.height - 2 * margin_px - 80)

        self.zoom = min(usable_w / span_x, usable_h / span_y)
        self.zoom = max(35.0, min(self.zoom, 180.0))

        center_x = (min_x + max_x) / 2.0
        center_y = (min_y + max_y) / 2.0

        self.offset_x = (self.width / 2.0) - center_x * self.zoom
        self.offset_y = (self.height / 2.0) + center_y * self.zoom

    def world_to_screen(self, x: float, y: float) -> tuple[int, int]:
        """Invierte el eje Y para que +Y apunte hacia arriba como en un plano cartesiano."""
        sx = int(self.offset_x + x * self.zoom)
        sy = int(self.offset_y - y * self.zoom)
        return sx, sy

    def zoom_at(self, mouse_pos: tuple[int, int], factor: float) -> None:
        mx, my = mouse_pos
        wx = (mx - self.offset_x) / self.zoom
        wy = (self.offset_y - my) / self.zoom

        self.zoom = max(20.0, min(self.zoom * factor, 350.0))

        self.offset_x = mx - wx * self.zoom
        self.offset_y = my + wy * self.zoom


class FlyInVisualizer:
    """Visualizador interactivo en Pygame para la simulación de drones Fly-in."""

    BG_COLOR = (15, 18, 26)
    GRID_COLOR = (26, 31, 44)
    PANEL_BG = (22, 27, 38)
    PANEL_BORDER = (55, 65, 85)
    TEXT_MAIN = (230, 236, 245)
    TEXT_DIM = (145, 158, 178)

    def __init__(
        self,
        graph: Graph,
        solver: Solver,
        width: int = 1360,
        height: int = 820,
    ) -> None:
        self.graph = graph
        self.solver = solver
        self.width = width
        self.height = height

        # Estado de la línea temporal:
        # `sim_time` va desde 0.0 hasta float(solver.total_turns).
        # El intervalo [k - 1.0, k] representa la transición del Turno k.
        self.sim_time: float = 0.0
        self.playing: bool = True
        self.turns_per_sec: float = 1.25
        self.show_labels: bool = True

        # Indexación rápida de pasos por dron y por turno: step_map[drone_id][turn]
        self.step_map: dict[str, dict[int, ScheduledStep]] = {}
        self.arrival_turns: dict[str, int] = {}
        self.drone_colors: dict[str, tuple[int, int, int]] = {}
        self._prepare_simulation_data()

        self.camera = Camera2D(width, height)
        self.camera.fit_graph(graph)

    def _prepare_simulation_data(self) -> None:
        total = max(1, len(self.solver.drones))
        for idx, drone in enumerate(self.solver.drones):
            self.drone_colors[drone.id] = drone_distinct_color(idx, total)
            steps = self.solver.schedules.get(drone.id, [])
            self.step_map[drone.id] = {step.turn: step for step in steps}
            self.arrival_turns[drone.id] = steps[-1].turn if steps else 0

    def _get_drone_zone_at_integer_turn(self, drone_id: str, turn_idx: int) -> str:
        """Devuelve el nombre del Hub donde se encuentra un dron al final del turno entero `turn_idx`."""
        start_name = self.graph.start.name if self.graph.start else ""
        end_name = self.graph.end.name if self.graph.end else ""

        if turn_idx <= 0:
            return start_name
        arrival = self.arrival_turns.get(drone_id, 0)
        if arrival > 0 and turn_idx >= arrival:
            return end_name

        step = self.step_map.get(drone_id, {}).get(turn_idx)
        if step is not None:
            return step.to_zone
        return start_name

    def _compute_drone_world_state(
        self, drone_id: str, sim_t: float
    ) -> tuple[float, float, str, bool]:
        """
        Calcula la posición continua (x, y) en coordenadas del mundo, la clave de agrupación
        (para separar visualmente drones que comparten nodo/arista) y si está en tránsito RESTRICTED.
        """
        start_hub = self.graph.start
        end_hub = self.graph.end
        assert start_hub is not None and end_hub is not None

        if sim_t <= 0.0:
            return float(start_hub.x), float(start_hub.y), f"hub:{start_hub.name}", False

        arrival_t = self.arrival_turns.get(drone_id, 0)
        if arrival_t == 0 or sim_t >= float(arrival_t):
            return float(end_hub.x), float(end_hub.y), f"hub:{end_hub.name}", False

        # Turno que se está ejecutando actualmente (1 .. total_turns)
        current_turn = int(math.floor(sim_t)) + 1
        alpha = sim_t - math.floor(sim_t)  # Progreso dentro del turno actual [0.0, 1.0)

        d_steps = self.step_map.get(drone_id, {})
        step = d_steps.get(current_turn)

        if step is None:
            zone_name = self._get_drone_zone_at_integer_turn(drone_id, current_turn - 1)
            hub = self.graph.nodes_dict[zone_name]
            return float(hub.x), float(hub.y), f"hub:{zone_name}", False

        if step.is_wait:
            hub = self.graph.nodes_dict[step.from_zone]
            return float(hub.x), float(hub.y), f"hub:{step.from_zone}", False

        u_hub = self.graph.nodes_dict[step.from_zone]
        v_hub = self.graph.nodes_dict[step.to_zone]

        # Caso 1: Primer turno entrando a una zona RESTRICTED (viaja de 0.0 a 0.5 de la arista)
        if step.is_restricted_transit:
            frac = 0.5 * alpha
            wx = u_hub.x + (v_hub.x - u_hub.x) * frac
            wy = u_hub.y + (v_hub.y - u_hub.y) * frac
            return wx, wy, f"edge:{step.from_zone}->{step.to_zone}:1", True

        # Caso 2: Segundo turno entrando a una zona RESTRICTED (viaja de 0.5 a 1.0 de la arista)
        prev_step = d_steps.get(current_turn - 1)
        if prev_step is not None and prev_step.is_restricted_transit:
            frac = 0.5 + 0.5 * alpha
            wx = u_hub.x + (v_hub.x - u_hub.x) * frac
            wy = u_hub.y + (v_hub.y - u_hub.y) * frac
            return wx, wy, f"edge:{step.from_zone}->{step.to_zone}:2", True

        # Caso 3: Movimiento estándar de 1 turno (viaja de 0.0 a 1.0 de la arista)
        wx = u_hub.x + (v_hub.x - u_hub.x) * alpha
        wy = u_hub.y + (v_hub.y - u_hub.y) * alpha
        return wx, wy, f"edge:{step.from_zone}->{step.to_zone}", False

    def _draw_grid(self, surface: pygame.Surface) -> None:
        step_px = max(25, int(self.camera.zoom))
        start_x = int(self.camera.offset_x) % step_px
        start_y = int(self.camera.offset_y) % step_px

        for x in range(start_x, self.width, step_px):
            pygame.draw.line(surface, self.GRID_COLOR, (x, 0), (x, self.height), 1)
        for y in range(start_y, self.height, step_px):
            pygame.draw.line(surface, self.GRID_COLOR, (0, y), (self.width, y), 1)

    def _draw_connections(
        self, surface: pygame.Surface, font_small: pygame.font.Font
    ) -> None:
        active_turn = min(self.solver.total_turns, int(math.floor(self.sim_time)) + 1)
        if self.sim_time >= self.solver.total_turns or self.sim_time <= 0.0:
            active_turn = int(round(self.sim_time))

        for link in self.graph.link_dict.values():
            u = self.graph.nodes_dict[link.from_zone]
            v = self.graph.nodes_dict[link.to_zone]
            p1 = self.camera.world_to_screen(u.x, u.y)
            p2 = self.camera.world_to_screen(v.x, v.y)

            canon_id = self.solver._canonical_link_id(link)
            used = self.solver.link_reservations[canon_id].get(active_turn, 0)

            if used > 0:
                line_color = (80, 210, 255)
                thickness = max(3, int(2 + link.max_link_capacity * 1.5))
            else:
                line_color = (75, 88, 110)
                thickness = max(2, int(1 + link.max_link_capacity))

            pygame.draw.line(surface, line_color, p1, p2, thickness)

            # Mostrar etiqueta de capacidad si max_link_capacity > 1 o está en uso
            if self.show_labels and (link.max_link_capacity > 1 or used > 0):
                mx, my = (p1[0] + p2[0]) // 2, (p1[1] + p2[1]) // 2
                cap_str = f"{used}/{link.max_link_capacity}"
                badge = font_small.render(cap_str, True, (220, 230, 245))
                bg_rect = badge.get_rect(center=(mx, my)).inflate(8, 4)
                pygame.draw.rect(surface, (30, 38, 54), bg_rect, border_radius=4)
                pygame.draw.rect(surface, line_color, bg_rect, width=1, border_radius=4)
                surface.blit(badge, badge.get_rect(center=(mx, my)))

    def _draw_hubs(
        self,
        surface: pygame.Surface,
        font_node: pygame.font.Font,
        font_small: pygame.font.Font,
        elapsed_sec: float,
    ) -> None:
        node_radius = int(max(13.0, min(28.0, self.camera.zoom * 0.24)))

        for hub in self.graph.nodes_dict.values():
            sx, sy = self.camera.world_to_screen(hub.x, hub.y)
            fill_rgb = resolve_color(hub.color, elapsed_sec)

            # Halo exterior para start_hub y end_hub
            if hub.directive == "start_hub":
                pygame.draw.circle(
                    surface, (46, 204, 113), (sx, sy), node_radius + 7, width=2
                )
            elif hub.directive == "end_hub":
                pygame.draw.circle(
                    surface, fill_rgb, (sx, sy), node_radius + 9, width=3
                )

            # Sombra y cuerpo del Hub
            pygame.draw.circle(surface, (8, 10, 15), (sx + 2, sy + 3), node_radius)
            pygame.draw.circle(surface, fill_rgb, (sx, sy), node_radius)

            # Borde según HubType (NORMAL, PRIORITY, RESTRICTED, BLOCKED)
            if hub.zone == HubType.PRIORITY:
                # Doble anillo dorado para zonas PRIORITY
                pygame.draw.circle(surface, (255, 215, 0), (sx, sy), node_radius + 4, 2)
                pygame.draw.circle(surface, (20, 25, 35), (sx, sy), node_radius, 2)
            elif hub.zone == HubType.RESTRICTED:
                # Borde ámbar/rojo grueso para zonas RESTRICTED (2 turnos)
                pygame.draw.circle(surface, (255, 90, 50), (sx, sy), node_radius + 3, 3)
            elif hub.zone == HubType.BLOCKED:
                pygame.draw.circle(surface, (240, 50, 50), (sx, sy), node_radius + 2, 3)
                d = int(node_radius * 0.7)
                pygame.draw.line(
                    surface, (240, 50, 50), (sx - d, sy - d), (sx + d, sy + d), 3
                )
                pygame.draw.line(
                    surface, (240, 50, 50), (sx - d, sy + d), (sx + d, sy - d), 3
                )
            else:
                pygame.draw.circle(surface, (30, 35, 48), (sx, sy), node_radius, 2)

            if self.show_labels:
                # Nombre del Hub debajo del nodo
                lbl = font_node.render(hub.name, True, self.TEXT_MAIN)
                lbl_rect = lbl.get_rect(center=(sx, sy + node_radius + 13))
                surface.blit(lbl, lbl_rect)

                # Indicador de capacidad máxima y tipo dentro o encima del nodo
                if hub.directive not in ("start_hub", "end_hub"):
                    tag = f"cap:{hub.max_drones}"
                    if hub.zone == HubType.RESTRICTED:
                        tag += " [2T]"
                    elif hub.zone == HubType.PRIORITY:
                        tag += " [★]"
                    cap_surf = font_small.render(tag, True, self.TEXT_DIM)
                    surface.blit(
                        cap_surf, cap_surf.get_rect(center=(sx, sy - node_radius - 11))
                    )

    def _draw_drones(
        self, surface: pygame.Surface, font_drone: pygame.font.Font
    ) -> None:
        drone_radius = int(max(7.0, min(14.0, self.camera.zoom * 0.12)))

        # 1. Calcular posición base de cada dron y agrupar los que coinciden en el mismo sitio
        raw_states: list[tuple[str, float, float, str, bool]] = []
        groups: dict[str, list[str]] = {}

        for drone in self.solver.drones:
            wx, wy, group_key, in_restricted = self._compute_drone_world_state(
                drone.id, self.sim_time
            )
            raw_states.append((drone.id, wx, wy, group_key, in_restricted))
            groups.setdefault(group_key, []).append(drone.id)

        # 2. Dibujar cada dron aplicando un ligero offset circular si comparte nodo/arista
        for drone_id, wx, wy, group_key, in_restricted in raw_states:
            sx, sy = self.camera.world_to_screen(wx, wy)
            members = groups[group_key]
            if len(members) > 1:
                idx = members.index(drone_id)
                angle = (2.0 * math.pi * idx) / len(members)
                spread_px = min(22.0, 6.0 + len(members) * 1.4)
                sx += int(math.cos(angle) * spread_px)
                sy += int(math.sin(angle) * spread_px)

            color = self.drone_colors[drone_id]

            # Si está en mitad de un tránsito RESTRICTED, dibujar pulso ámbar alrededor
            if in_restricted:
                pygame.draw.circle(
                    surface, (255, 140, 40), (sx, sy), drone_radius + 4, width=2
                )

            pygame.draw.circle(surface, (10, 12, 18), (sx, sy), drone_radius + 2)
            pygame.draw.circle(surface, color, (sx, sy), drone_radius)

            id_surf = font_drone.render(drone_id, True, (15, 18, 25))
            surface.blit(id_surf, id_surf.get_rect(center=(sx, sy)))

    def _draw_hud(
        self,
        surface: pygame.Surface,
        font_title: pygame.font.Font,
        font_ui: pygame.font.Font,
        font_small: pygame.font.Font,
    ) -> None:
        # Barra superior
        top_rect = pygame.Rect(0, 0, self.width, 54)
        pygame.draw.rect(surface, self.PANEL_BG, top_rect)
        pygame.draw.line(
            surface, self.PANEL_BORDER, (0, 54), (self.width, 54), width=1
        )

        current_turn_display = int(math.ceil(self.sim_time - 1e-6))
        if self.sim_time <= 1e-5:
            current_turn_display = 0

        arrived_count = sum(
            1
            for d in self.solver.drones
            if self.arrival_turns.get(d.id, 0) > 0
            and self.sim_time >= float(self.arrival_turns[d.id]) - 1e-5
        )

        status_txt = "PLAYING" if self.playing else "PAUSED"
        status_col = (46, 204, 113) if self.playing else (241, 196, 15)

        title_surf = font_title.render("FLY-IN // SIMULATOR", True, self.TEXT_MAIN)
        surface.blit(title_surf, (20, 15))

        status_surf = font_ui.render(f"[{status_txt}]", True, status_col)
        surface.blit(status_surf, (255, 17))

        metrics = (
            f"Turno: {current_turn_display} / {self.solver.total_turns}   |   "
            f"En Meta: {arrived_count} / {self.graph.n_drones}   |   "
            f"Velocidad: {self.turns_per_sec:.2f} turnos/s"
        )
        metrics_surf = font_ui.render(metrics, True, self.TEXT_MAIN)
        surface.blit(metrics_surf, (380, 17))

        # Barra de progreso temporal e instrucciones en la parte inferior
        bottom_rect = pygame.Rect(0, self.height - 64, self.width, 64)
        pygame.draw.rect(surface, self.PANEL_BG, bottom_rect)
        pygame.draw.line(
            surface,
            self.PANEL_BORDER,
            (0, self.height - 64),
            (self.width, self.height - 64),
            width=1,
        )

        # Barra de progreso de turnos
        bar_x, bar_y, bar_w, bar_h = 24, self.height - 48, self.width - 48, 12
        pygame.draw.rect(
            surface, (38, 45, 62), (bar_x, bar_y, bar_w, bar_h), border_radius=6
        )
        if self.solver.total_turns > 0:
            pct = max(0.0, min(1.0, self.sim_time / float(self.solver.total_turns)))
            fill_w = int(bar_w * pct)
            pygame.draw.rect(
                surface, (52, 152, 219), (bar_x, bar_y, fill_w, bar_h), border_radius=6
            )

        controls_txt = (
            "Controles: [ESPACIO] Play/Pausa  |  [←/→] Paso a Paso (Turno)  |  "
            "[↑/↓] Velocidad  |  [R] Reiniciar  |  [F] Centrar Cámara  |  "
            "[L] Etiquetas  |  [Ratón + Rueda] Pan & Zoom  |  [ESC] Salir"
        )
        ctrl_surf = font_small.render(controls_txt, True, self.TEXT_DIM)
        surface.blit(ctrl_surf, (24, self.height - 26))

    def run(self) -> None:
        """Inicia el bucle principal de renderizado y eventos de Pygame."""
        pygame.init()
        pygame.display.set_caption(
            f"Fly-in Visualizer — {self.graph.n_drones} Drones | {self.solver.total_turns} Turnos"
        )
        screen = pygame.display.set_mode(
            (self.width, self.height), pygame.RESIZABLE
        )
        clock = pygame.time.Clock()

        font_title = pygame.font.SysFont("monospace", 18, bold=True)
        font_ui = pygame.font.SysFont("monospace", 15, bold=True)
        font_node = pygame.font.SysFont("monospace", 13, bold=True)
        font_small = pygame.font.SysFont("monospace", 12)
        font_drone = pygame.font.SysFont("monospace", 10, bold=True)

        dragging = False
        last_mouse = (0, 0)
        elapsed_sec = 0.0

        running = True
        while running:
            dt = clock.tick(60) / 1000.0
            elapsed_sec += dt

            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    running = False

                elif event.type == pygame.VIDEORESIZE:
                    self.width, self.height = event.w, event.h
                    self.camera.width, self.camera.height = event.w, event.h
                    screen = pygame.display.set_mode(
                        (self.width, self.height), pygame.RESIZABLE
                    )

                elif event.type == pygame.KEYDOWN:
                    if event.key == pygame.K_ESCAPE:
                        running = False
                    elif event.key == pygame.K_SPACE:
                        if self.sim_time >= float(self.solver.total_turns):
                            self.sim_time = 0.0
                        self.playing = not self.playing
                    elif event.key == pygame.K_r:
                        self.sim_time = 0.0
                        self.playing = True
                    elif event.key == pygame.K_f:
                        self.camera.fit_graph(self.graph)
                    elif event.key == pygame.K_l:
                        self.show_labels = not self.show_labels
                    elif event.key == pygame.K_RIGHT:
                        self.playing = False
                        self.sim_time = min(
                            float(self.solver.total_turns),
                            math.floor(self.sim_time + 1e-5) + 1.0,
                        )
                    elif event.key == pygame.K_LEFT:
                        self.playing = False
                        self.sim_time = max(
                            0.0, math.ceil(self.sim_time - 1e-5) - 1.0
                        )
                    elif event.key == pygame.K_UP:
                        self.turns_per_sec = min(10.0, self.turns_per_sec * 1.25)
                    elif event.key == pygame.K_DOWN:
                        self.turns_per_sec = max(0.2, self.turns_per_sec / 1.25)

                elif event.type == pygame.MOUSEBUTTONDOWN:
                    if event.button == 1:
                        # Si hace clic en la barra de progreso inferior, salta a ese turno
                        if event.pos[1] >= self.height - 64:
                            bar_x, bar_w = 24, self.width - 48
                            pct = (event.pos[0] - bar_x) / max(1, bar_w)
                            pct = max(0.0, min(1.0, pct))
                            self.sim_time = pct * float(self.solver.total_turns)
                            self.playing = False
                        else:
                            dragging = True
                            last_mouse = event.pos
                    elif event.button == 4:  # Rueda arriba
                        self.camera.zoom_at(event.pos, 1.12)
                    elif event.button == 5:  # Rueda abajo
                        self.camera.zoom_at(event.pos, 1.0 / 1.12)

                elif event.type == pygame.MOUSEBUTTONUP:
                    if event.button == 1:
                        dragging = False

                elif event.type == pygame.MOUSEMOTION:
                    if dragging:
                        dx = event.pos[0] - last_mouse[0]
                        dy = event.pos[1] - last_mouse[1]
                        self.camera.offset_x += dx
                        self.camera.offset_y += dy
                        last_mouse = event.pos

            # Avance del reloj de simulación
            if self.playing and self.solver.total_turns > 0:
                self.sim_time += dt * self.turns_per_sec
                if self.sim_time >= float(self.solver.total_turns):
                    self.sim_time = float(self.solver.total_turns)
                    self.playing = False

            # Renderizado de capas
            screen.fill(self.BG_COLOR)
            self._draw_grid(screen)
            self._draw_connections(screen, font_small)
            self._draw_hubs(screen, font_node, font_small, elapsed_sec)
            self._draw_drones(screen, font_drone)
            self._draw_hud(screen, font_title, font_ui, font_small)

            pygame.display.flip()

        pygame.quit()