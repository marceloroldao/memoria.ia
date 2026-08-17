from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class Occurrence:
    memory_id: str
    layer: int
    local_time: int
    node_id: str
