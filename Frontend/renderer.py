"""Minimalist single-file Pygame renderer for Fly-In."""
from __future__ import annotations

import math
import pygame

from Backend.Solver.models import ScheduledStep
from Backend.Solver.solver import Solver
from Backend.Zones.graph import Graph

COLORS: dict[str, tuple[int, int, int]] = {
    "white": (235, 240, 245),
    "black": (60, 70, 90),
    "red": (235, 85, 95),
    "darkred": (180, 50, 65),
    "crimson": (220, 60, 90),
    "maroon": (150, 55, 85),
    "green": (80, 215, 150),
    "blue": (85, 170, 245),
    "yellow": (245, 215, 95),
    "gold": (240, 190, 70),
    "orange": (245, 145, 80),
    "purple": (175, 115, 240),
    "violet": (205, 135, 245),
    "brown": (185, 130, 95),
    "cyan": (90, 225, 235),
    "gray": (150, 165, 185),
    "rainbow": (255, 120, 220),
}


class Renderer:
    """Minimalist turn-based visualizer that scales dynamically with the screen."""

    def __init__(self, graph: Graph, solver: Solver) -> None:
        self.graph = graph
        self.solver = solver
        self.turn = 0
        self.fullscreen = False
        self.show_names = True
        self.win_size = (1200, 800)
        self.steps_by_drone: dict[str, dict[int, ScheduledStep]] = {}
        self.last_turn: dict[str, int] = {}
        self.max_printed_turn = 0
        self.turn_moves: dict[int, list[str]] = {}
        for drone_id, steps in solver.schedules.items():
            for step in steps:
                if not step.is_wait:
                    dst = (f"{step.from_zone}-{step.to_zone}"
                           if step.is_restricted_transit else step.to_zone)
                    self.turn_moves.setdefault(step.turn, []).append(
                        f"{drone_id}-{dst}"
                        )
        for drone in solver.drones:
            sched = solver.schedules.get(drone.id, [])
            self.steps_by_drone[drone.id] = {s.turn: s for s in sched}
            self.last_turn[drone.id] = sched[-1].turn if sched else 0

    def _to_screen(
        self, x: float, y: float, width: int, height: int
    ) -> tuple[int, int]:
        """Map world coordinates (x, y) to screen pixels with aspect-ratio scaling."""
        if not self.graph.nodes_dict:
            return width // 2, height // 2

        xs = [h.x for h in self.graph.nodes_dict.values()]
        ys = [h.y for h in self.graph.nodes_dict.values()]
        min_x, max_x = float(min(xs)), float(max(xs))
        min_y, max_y = float(min(ys)), float(max(ys))

        span_x = max(1.0, max_x - min_x)
        span_y = max(1.0, max_y - min_y)

        pad_x = max(70.0, width * 0.12)
        pad_y = max(70.0, height * 0.12)
        usable_w = max(100.0, width - 2.0 * pad_x)
        usable_h = max(100.0, height - 2.0 * pad_y)

        scale = min(usable_w / span_x, usable_h / span_y)
        cx, cy = width * 0.5, height * 0.5
        mid_x, mid_y = (min_x + max_x) * 0.5, (min_y + max_y) * 0.5

        sx = int(round(cx + (x - mid_x) * scale))
        sy = int(round(cy - (y - mid_y) * scale))
        return sx, sy

    def _drone_world_pos(self, drone_id: str) -> tuple[float, float]:
        """Return world coordinates (wx, wy) of a drone on the current turn."""
        start = self.graph.start
        end = self.graph.end
        if start is None or end is None:
            return 0.0, 0.0

        if self.turn <= 0:
            return float(start.x), float(start.y)

        end_t = self.last_turn.get(drone_id, 0)
        if end_t == 0 or self.turn >= end_t:
            return float(end.x), float(end.y)

        step = self.steps_by_drone.get(drone_id, {}).get(self.turn)
        if step is None:
            return float(start.x), float(start.y)

        if step.is_restricted_transit:
            u = self.graph.nodes_dict[step.from_zone]
            v = self.graph.nodes_dict[step.to_zone]
            return (u.x + v.x) * 0.5, (u.y + v.y) * 0.5

        hub = self.graph.nodes_dict[step.to_zone]
        return float(hub.x), float(hub.y)

    @staticmethod
    def _place_label(
        pos: tuple[int, int],
        size: tuple[int, int],
        radius: int,
        occupied: list[pygame.Rect],
    ) -> pygame.Rect:
        """Find a non-overlapping bounding box for a node label."""
        px, py = pos
        tw, th = size
        bw, bh = tw + 8, th + 4

        dirs = [
            (0.0, 1.0),
            (0.0, -1.0),
            (1.0, 0.0),
            (-1.0, 0.0),
            (0.85, 0.85),
            (-0.85, 0.85),
            (0.85, -0.85),
            (-0.85, -0.85),
        ]

        best_rect = pygame.Rect(0, 0, bw, bh)
        best_cost = float("inf")

        for ring in (1.0, 1.85, 2.7):
            dist_x = (radius + bw * 0.5 + 5.0) * ring
            dist_y = (radius + bh * 0.5 + 5.0) * ring
            for dx, dy in dirs:
                cx = int(round(px + dx * dist_x))
                cy = int(round(py + dy * dist_y))
                cand = pygame.Rect(cx - bw // 2, cy - bh // 2, bw, bh)

                overlap = 0
                for occ in occupied:
                    if cand.colliderect(occ):
                        ix = min(cand.right, occ.right) - max(cand.left, occ.left)
                        iy = min(cand.bottom, occ.bottom) - max(cand.top, occ.top)
                        overlap += ix * iy

                if overlap == 0:
                    return cand

                cost = overlap + ring * 25.0
                if cost < best_cost:
                    best_cost = cost
                    best_rect = cand

        return best_rect

    def draw_edges(self, screen: pygame.Surface) -> None:
        """Draw graph connections."""
        w, h = screen.get_size()
        for link in self.graph.link_dict.values():
            u = self.graph.nodes_dict[link.from_zone]
            v = self.graph.nodes_dict[link.to_zone]
            p1 = self._to_screen(u.x, u.y, w, h)
            p2 = self._to_screen(v.x, v.y, w, h)
            pygame.draw.line(screen, (85, 95, 120), p1, p2, 2)

    def draw_nodes(
        self, screen: pygame.Surface, font: pygame.font.Font
    ) -> None:
        """Draw hubs and optionally their non-overlapping labels."""
        w, h = screen.get_size()
        radius = max(8, int(min(w, h) * 0.018))

        occupied: list[pygame.Rect] = []
        node_data: list[tuple[tuple[int, int], tuple[int, int, int], str]] = []

        for hub in self.graph.nodes_dict.values():
            pos = self._to_screen(hub.x, hub.y, w, h)
            color = COLORS.get(hub.color.strip().lower(), COLORS["white"])
            pygame.draw.circle(screen, color, pos, radius)
            pygame.draw.circle(screen, (20, 24, 34), pos, radius, 2)

            if self.show_names:
                occupied.append(
                    pygame.Rect(
                        pos[0] - radius - 2,
                        pos[1] - radius - 2,
                        (radius + 2) * 2,
                        (radius + 2) * 2,
                    )
                )
                node_data.append((pos, color, hub.name))

        if not self.show_names:
            return

        for pos, color, name in node_data:
            label = font.render(name, True, (235, 240, 250))
            box = self._place_label(pos, label.get_size(), radius, occupied)
            occupied.append(box)

            if math.hypot(box.centerx - pos[0], box.centery - pos[1]) > radius * 2.4:
                pygame.draw.line(screen, (95, 105, 130), pos, box.center, 1)

            pygame.draw.rect(screen, (18, 22, 32), box, border_radius=4)
            pygame.draw.rect(screen, color, box, width=1, border_radius=4)
            screen.blit(label, label.get_rect(center=box.center))

    def draw_drones(
        self, screen: pygame.Surface, font: pygame.font.Font
    ) -> None:
        """Draw drones with lowercase labels (d1, d2, d3...)."""
        w, h = screen.get_size()
        radius = max(5, int(min(w, h) * 0.010))

        groups: dict[tuple[int, int], list[str]] = {}
        for drone in self.solver.drones:
            wx, wy = self._drone_world_pos(drone.id)
            spos = self._to_screen(wx, wy, w, h)
            groups.setdefault(spos, []).append(drone.id)

        for (bx, by), drone_ids in groups.items():
            count = len(drone_ids)
            spread = max(12, int(radius * 2.2)) if count > 1 else 0
            for idx, did in enumerate(drone_ids):
                if count > 1:
                    angle = (2.0 * math.pi * idx) / count
                    dx = int(round(bx + math.cos(angle) * spread))
                    dy = int(round(by + math.sin(angle) * spread))
                else:
                    dx, dy = bx, by

                pygame.draw.circle(screen, (0, 230, 255), (dx, dy), radius)
                pygame.draw.circle(screen, (15, 20, 30), (dx, dy), radius, 1)

                label = font.render(did.lower(), True, (255, 240, 150))
                rect = label.get_rect(center=(dx, dy - radius - 9))
                screen.blit(label, rect)

    def draw_turn(
        self, screen: pygame.Surface, font: pygame.font.Font
    ) -> None:
        """Render the current turn counter on screen."""
        text = f"Turn: {self.turn} / {self.solver.total_turns}"
        surf = font.render(text, True, (240, 245, 255))
        screen.blit(surf, (20, 20))

    def run(self) -> None:
        """Run the main event and rendering loop."""
        pygame.init()
        pygame.display.set_caption("Fly-In")
        screen = pygame.display.set_mode(self.win_size, pygame.RESIZABLE)
        clock = pygame.time.Clock()

        running = True
        while running:
            clock.tick(60)
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    running = False
                elif event.type == pygame.VIDEORESIZE and not self.fullscreen:
                    self.win_size = (event.w, event.h)
                    screen = pygame.display.set_mode(
                        self.win_size, pygame.RESIZABLE
                    )
                elif event.type == pygame.KEYDOWN:
                    if event.key == pygame.K_ESCAPE:
                        running = False
                    elif event.key == pygame.K_RIGHT:
                        self.turn = min(self.solver.total_turns, self.turn + 1)
                        if self.turn > self.max_printed_turn:
                                self.max_printed_turn = self.turn
                                if self.turn in self.turn_moves:
                                    moves_str = " ".join(self.turn_moves[self.turn])
                                    print(f"Turn {self.turn}: {moves_str}")
                            #-------------------
                                    print(self.solver.test(self.turn))
                        else:
                            print("All nodes have reached the goal...")
                    elif event.key == pygame.K_LEFT:
                        self.turn = max(0, self.turn - 1)
                    elif event.key == pygame.K_n:
                        self.show_names = not self.show_names
                    elif event.key == pygame.K_f:
                        self.fullscreen = not self.fullscreen
                        if self.fullscreen:
                            screen = pygame.display.set_mode(
                                (0, 0), pygame.FULLSCREEN
                            )
                        else:
                            screen = pygame.display.set_mode(
                                self.win_size, pygame.RESIZABLE
                            )

            w, h = screen.get_size()
            font_size = max(11, int(min(w, h) * 0.016))
            font = pygame.font.SysFont("monospace", font_size, bold=True)

            screen.fill((18, 22, 32))
            self.draw_edges(screen)
            self.draw_nodes(screen, font)
            self.draw_drones(screen, font)
            self.draw_turn(screen, font)
            pygame.display.flip()

        pygame.quit()
