"""Pygame drawing routines for the Fly-In visualization."""
from __future__ import annotations

import math

import pygame

from Backend.Zones.hub_type import HubType
from Frontend.visualizer_support import (
    DroneRenderState,
    clamp,
    resolve_color,
)
from Frontend.visualizer_context import _VisualizerContext

__all__ = ["_VisualizerRendering"]


class _VisualizerRendering(_VisualizerContext):
    """Visual presentation layer mixed into :class:`FlyInVisualizer`."""

    def _build_background_surface(self) -> pygame.Surface:
        """Pre-render the nighttime atmospheric gradient and soft nebulae."""
        surf = pygame.Surface((self.width, self.height))
        for y in range(self.height):
            t = y / max(1, self.height - 1)
            r = int(self.BG_TOP[0] + (self.BG_BOTTOM[0] - self.BG_TOP[0]) * t)
            g = int(self.BG_TOP[1] + (self.BG_BOTTOM[1] - self.BG_TOP[1]) * t)
            b = int(self.BG_TOP[2] + (self.BG_BOTTOM[2] - self.BG_TOP[2]) * t)
            pygame.draw.line(surf, (r, g, b), (0, y), (self.width, y))

        # Subtle atmospheric auroras in the background.
        nebula = pygame.Surface((self.width, self.height), pygame.SRCALPHA)
        self.glow.draw(
            nebula,
            (int(self.width * 0.25), int(self.height * 0.3)),
            int(min(self.width, self.height) * 0.42),
            (45, 85, 165),
            peak_alpha=24,
        )
        self.glow.draw(
            nebula,
            (int(self.width * 0.75), int(self.height * 0.68)),
            int(min(self.width, self.height) * 0.45),
            (95, 50, 145),
            peak_alpha=20,
        )
        surf.blit(nebula, (0, 0))
        return surf

    def _draw_atmosphere(self, surface: pygame.Surface, elapsed: float) -> None:
        if self._bg_surface is None or self._bg_surface.get_size() != (
            self.width,
            self.height,
        ):
            self._bg_surface = self._build_background_surface()
        surface.blit(self._bg_surface, (0, 0))

        # Subtle geometric grid when zoomed in close enough.
        if self.camera.zoom >= 28.0:
            step_px = max(36, int(round(self.camera.zoom * 2.0)))
            ox = int(self.camera.offset_x) % step_px
            oy = int(self.camera.offset_y) % step_px
            grid_col = (20, 26, 48)
            for x in range(ox, self.width, step_px):
                pygame.draw.line(surface, grid_col, (x, 0), (x, self.height), 1)
            for y in range(oy, self.height, step_px):
                pygame.draw.line(surface, grid_col, (0, y), (self.width, y), 1)

        # Starfield with parallax as the camera moves.
        for bx, by, rad, p_factor, phase in self.stars:
            sx = int(
                (
                    bx
                    + self.camera.offset_x * p_factor
                    + elapsed * 3.5 * p_factor
                )
                % self.width
            )
            sy = int(
                (
                    by
                    + self.camera.offset_y * p_factor
                    - elapsed * 5.0 * p_factor
                )
                % self.height
            )
            twinkle = 0.5 + 0.5 * math.sin(elapsed * 2.2 + phase)
            r_int = max(1, int(rad * (0.75 + 0.35 * twinkle)))
            c_val = int(155 + 90 * twinkle)
            pygame.draw.circle(surface, (c_val - 20, c_val, 255), (sx, sy), r_int)

    def _draw_connections(self, surface: pygame.Surface, elapsed: float) -> None:
        """
        Draw connections as energy conduits. If drones are crossing on the
        current turn, emit glowing photons moving in the direction of travel.
        """
        active_turn = min(self.solver.total_turns, int(math.floor(self.sim_time)) + 1)
        if self.sim_time <= 0.0 or self.sim_time >= float(self.solver.total_turns):
            active_turn = 0

        # Collect the directed edges active on the current turn.
        active_Transits: dict[str, tuple[str, str, int, bool]] = {}
        if active_turn > 0:
            for d in self.solver.drones:
                st = self.step_map.get(d.id, {}).get(active_turn)
                if st is not None and not st.is_wait:
                    cid = self.solver._canonical_link_id(st.connection)
                    prev_count = active_Transits.get(cid, ("", "", 0, False))[2]
                    active_Transits[cid] = (
                        st.from_zone,
                        st.to_zone,
                        prev_count + 1,
                        st.is_restricted_transit,
                    )

        # Edges along the route of the selected drone or the one under the cursor.
        highlighted_drone_id = self.selected_drone or self.hovered_drone
        highlighted_edges: set[str] = set()
        if highlighted_drone_id:
            for st in self.solver.schedules.get(highlighted_drone_id, []):
                if not st.is_wait:
                    highlighted_edges.add(self.solver._canonical_link_id(st.connection))

        for link in self.graph.link_dict.values():
            u = self.graph.nodes_dict[link.from_zone]
            v = self.graph.nodes_dict[link.to_zone]
            p1 = self.camera.to_screen(u.x, u.y)
            p2 = self.camera.to_screen(v.x, v.y)

            cid = self.solver._canonical_link_id(link)
            is_highlighted = cid in highlighted_edges
            transit_info = active_Transits.get(cid)

            if is_highlighted:
                pygame.draw.line(surface, (75, 165, 235), p1, p2, 6)
                pygame.draw.aaline(surface, (215, 248, 255), p1, p2)
            elif transit_info is not None:
                from_z, to_z, _, is_rest = transit_info
                glow_col = (245, 145, 85) if is_rest else (70, 155, 235)
                core_col = (255, 220, 175) if is_rest else (175, 240, 255)
                pygame.draw.line(surface, glow_col, p1, p2, 4)
                pygame.draw.aaline(surface, core_col, p1, p2)

                # Emit photon pulses traveling from `from_z` to `to_z`.
                src_hub = self.graph.nodes_dict[from_z]
                dst_hub = self.graph.nodes_dict[to_z]
                sp1 = self.camera.to_screen_float(src_hub.x, src_hub.y)
                sp2 = self.camera.to_screen_float(dst_hub.x, dst_hub.y)
                for p_idx in range(2):
                    phase = (elapsed * 1.6 + p_idx * 0.5) % 1.0
                    px = int(sp1[0] + (sp2[0] - sp1[0]) * phase)
                    py = int(sp1[1] + (sp2[1] - sp1[1]) * phase)
                    self.glow.draw(surface, (px, py), 7, core_col, peak_alpha=95)
                    pygame.draw.circle(surface, (255, 255, 255), (px, py), 2)
            else:
                # Idle cable: subtle and elegant.
                pygame.draw.line(surface, (28, 36, 62), p1, p2, 2)
                pygame.draw.aaline(surface, (54, 68, 106), p1, p2)

    def _draw_hubs(
        self, surface: pygame.Surface, elapsed: float
    ) -> dict[str, tuple[int, int]]:
        """Draw hubs with sacred geometry, soft glows, and capacity indicators."""
        node_radius = int(clamp(self.camera.zoom * 0.20, 9.0, 24.0))
        screen_positions: dict[str, tuple[int, int]] = {}

        active_turn = min(self.solver.total_turns, int(math.floor(self.sim_time)) + 1)
        if self.sim_time <= 0.0 or self.sim_time >= float(self.solver.total_turns):
            active_turn = int(round(self.sim_time))

        # Expanding waves at the goal.
        for sw in list(self.shockwaves):
            sx, sy = self.camera.to_screen(sw.x, sw.y)
            r = int(node_radius + sw.progress * node_radius * 3.8)
            alpha = int(clamp((1.0 - sw.progress) * 190, 0, 255))
            if alpha > 5:
                ring_surf = pygame.Surface((r * 2 + 6, r * 2 + 6), pygame.SRCALPHA)
                pygame.draw.circle(
                    ring_surf, (*sw.color, alpha), (r + 3, r + 3), r, width=2
                )
                surface.blit(ring_surf, (sx - r - 3, sy - r - 3))

        for name, hub in self.graph.nodes_dict.items():
            sx, sy = self.camera.to_screen(hub.x, hub.y)
            screen_positions[name] = (sx, sy)
            col = resolve_color(hub.color, elapsed)

            is_focus = name in (self.selected_hub, self.hovered_hub)
            breath = 1.0 + 0.08 * math.sin(elapsed * 2.4 + hub.x * 0.5 + hub.y * 0.5)
            glow_r = int(node_radius * (2.6 if is_focus else 2.0) * breath)

            # 1. Bioluminescent aura.
            self.glow.draw(
                surface, (sx, sy), glow_r, col, peak_alpha=95 if is_focus else 62
            )

            # 2. Outer geometry based on the hub's role.
            if hub.directive == "start_hub":
                # Double orbital ring at the start.
                pygame.draw.circle(
                    surface, (105, 242, 215), (sx, sy), node_radius + 7, width=2
                )
                for k in range(3):
                    ang = elapsed * 1.4 + k * (2.0 * math.pi / 3.0)
                    ox = sx + int(math.cos(ang) * (node_radius + 7))
                    oy = sy + int(math.sin(ang) * (node_radius + 7))
                    pygame.draw.circle(surface, (220, 255, 245), (ox, oy), 2)

            elif hub.directive == "end_hub":
                # Harmonic crown at the goal.
                pygame.draw.circle(surface, col, (sx, sy), node_radius + 8, width=2)
                pygame.draw.circle(
                    surface, (255, 255, 255), (sx, sy), node_radius + 4, width=1
                )

            elif hub.zone == HubType.PRIORITY:
                # Golden orbital diamond for PRIORITY hubs.
                d = node_radius + 6
                pts = [(sx, sy - d), (sx + d, sy), (sx, sy + d), (sx - d, sy)]
                pygame.draw.polygon(surface, (255, 220, 115), pts, width=2)

            elif hub.zone == HubType.RESTRICTED:
                # Amber-crimson containment ring for RESTRICTED hubs (2 turns).
                pygame.draw.circle(
                    surface, (255, 115, 95), (sx, sy), node_radius + 4, width=2
                )

            elif hub.zone == HubType.BLOCKED:
                pygame.draw.circle(
                    surface, (240, 75, 95), (sx, sy), node_radius + 3, width=2
                )

            # 3. Multilayer hub core.
            pygame.draw.circle(surface, (14, 18, 34), (sx, sy), node_radius + 2)
            pygame.draw.circle(surface, col, (sx, sy), node_radius)
            # Inner crystalline reflection.
            inner_r = max(3, int(node_radius * 0.42))
            pygame.draw.circle(surface, (250, 253, 255), (sx, sy), inner_r)

            # 4. Orbital occupancy indicators (`used / max_drones`, without text).
            if (
                hub.directive not in ("start_hub", "end_hub")
                and 1 <= hub.max_drones <= 6
                and self.camera.zoom >= 32.0
            ):
                occ = self.solver.hub_reservations[name].get(active_turn, 0)
                pip_r = node_radius + 6
                for p in range(hub.max_drones):
                    ang = -math.pi * 0.5 + (p - (hub.max_drones - 1) * 0.5) * 0.42
                    px = sx + int(math.cos(ang) * pip_r)
                    py = sy + int(math.sin(ang) * pip_r)
                    p_col = (125, 245, 255) if p < occ else (55, 68, 102)
                    pygame.draw.circle(surface, p_col, (px, py), 2)

            if is_focus:
                pygame.draw.circle(
                    surface, (255, 255, 255), (sx, sy), node_radius + 10, width=2
                )

        return screen_positions

    def _draw_drones(
        self, surface: pygame.Surface, drone_states: list[DroneRenderState]
    ) -> None:
        """Draw tapered silk trails and the oriented drone bodies."""
        drone_radius = int(clamp(self.camera.zoom * 0.105, 5.0, 11.0))

        # 1. Tapered ribbon trails.
        for st in drone_states:
            if not st.is_active:
                continue
            pts = [self.camera.to_screen(wx, wy) for wx, wy in self.trails[st.drone_id]]
            if len(pts) >= 2:
                col = self.drone_colors[st.drone_id]
                pygame.draw.aalines(surface, col, False, pts)
                # Decreasing points of light along the trail.
                for i in range(0, len(pts), 3):
                    frac = (i + 1) / len(pts)
                    r_pt = max(1, int(drone_radius * 0.55 * frac))
                    pygame.draw.circle(surface, col, pts[i], r_pt)

        # 2. Glowing body and directional nose of each drone.
        for st in drone_states:
            ix, iy = int(round(st.sx)), int(round(st.sy))
            col = self.drone_colors[st.drone_id]
            is_focus = st.drone_id in (self.selected_drone, self.hovered_drone)

            self.glow.draw(
                surface,
                (ix, iy),
                int(drone_radius * (3.0 if is_focus else 2.2)),
                col,
                peak_alpha=105 if is_focus else 72,
            )

            # Show an amber containment halo while crossing a RESTRICTED hub.
            if st.in_restricted:
                pygame.draw.circle(
                    surface, (255, 165, 80), (ix, iy), drone_radius + 4, width=1
                )

            # Draw a soft, oriented droplet/firefly silhouette while in flight.
            if st.is_active:
                nose_x = ix + int(math.cos(st.heading_rad) * (drone_radius + 3))
                nose_y = iy + int(math.sin(st.heading_rad) * (drone_radius + 3))
                pygame.draw.line(
                    surface, (255, 255, 255), (ix, iy), (nose_x, nose_y), 2
                )

            pygame.draw.circle(surface, (12, 16, 30), (ix, iy), drone_radius + 1)
            pygame.draw.circle(surface, col, (ix, iy), drone_radius)
            pygame.draw.circle(
                surface, (255, 255, 255), (ix, iy), max(2, drone_radius // 2)
            )

            if is_focus:
                pygame.draw.circle(
                    surface, (255, 255, 255), (ix, iy), drone_radius + 6, width=2
                )

    def _draw_pill_badge(
        self,
        surface: pygame.Surface,
        text_surf: pygame.Surface,
        anchor: tuple[int, int],
        center_pos: tuple[float, float],
        border_color: tuple[int, int, int],
        bg_alpha: int = 195,
    ) -> None:
        """Draw a frosted-glass pill with a subtle leader line when separated."""
        tw, th = text_surf.get_size()
        pad_x, pad_y = 7, 3
        bw, bh = tw + pad_x * 2, th + pad_y * 2
        cx, cy = int(round(center_pos[0])), int(round(center_pos[1]))
        rect = pygame.Rect(cx - bw // 2, cy - bh // 2, bw, bh)

        # Subtle leader line between the object and its label.
        dist = math.hypot(cx - anchor[0], cy - anchor[1])
        if dist > 20.0:
            pygame.draw.aaline(surface, (*border_color, 95), anchor, (cx, cy))

        pill = pygame.Surface((bw, bh), pygame.SRCALPHA)
        pygame.draw.rect(
            pill, (14, 18, 36, bg_alpha), (0, 0, bw, bh), border_radius=8
        )
        pygame.draw.rect(
            pill, (*border_color, 145), (0, 0, bw, bh), width=1, border_radius=8
        )
        surface.blit(pill, rect.topleft)
        surface.blit(text_surf, (rect.x + pad_x, rect.y + pad_y))

    def _draw_all_labels(
        self,
        surface: pygame.Surface,
        node_screen_pos: dict[str, tuple[int, int]],
        drone_states: list[DroneRenderState],
        groups: dict[str, list[str]],
        font_node: pygame.font.Font,
        font_drone: pygame.font.Font,
        elapsed: float,
        dt: float,
    ) -> None:
        """Update damped label physics and render labels without flicker."""
        node_radius = int(clamp(self.camera.zoom * 0.20, 9.0, 24.0))
        drone_radius = int(clamp(self.camera.zoom * 0.105, 5.0, 11.0))

        # 1. Cache hub text surfaces and update their dimensions.
        for name in self.graph.nodes_dict:
            if name not in self._node_text_cache:
                self._node_text_cache[name] = font_node.render(
                    name, True, self.TEXT_BRIGHT
                )
            ts = self._node_text_cache[name]
            st = self.label_engine.node_labels[name]
            st.width, st.height = ts.get_width() + 14, ts.get_height() + 6

        self.label_engine.update_node_labels(node_screen_pos, node_radius, dt)

        # Draw hub labels.
        if self.show_node_names:
            for name, hub in self.graph.nodes_dict.items():
                ax, ay = node_screen_pos[name]
                st = self.label_engine.node_labels[name]
                col = resolve_color(hub.color, elapsed)
                self._draw_pill_badge(
                    surface=surface,
                    text_surf=self._node_text_cache[name],
                    anchor=(ax, ay),
                    center_pos=(ax + st.cur_dx, ay + st.cur_dy),
                    border_color=col,
                    bg_alpha=190,
                )

        # 2. Drone labels (with smooth physics).
        if self.drone_label_mode == 2:
            return

        active_tuples: list[tuple[str, float, float]] = []
        for dst in drone_states:
            show_this = (
                self.drone_label_mode == 1
                or dst.is_active
                or dst.drone_id in (self.selected_drone, self.hovered_drone)
                or len(groups.get(dst.group_key, [])) <= 3
            )
            if show_this:
                if dst.drone_id not in self._drone_text_cache:
                    self._drone_text_cache[dst.drone_id] = font_drone.render(
                        dst.drone_id, True, self.drone_colors[dst.drone_id]
                    )
                active_tuples.append((dst.drone_id, dst.sx, dst.sy))

        self.label_engine.update_drone_labels(
            active_tuples, node_screen_pos, drone_radius, dt
        )

        for did, sx, sy in active_tuples:
            st = self.label_engine.drone_labels[did]
            ts = self._drone_text_cache[did]
            st.width, st.height = ts.get_width() + 12, ts.get_height() + 6
            self._draw_pill_badge(
                surface=surface,
                text_surf=ts,
                anchor=(int(round(sx)), int(round(sy))),
                center_pos=(sx + st.cur_dx, sy + st.cur_dy),
                border_color=self.drone_colors[did],
                bg_alpha=215,
            )

    def _draw_inspector_card(
        self,
        surface: pygame.Surface,
        drone_states: list[DroneRenderState],
        font_title: pygame.font.Font,
        font_body: pygame.font.Font,
    ) -> None:
        """Floating side panel with live telemetry for the selected hub or drone."""
        target_drone = self.selected_drone or self.hovered_drone
        target_hub = self.selected_hub or self.hovered_hub

        if not target_drone and not target_hub:
            return

        card_w, card_h = 310, 175
        card_x, card_y = self.width - card_w - 24, 78
        card = pygame.Surface((card_w, card_h), pygame.SRCALPHA)
        pygame.draw.rect(
            card, self.PANEL_BG, (0, 0, card_w, card_h), border_radius=14
        )
        pygame.draw.rect(
            card,
            self.PANEL_BORDER,
            (0, 0, card_w, card_h),
            width=1,
            border_radius=14,
        )

        lines: list[tuple[str, tuple[int, int, int]]] = []

        if target_drone:
            col = self.drone_colors.get(target_drone, self.TEXT_ACCENT)
            dst = next((d for d in drone_states if d.drone_id == target_drone), None)
            arr_t = self.arrival_turns.get(target_drone, 0)
            dep_t = self.departure_turns.get(target_drone, 0)
            steps = [
                s.to_zone
                for s in self.solver.schedules.get(target_drone, [])
                if not s.is_wait and not s.is_restricted_transit
            ]
            route_preview = " → ".join(steps[:4]) + (" …" if len(steps) > 4 else "")

            lines.append((f"✦ DRONE {target_drone}", col))
            if dst:
                lines.append((f"Status: {dst.status_text}", self.TEXT_BRIGHT))
            lines.append(
                (f"Departure: Turn {dep_t}   ·   Arrival: Turn {arr_t}", self.TEXT_SOFT)
            )
            lines.append((f"Total hops: {len(steps)} connections", self.TEXT_SOFT))
            lines.append((f"Route: {route_preview}", self.TEXT_ACCENT))

        elif target_hub and target_hub in self.graph.nodes_dict:
            hub = self.graph.nodes_dict[target_hub]
            active_turn = min(
                self.solver.total_turns, int(math.floor(self.sim_time)) + 1
            )
            occ = self.solver.hub_reservations[target_hub].get(active_turn, 0)
            h_val = self.solver.heuristics.get(target_hub, -1)
            neighbors = len(self.graph.get_neighbors(target_hub))

            lines.append((f"✦ HUB: {hub.name}", self.TEXT_ACCENT))
            lines.append(
                (
                    f"Type: {hub.zone.value.upper()}   ·   Role: {hub.directive}",
                    self.TEXT_BRIGHT,
                )
            )
            lines.append(
                (
                    f"Coordinates: ({hub.x}, {hub.y})   ·   Links: {neighbors}",
                    self.TEXT_SOFT,
                )
            )
            if hub.directive in ("start_hub", "end_hub"):
                lines.append(("Capacity: Unlimited (terminal)", self.TEXT_SOFT))
            else:
                lines.append(
                    (
                        f"Current occupancy: {occ} / {hub.max_drones} drones",
                        self.TEXT_SOFT,
                    )
                )
            if h_val >= 0:
                lines.append(
                    (f"Minimum distance to goal h(u): {h_val} turns", self.TEXT_ACCENT)
                )

        y_off = 16
        for idx, (txt, col) in enumerate(lines):
            f = font_title if idx == 0 else font_body
            surf = f.render(txt, True, col)
            card.blit(surf, (18, y_off))
            y_off += 30 if idx == 0 else 26

        surface.blit(card, (card_x, card_y))

    def _draw_hud(
        self,
        surface: pygame.Surface,
        font_title: pygame.font.Font,
        font_ui: pygame.font.Font,
        font_small: pygame.font.Font,
    ) -> None:
        """Minimal frosted-glass top and bottom interface."""
        # Top bar.
        top_w = self.width - 40
        top = pygame.Surface((top_w, 50), pygame.SRCALPHA)
        pygame.draw.rect(top, self.PANEL_BG, (0, 0, top_w, 50), border_radius=14)
        pygame.draw.rect(
            top, self.PANEL_BORDER, (0, 0, top_w, 50), width=1, border_radius=14
        )
        surface.blit(top, (20, 14))

        turn_disp = int(math.ceil(self.sim_time - 1e-6)) if self.sim_time > 1e-5 else 0
        arrived = sum(
            1
            for d in self.solver.drones
            if self.arrival_turns.get(d.id, 0) > 0
            and self.sim_time >= float(self.arrival_turns[d.id]) - 1e-5
        )

        surface.blit(
            font_title.render("✦ FLY-IN // ASTRAL ENGINE", True, self.TEXT_BRIGHT),
            (38, 28),
        )

        st_label = "● PLAYING" if self.playing else "● PAUSED"
        st_color = (105, 242, 195) if self.playing else (255, 215, 115)
        surface.blit(font_ui.render(st_label, True, st_color), (310, 30))

        stats_txt = (
            f"Turn: {turn_disp} / {self.solver.total_turns}     ·     "
            f"At Goal: {arrived} / {self.graph.n_drones}     ·     "
            f"Speed: {self.turns_per_sec:.2f} turns/s"
        )
        surface.blit(font_ui.render(stats_txt, True, self.TEXT_BRIGHT), (485, 30))

        # Bottom bar with interactive timeline.
        bot_w = self.width - 40
        bot = pygame.Surface((bot_w, 58), pygame.SRCALPHA)
        pygame.draw.rect(bot, self.PANEL_BG, (0, 0, bot_w, 58), border_radius=14)
        pygame.draw.rect(
            bot, self.PANEL_BORDER, (0, 0, bot_w, 58), width=1, border_radius=14
        )
        surface.blit(bot, (20, self.height - 72))

        bar_x, bar_y, bar_w, bar_h = 42, self.height - 56, self.width - 84, 8
        pygame.draw.rect(
            surface, (34, 44, 78), (bar_x, bar_y, bar_w, bar_h), border_radius=4
        )

        # Subtle turn markers on the timeline.
        if 1 <= self.solver.total_turns <= 60:
            for t_mark in range(1, self.solver.total_turns):
                mx = bar_x + int((t_mark / self.solver.total_turns) * bar_w)
                pygame.draw.line(
                    surface, (55, 70, 115), (mx, bar_y), (mx, bar_y + bar_h - 1), 1
                )

        if self.solver.total_turns > 0:
            pct = clamp(self.sim_time / float(self.solver.total_turns), 0.0, 1.0)
            fill_w = int(bar_w * pct)
            pygame.draw.rect(
                surface, (105, 210, 255), (bar_x, bar_y, fill_w, bar_h), border_radius=4
            )
            knob_pos = (bar_x + fill_w, bar_y + bar_h // 2)
            self.glow.draw(surface, knob_pos, 14, (125, 225, 255), peak_alpha=110)
            pygame.draw.circle(surface, (245, 252, 255), knob_pos, 6)

        mode_names = {0: "Active", 1: "All", 2: "Hidden"}
        controls = (
            f"[SPACE] Play/Pause  ·  [←/→] Turn  ·  [↑/↓] Speed  ·  "
            f"[N] Hubs: {'ON' if self.show_node_names else 'OFF'}  ·  "
            f"[D] Drones: {mode_names[self.drone_label_mode]}  ·  "
            f"[F] Fit  ·  [Click] Inspect"
        )
        surface.blit(
            font_small.render(controls, True, self.TEXT_SOFT), (42, self.height - 36)
        )

    def _update_hover(
        self,
        mouse_pos: tuple[int, int],
        node_screen_pos: dict[str, tuple[int, int]],
        drone_states: list[DroneRenderState],
    ) -> None:
        mx, my = mouse_pos
        self.hovered_drone = None
        self.hovered_hub = None

        # Prioritize drones under the cursor.
        best_d_dist = 16.0
        for dst in drone_states:
            d = math.hypot(mx - dst.sx, my - dst.sy)
            if d < best_d_dist:
                best_d_dist = d
                self.hovered_drone = dst.drone_id

        if self.hovered_drone is None:
            best_h_dist = 24.0
            for name, (hx, hy) in node_screen_pos.items():
                d = math.hypot(mx - hx, my - hy)
                if d < best_h_dist:
                    best_h_dist = d
                    self.hovered_hub = name
