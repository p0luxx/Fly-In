"""Shared rendering utilities, visual state, camera, and label layout."""
from __future__ import annotations

import colorsys
import math
from dataclasses import dataclass

import pygame

from Backend.Zones.graph import Graph


DREAM_PALETTE: dict[str, tuple[int, int, int]] = {
    "white": (242, 246, 255),
    "black": (78, 88, 120),
    "red": (255, 102, 132),
    "darkred": (210, 72, 108),
    "crimson": (255, 82, 122),
    "maroon": (188, 82, 132),
    "green": (98, 238, 188),
    "blue": (98, 188, 255),
    "yellow": (255, 226, 126),
    "gold": (255, 208, 96),
    "orange": (255, 162, 108),
    "purple": (192, 132, 255),
    "violet": (222, 152, 255),
    "brown": (205, 150, 115),
    "cyan": (105, 242, 248),
    "gray": (162, 178, 208),
}


def clamp(val: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, val))


def smoothstep(t: float) -> float:
    t = clamp(t, 0.0, 1.0)
    return t * t * (3.0 - 2.0 * t)


def ease_in_out_sine(t: float) -> float:
    t = clamp(t, 0.0, 1.0)
    return -0.5 * (math.cos(math.pi * t) - 1.0)


def exp_decay(current: float, target: float, speed: float, dt: float) -> float:
    """Exponential interpolation independent of frame rate (no flicker)."""
    factor = 1.0 - math.exp(-speed * dt)
    return current + (target - current) * factor


def resolve_color(color_name: str, elapsed: float = 0.0) -> tuple[int, int, int]:
    clean = color_name.strip().lower()
    if clean == "rainbow":
        r, g, b = colorsys.hsv_to_rgb((elapsed * 0.14) % 1.0, 0.52, 1.0)
        return int(r * 255), int(g * 255), int(b * 255)
    return DREAM_PALETTE.get(clean, DREAM_PALETTE["white"])


def golden_angle_drone_color(index: int) -> tuple[int, int, int]:
    """Distribute drone colors using the golden ratio."""
    hue = (0.52 + index * 0.618033988749895) % 1.0
    r, g, b = colorsys.hsv_to_rgb(hue, 0.48, 1.0)
    return int(r * 255), int(g * 255), int(b * 255)


