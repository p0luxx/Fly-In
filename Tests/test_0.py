from pathlib import Path

from Backend.Parser.map_parser import MapParser


def test_map_parser_loads_a_valid_map(tmp_path: Path) -> None:
    map_file = tmp_path / "map.txt"
    map_file.write_text(
        "\n".join(
            (
                "nb_drones: 1",
                "start_hub: start 0 0",
                "end_hub: goal 2 0",
                "connection: start-goal",
            )
        ),
        encoding="utf-8",
    )

    parsed_map = MapParser(file_name=str(map_file))

    assert parsed_map.nb_drones == 1
    assert [hub.name for hub in parsed_map.hubs] == ["start", "goal"]
    assert len(parsed_map.connections) == 1
