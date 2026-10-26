from collections.abc import Generator

from Backend.Zones.conection import Connection


class Drone:
    def __init__(self, id: str, path: list[Connection]) -> None:
        self.id = id
        self.path = path
        self.steps: Generator[Connection, None, None] = self._next_step()
        self.c_pos: Connection | None = None

    def _next_step(self) -> Generator[Connection, None, None]:
        for step in self.path:
            self.c_pos = step
            yield step