class GlowCache:
    """Pre-render and cache soft radial glows to maintain 60 FPS."""

    def __init__(self) -> None:
        self._cache: dict[tuple[int, tuple[int, int, int], int], pygame.Surface] = {}

    def get(
        self, radius: int, color: tuple[int, int, int], peak_alpha: int = 80
    ) -> pygame.Surface:
        r_quant = max(4, (radius // 2) * 2)
        c_quant = (color[0] // 4 * 4, color[1] // 4 * 4, color[2] // 4 * 4)
        key = (r_quant, c_quant, peak_alpha)

        if key not in self._cache:
            if len(self._cache) > 512:
                self._cache.clear()
            size = r_quant * 2
            surf = pygame.Surface((size, size), pygame.SRCALPHA)
            layers = 8
            for i in range(layers, 0, -1):
                frac = i / layers
                sub_r = max(1, int(r_quant * frac))
                # Smooth Gaussian falloff toward the edge.
                falloff = math.exp(-3.2 * (frac * frac))
                alpha = int(clamp(peak_alpha * falloff, 0, 255))
                if alpha > 0:
                    pygame.draw.circle(
                        surf, (*c_quant, alpha), (r_quant, r_quant), sub_r
                    )
            self._cache[key] = surf
        return self._cache[key]

    def draw(
        self,
        target: pygame.Surface,
        center: tuple[int, int],
        radius: int,
        color: tuple[int, int, int],
        peak_alpha: int = 80,
    ) -> None:
        if radius <= 2:
            return
        sprite = self.get(radius, color, peak_alpha)
        half = sprite.get_width() // 2
        target.blit(
            sprite,
            (center[0] - half, center[1] - half),
            special_flags=pygame.BLEND_PREMULTIPLIED if False else 0,
        )


@dataclass
class Shockwave:
    """Expanding harmonic wave emitted when a drone reaches the goal."""

    x: float
    y: float
    color: tuple[int, int, int]
    progress: float = 0.0
    speed: float = 1.35


@dataclass
class SmoothLabelState:
    """Persistent label state for smooth movement."""

    rest_dx: float
    rest_dy: float
    cur_dx: float
    cur_dy: float
    width: int = 60
    height: int = 20
    alpha: float = 1.0


class OrganicLabelEngine:
    """
    Calculate optimal label positions using initial topological analysis, then
    apply continuously damped repulsion forces at runtime (no discrete jumps).
    """

    def __init__(self, graph: Graph) -> None:
        self.graph = graph
        self.node_labels: dict[str, SmoothLabelState] = {}
        self.drone_labels: dict[str, SmoothLabelState] = {}
        self._init_topological_node_offsets()

    def _init_topological_node_offsets(self) -> None:
        """
        For each hub, analyze the angles of its connected edges and place its
        label along the bisector of the largest open angle.
        """
        for name, hub in self.graph.nodes_dict.items():
            neighbors = self.graph.get_neighbors(name)
            edge_angles: list[float] = []

            for link in neighbors:
                other_name = link.get_destination(name)
                other = self.graph.nodes_dict.get(other_name)
                if other is not None:
                    # The screen's Y axis is inverted (-dy).
                    dx = float(other.x - hub.x)
                    dy = float(-(other.y - hub.y))
                    if abs(dx) > 1e-4 or abs(dy) > 1e-4:
                        ang = math.atan2(dy, dx) % (2.0 * math.pi)
                        edge_angles.append(ang)

            if not edge_angles:
                best_angle = math.pi * 0.5  # Below by default.
            elif len(edge_angles) == 1:
                best_angle = (edge_angles[0] + math.pi) % (2.0 * math.pi)
            else:
                edge_angles.sort()
                best_gap = -1.0
                best_angle = math.pi * 0.5
                n = len(edge_angles)
                for i in range(n):
                    a1 = edge_angles[i]
                    a2 = (
                        edge_angles[(i + 1) % n]
                        if i + 1 < n
                        else edge_angles[0] + 2.0 * math.pi
                    )
                    gap = a2 - a1
                    mid = (a1 + a2) * 0.5
                    # Slight aesthetic preference for placing labels above or below.
                    vertical_bonus = 0.15 * abs(math.sin(mid))
                    if gap + vertical_bonus > best_gap:
                        best_gap = gap + vertical_bonus
                        best_angle = mid % (2.0 * math.pi)

            dist = 28.0
            rx = math.cos(best_angle) * dist * 1.15
            ry = math.sin(best_angle) * dist
            self.node_labels[name] = SmoothLabelState(
                rest_dx=rx, rest_dy=ry, cur_dx=rx, cur_dy=ry
            )

    def update_node_labels(
        self,
        screen_positions: dict[str, tuple[int, int]],
        node_radius: int,
        dt: float,
    ) -> None:
        """
        Smoothly relax node labels relative to one another using continuous
        forces, without allowing abrupt jumps from one side to the other.
        """
        names = list(self.node_labels.keys())
        base_scale = max(0.85, min(1.45, node_radius / 14.0))

        # 1. Calculate smooth repulsion forces between nearby node labels.
        forces: dict[str, list[float]] = {n: [0.0, 0.0] for n in names}

        for i in range(len(names)):
            n1 = names[i]
            st1 = self.node_labels[n1]
            ax1, ay1 = screen_positions[n1]
            cx1 = ax1 + st1.cur_dx
            cy1 = ay1 + st1.cur_dy

            # Smoothly repel nearby nodes and their labels.
            for j in range(i + 1, len(names)):
                n2 = names[j]
                st2 = self.node_labels[n2]
                ax2, ay2 = screen_positions[n2]

                # Ignore nodes that are far apart on screen.
                if abs(ax1 - ax2) > 220 or abs(ay1 - ay2) > 140:
                    continue

                cx2 = ax2 + st2.cur_dx
                cy2 = ay2 + st2.cur_dy

                # Overlap between the two text boxes.
                min_sep_x = (st1.width + st2.width) * 0.5 + 8.0
                min_sep_y = (st1.height + st2.height) * 0.5 + 6.0
                dx = cx1 - cx2
                dy = cy1 - cy2

                if abs(dx) < min_sep_x and abs(dy) < min_sep_y:
                    pen_x = (min_sep_x - abs(dx)) / min_sep_x
                    pen_y = (min_sep_y - abs(dy)) / min_sep_y
                    strength = pen_x * pen_y * 28.0
                    dir_x = 1.0 if dx >= 0 else -1.0
                    dir_y = 1.0 if dy >= 0 else -1.0
                    forces[n1][0] += dir_x * strength * 0.45
                    forces[n1][1] += dir_y * strength * 0.85
                    forces[n2][0] -= dir_x * strength * 0.45
                    forces[n2][1] -= dir_y * strength * 0.85

        # 2. Integrate with exponential damping toward (rest + force).
        for name in names:
            st = self.node_labels[name]
            fx, fy = forces[name]
            # Limit displacement so labels never drift too far from their hubs.
            fx = clamp(fx, -36.0, 36.0)
            fy = clamp(fy, -28.0, 28.0)

            target_dx = st.rest_dx * base_scale + fx
            target_dy = st.rest_dy * base_scale + fy

            st.cur_dx = exp_decay(st.cur_dx, target_dx, speed=7.5, dt=dt)
            st.cur_dy = exp_decay(st.cur_dy, target_dy, speed=7.5, dt=dt)

    def update_drone_labels(
        self,
        active_drones: list[tuple[str, float, float]],
        node_screen_pos: dict[str, tuple[int, int]],
        drone_radius: int,
        dt: float,
    ) -> None:
        """
        Update drone label positions organically so labels separate smoothly
        when drones travel together.
        """
        rest_y = -(drone_radius + 15.0)
        n = len(active_drones)

        for idx, (did, _, _) in enumerate(active_drones):
            if did not in self.drone_labels:
                # Create a small initial fan based on the drone index.
                fan_x = ((idx % 3) - 1) * 4.0
                self.drone_labels[did] = SmoothLabelState(
                    rest_dx=fan_x,
                    rest_dy=rest_y,
                    cur_dx=fan_x,
                    cur_dy=rest_y,
                )
            else:
                self.drone_labels[did].rest_dy = rest_y

        forces: dict[str, list[float]] = {
            did: [0.0, 0.0] for did, _, _ in active_drones
        }

        # Smoothly repel labels of nearby active drones.
        for i in range(n):
            d1, x1, y1 = active_drones[i]
            st1 = self.drone_labels[d1]
            lx1, ly1 = x1 + st1.cur_dx, y1 + st1.cur_dy

            for j in range(i + 1, n):
                d2, x2, y2 = active_drones[j]
                if abs(x1 - x2) > 130 or abs(y1 - y2) > 90:
                    continue
                st2 = self.drone_labels[d2]
                lx2, ly2 = x2 + st2.cur_dx, y2 + st2.cur_dy

                sep_x = (st1.width + st2.width) * 0.5 + 6.0
                sep_y = (st1.height + st2.height) * 0.5 + 5.0
                dx = lx1 - lx2
                dy = ly1 - ly2

                if abs(dx) < sep_x and abs(dy) < sep_y:
                    # Break exact-position ties deterministically using the ID.
                    if abs(dx) < 0.5 and abs(dy) < 0.5:
                        angle = (i - j) * 1.1
                        dx, dy = math.cos(angle), math.sin(angle)
                    overlap_x = (sep_x - abs(dx)) / sep_x
                    overlap_y = (sep_y - abs(dy)) / sep_y
                    push = overlap_x * overlap_y * 24.0
                    sx = 1.0 if dx >= 0 else -1.0
                    sy = 1.0 if dy >= 0 else -1.0
                    forces[d1][0] += sx * push * 0.7
                    forces[d1][1] += sy * push * 0.7
                    forces[d2][0] -= sx * push * 0.7
                    forces[d2][1] -= sy * push * 0.7

            # Smoothly repel nearby visible node labels.
            for hname, (hx, hy) in node_screen_pos.items():
                if abs(lx1 - hx) > 140 or abs(ly1 - hy) > 90:
                    continue
                nst = self.node_labels.get(hname)
                if nst is None:
                    continue
                nlx, nly = hx + nst.cur_dx, hy + nst.cur_dy
                sep_x = (st1.width + nst.width) * 0.5 + 6.0
                sep_y = (st1.height + nst.height) * 0.5 + 5.0
                dx = lx1 - nlx
                dy = ly1 - nly
                if abs(dx) < sep_x and abs(dy) < sep_y:
                    push = ((sep_y - abs(dy)) / sep_y) * 18.0
                    sy = -1.0 if dy <= 0 else 1.0
                    forces[d1][1] += sy * push

        for did, _, _ in active_drones:
            st = self.drone_labels[did]
            fx = clamp(forces[did][0], -34.0, 34.0)
            fy = clamp(forces[did][1], -30.0, 22.0)
            target_dx = st.rest_dx + fx
            target_dy = st.rest_dy + fy
            st.cur_dx = exp_decay(st.cur_dx, target_dx, speed=9.0, dt=dt)
            st.cur_dy = exp_decay(st.cur_dy, target_dy, speed=9.0, dt=dt)


class SmoothCamera2D:
    """2D camera with exponential interpolation for smooth zooming and panning."""

    def __init__(self, width: int, height: int) -> None:
        self.width = width
        self.height = height
        self.offset_x = 0.0
        self.offset_y = 0.0
        self.zoom = 90.0

        self.target_offset_x = 0.0
        self.target_offset_y = 0.0
        self.target_zoom = 90.0

    def fit_graph(self, graph: Graph, instant: bool = False) -> None:
        if not graph.nodes_dict:
            return
        xs = [n.x for n in graph.nodes_dict.values()]
        ys = [n.y for n in graph.nodes_dict.values()]
        min_x, max_x = min(xs), max(xs)
        min_y, max_y = min(ys), max(ys)

        span_x = max(1.0, float(max_x - min_x))
        span_y = max(1.0, float(max_y - min_y))

        margin_x = 160
        margin_y = 145
        usable_w = max(240, self.width - 2 * margin_x)
        usable_h = max(220, self.height - 2 * margin_y)

        z = min(usable_w / span_x, usable_h / span_y)
        z = clamp(z, 18.0, 175.0)

        cx = (min_x + max_x) * 0.5
        cy = (min_y + max_y) * 0.5

        self.target_zoom = z
        self.target_offset_x = (self.width * 0.5) - cx * z
        self.target_offset_y = (self.height * 0.5) + cy * z

        if instant:
            self.zoom = self.target_zoom
            self.offset_x = self.target_offset_x
            self.offset_y = self.target_offset_y

    def update(self, dt: float) -> None:
        self.zoom = exp_decay(self.zoom, self.target_zoom, 12.0, dt)
        self.offset_x = exp_decay(self.offset_x, self.target_offset_x, 12.0, dt)
        self.offset_y = exp_decay(self.offset_y, self.target_offset_y, 12.0, dt)

    def pan(self, dx: float, dy: float) -> None:
        self.target_offset_x += dx
        self.target_offset_y += dy
        self.offset_x += dx
        self.offset_y += dy

    def zoom_at(self, mouse_pos: tuple[int, int], factor: float) -> None:
        mx, my = mouse_pos
        wx = (mx - self.target_offset_x) / self.target_zoom
        wy = (self.target_offset_y - my) / self.target_zoom

        new_z = clamp(self.target_zoom * factor, 10.0, 380.0)
        self.target_zoom = new_z
        self.target_offset_x = mx - wx * new_z
        self.target_offset_y = my + wy * new_z

    def to_screen(self, x: float, y: float) -> tuple[int, int]:
        return int(round(self.offset_x + x * self.zoom)), int(
            round(self.offset_y - y * self.zoom)
        )

    def to_screen_float(self, x: float, y: float) -> tuple[float, float]:
        return self.offset_x + x * self.zoom, self.offset_y - y * self.zoom


@dataclass
class DroneRenderState:
    drone_id: str
    wx: float
    wy: float
    sx: float
    sy: float
    heading_rad: float
    group_key: str
    status_text: str
    is_active: bool
    in_restricted: bool
