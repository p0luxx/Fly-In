from Zones.conection import Connection
from typing import Generator

class Drone:
    def __init__(self, id: str, path: list[Connection]) -> None:
        self.id = id
        self.path = path
        self.steps: Generator = self._next_step()
        self.c_pos: Connection = None

    def _next_step(self) -> Generator[Connection]:
        try:
            for step in self.path:
                self.c_pos = step
                yield step
        except StopIteration as e:
            return e
