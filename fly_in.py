#!/bin/usr/python3
"""Command-line entry point for the Fly-In application."""
from __future__ import annotations

import argparse
import sys
from collections.abc import Sequence


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Plan routes for multiple drones and optionally visualize them."
    )
    parser.add_argument("map_file", help="Path to the map file.")
    parser.add_argument(
        "--no-gui",
        action="store_true",
        help="Run route planning without opening the Pygame visualizer.",
    )
    args = parser.parse_args(argv)

    try:
        from Backend.orchestrator import Orchestrator

        Orchestrator().run(args.map_file, use_gui=not args.no_gui)
    except (ValueError, FileNotFoundError, PermissionError, RuntimeError) as error:
        print(error, file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        print("\nThe program has been interrupted.", file=sys.stderr)
        sys.exit(130)
