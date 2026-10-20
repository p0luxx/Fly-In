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
        elif current_zone == self.to_zone:
            return self.from_zone
        else:
            raise ValueError(f"Zone: {current_zone} is not part of connection {self.id}")



"""
if __name__ == "__main__":
    link_a: Connection = Connection(from_zone="start_hub",
                                    to_zone="node_1a",
                                    max_link_capacity=1)
    print(link_a, "\n" + link_a.id)
"""