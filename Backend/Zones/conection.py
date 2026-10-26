from dataclasses import dataclass


@dataclass
class Connection:
    from_zone: str = ""
    to_zone: str = ""
    max_link_capacity: int = 1

    @property
    def id(self) -> str:
        return f"{self.from_zone}-{self.to_zone}"

    def get_destination(self, current_zone: str) -> str:
        if current_zone == self.from_zone:
            return self.to_zone
        if current_zone == self.to_zone:
            return self.from_zone
        raise ValueError(
            f"Zone: {current_zone} is not part of connection {self.id}"
        )
