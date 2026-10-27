"""Load and validate map files for the Fly-In application."""
from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field, model_validator

from Backend.Zones.conection import Connection
from Backend.Zones.hub import Hub
from Backend.Zones.hub_type import HubType
import sys


class MapParser(BaseModel):
    file_name: str
    content: list[str] = Field(default_factory=list, exclude=True)
    nb_drones: int = 0
    hubs: list[Hub] = Field(default_factory=list)
    connections: list[Connection] = Field(default_factory=list)

    @model_validator(mode="after")
    def process_file_automatically(self) -> MapParser:
        self._read_file()
        self._parse_and_route()
        start_count = sum(hub.directive == "start_hub" for hub in self.hubs)
        end_count = sum(hub.directive == "end_hub" for hub in self.hubs)
        if start_count != 1 or end_count != 1:
            raise ValueError(
                "The map must contain exactly one start_hub and one end_hub."
            )
        return self

    def _read_file(self) -> None:
        try:
            with open(self.file_name, "r", encoding="utf-8") as map_file:
                raw_lines = map_file.readlines()
        except PermissionError as error:
            raise PermissionError(
                f"Permission denied while reading map file: {self.file_name}"
            ) from error
        except FileNotFoundError as error:
            raise FileNotFoundError(
                f"Map file not found: {self.file_name}"
            ) from error

        self.content = [
            line.strip()
            for line in raw_lines
            if line.strip() and not line.strip().startswith("#")
        ]

    def _parse_and_route(self) -> None:
        try:
            for line in self.content:
                if ":" not in line:
                    raise ValueError("Invalid map syntax: missing ':' separator.")
                key, value = (part.strip() for part in line.split(":", 1))
                match key:
                    case "nb_drones":
                        self._drone_processing(value)
                    case "start_hub" | "hub" | "end_hub":
                        self._hub_processor(key, value)
                    case "connection":
                        self._connection_processor(value)
                    case _:
                        raise ValueError(f"Unknown map directive: {key}")
        except ValueError as error:
            raise ValueError(f"Invalid map: {error}") from error

    def _drone_processing(self, value: str) -> None:
        self.nb_drones = int(value)

    def _hub_processor(self, directive: str, value: str) -> None:
        parts = value.split("[", 1)
        coordinates = parts[0].split()
        if len(coordinates) != 3:
            raise ValueError("A hub must define a name and x/y coordinates.")
        name, x_str, y_str = coordinates
        if "-" in name:
            print(f"The node name cannot contain hyphens: '{name}'")
            sys.exit()
        extras: dict[str, Any] = {}
        if len(parts) > 1:
            extra_raw = parts[1].strip()
            if not extra_raw.endswith("]"):
                raise ValueError("Invalid hub syntax: missing closing ']'.")
            for item in extra_raw[:-1].split():
                key, value_part = item.split("=", 1)
                try:
                    if value_part.lstrip("-").isnumeric():
                        extras[key] = int(value_part)
                    elif key == "zone":
                        extras[key] = HubType[value_part.upper()]
                    else:
                        extras[key] = value_part
                except KeyError as error:
                    raise ValueError(
                        "Invalid hub zone type; use a supported HubType."
                    ) from error
        try:
            self.hubs.append(
                Hub(
                    directive=directive,
                    name=name,
                    x=int(x_str),
                    y=int(y_str),
                    **extras,
                )
            )
        except TypeError as e:
            raise TypeError(
                "Unknown parameter within [...]"
            ) from e

    def _connection_processor(self, value: str) -> None:
        parts = value.strip().split("[", 1)
        route_str = parts[0].strip()
        if "-" not in route_str:
            raise ValueError(
                f"Invalid connection syntax (missing '-'): '{route_str}'"
            )

        from_zone, to_zone = (part.strip() for part in route_str.split("-", 1))
        if not from_zone or not to_zone:
            raise ValueError(f"Connection endpoints cannot be empty: '{route_str}'")

        capacity = 1
        if len(parts) > 1:
            extra_raw = parts[1].strip()
            if not extra_raw.endswith("]"):
                raise ValueError("Invalid connection syntax: missing closing ']'.")
            for item in extra_raw[:-1].split():
                if "=" not in item:
                    continue
                key, raw_value = item.split("=", 1)
                if key == "max_link_capacity":
                    if not raw_value.isdigit() or int(raw_value) <= 0:
                        raise ValueError(
                            "max_link_capacity must be a positive integer."
                        )
                    capacity = int(raw_value)

        self.connections.append(
            Connection(
                from_zone=from_zone,
                to_zone=to_zone,
                max_link_capacity=capacity,
            )
        )
