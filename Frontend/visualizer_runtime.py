"""Pygame window lifecycle, input handling, and frame loop."""
from __future__ import annotations

import math

import pygame

from Frontend.visualizer_support import DroneRenderState, clamp
from Frontend.visualizer_rendering import _VisualizerRendering

__all__ = ["_PygameRuntime"]


class _PygameRuntime(_VisualizerRendering):
    """Technical Pygame runtime mixed into :class:`FlyInVisualizer`."""

    def run(self) -> None:
        pygame.init()
        pygame.display.set_caption(
            f"Fly-In Astral Visualizer — {self.graph.n_drones} Drones | "
            f"{self.solver.total_turns} Turns"
        )
        screen = pygame.display.set_mode((self.width, self.height), pygame.RESIZABLE)
        clock = pygame.time.Clock()

        font_title = pygame.font.SysFont("sans", 16, bold=True)
        font_ui = pygame.font.SysFont("sans", 14, bold=True)
        font_node = pygame.font.SysFont("sans", 13, bold=True)
        font_drone = pygame.font.SysFont("sans", 11, bold=True)
        font_small = pygame.font.SysFont("sans", 12)

        dragging_cam = False
        scrubbing_timeline = False
        last_mouse = (0, 0)
        elapsed = 0.0

        node_screen_pos: dict[str, tuple[int, int]] = {}
        drone_states: list[DroneRenderState] = []

        running = True
        while running:
            dt = clamp(clock.tick(60) / 1000.0, 0.001, 0.05)
            elapsed += dt

            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    running = False

                elif event.type == pygame.VIDEORESIZE:
                    self.width, self.height = event.w, event.h
                    self.camera.width, self.camera.height = event.w, event.h
                    self._bg_surface = None
                    screen = pygame.display.set_mode(
                        (self.width, self.height), pygame.RESIZABLE
                    )

                elif event.type == pygame.KEYDOWN:
                    if event.key == pygame.K_ESCAPE:
                        running = False
                    elif event.key == pygame.K_SPACE:
                        if self.sim_time >= float(self.solver.total_turns):
                            self.sim_time = 0.0
                            self._triggered_arrivals.clear()
                            for tr in self.trails.values():
                                tr.clear()
                        self.playing = not self.playing
                    elif event.key == pygame.K_r:
                        self.sim_time = 0.0
                        self._triggered_arrivals.clear()
                        for tr in self.trails.values():
                            tr.clear()
                        self.playing = True
                    elif event.key == pygame.K_f:
                        self.camera.fit_graph(self.graph, instant=False)
                    elif event.key == pygame.K_n:
                        self.show_node_names = not self.show_node_names
                    elif event.key == pygame.K_d:
                        self.drone_label_mode = (self.drone_label_mode + 1) % 3
                    elif event.key == pygame.K_l:
                        self.show_node_names = not self.show_node_names
                        self.drone_label_mode = 0 if self.show_node_names else 2
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
                        for tr in self.trails.values():
                            tr.clear()
                    elif event.key == pygame.K_UP:
                        self.turns_per_sec = min(8.0, self.turns_per_sec * 1.25)
                    elif event.key == pygame.K_DOWN:
                        self.turns_per_sec = max(0.2, self.turns_per_sec / 1.25)

                elif event.type == pygame.MOUSEBUTTONDOWN:
                    if event.button == 1:
                        if event.pos[1] >= self.height - 72:
                            scrubbing_timeline = True
                            self.playing = False
                            bar_x, bar_w = 42, self.width - 84
                            pct = clamp(
                                (event.pos[0] - bar_x) / max(1, bar_w), 0.0, 1.0
                            )
                            self.sim_time = pct * float(self.solver.total_turns)
                            for tr in self.trails.values():
                                tr.clear()
                        else:
                            # Select a drone or hub for the inspector when clicked.
                            if self.hovered_drone:
                                self.selected_drone = (
                                    None
                                    if self.selected_drone == self.hovered_drone
                                    else self.hovered_drone
                                )
                                self.selected_hub = None
                            elif self.hovered_hub:
                                self.selected_hub = (
                                    None
                                    if self.selected_hub == self.hovered_hub
                                    else self.hovered_hub
                                )
                                self.selected_drone = None
                            else:
                                self.selected_drone = None
                                self.selected_hub = None
                            dragging_cam = True
                            last_mouse = event.pos
                    elif event.button == 4:
                        self.camera.zoom_at(event.pos, 1.14)
                    elif event.button == 5:
                        self.camera.zoom_at(event.pos, 1.0 / 1.14)

                elif event.type == pygame.MOUSEBUTTONUP:
                    if event.button == 1:
                        dragging_cam = False
                        scrubbing_timeline = False

                elif event.type == pygame.MOUSEMOTION:
                    if scrubbing_timeline:
                        bar_x, bar_w = 42, self.width - 84
                        pct = clamp((event.pos[0] - bar_x) / max(1, bar_w), 0.0, 1.0)
                        self.sim_time = pct * float(self.solver.total_turns)
                    elif dragging_cam:
                        dx = event.pos[0] - last_mouse[0]
                        dy = event.pos[1] - last_mouse[1]
                        self.camera.pan(dx, dy)
                        last_mouse = event.pos

            # Update the camera, clock, and expanding shockwaves.
            self.camera.update(dt)

            if self.playing and self.solver.total_turns > 0:
                self.sim_time += dt * self.turns_per_sec
                if self.sim_time >= float(self.solver.total_turns):
                    self.sim_time = float(self.solver.total_turns)
                    self.playing = False

            for sw in list(self.shockwaves):
                sw.progress += dt * sw.speed
                if sw.progress >= 1.0:
                    self.shockwaves.remove(sw)

            # Render all layers in order.
            self._draw_atmosphere(screen, elapsed)
            self._draw_connections(screen, elapsed)
            node_screen_pos = self._draw_hubs(screen, elapsed)
            drone_states, groups = self._compute_all_drones_render_state(elapsed)
            self._draw_drones(screen, drone_states)
            self._update_hover(pygame.mouse.get_pos(), node_screen_pos, drone_states)
            self._draw_all_labels(
                screen,
                node_screen_pos,
                drone_states,
                groups,
                font_node,
                font_drone,
                elapsed,
                dt,
            )
            self._draw_inspector_card(screen, drone_states, font_title, font_small)
            self._draw_hud(screen, font_title, font_ui, font_small)

            pygame.display.flip()

        pygame.quit()
