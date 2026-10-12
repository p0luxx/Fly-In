from dataclasses import dataclass

@dataclass
class Connection:
    from_zone: str = ""
    to_zone: str = ""
    max_link_capacity: int = 1

    @property
    def id(self) -> str:
        return f"{self.from_zone}-{self.to_zone}"



"""
if __name__ == "__main__":
    link_a: Connection = Connection(from_zone="start_hub",
                                    to_zone="node_1a",
                                    max_link_capacity=1)
    print(link_a, "\n" + link_a.id)
"""