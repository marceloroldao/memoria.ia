from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass

from .structural_trajectory_v2 import StructuralTrajectoryIndex


@dataclass(frozen=True, slots=True)
class StructuralDensityProfileV2:
    hierarchy_id: str
    address: int
    occurrences: int
    trajectory_count: int
    predecessor_count: int
    successor_count: int
    connection_count: int

    @property
    def density_key(self) -> tuple[int, int, int, int, int]:
        return (
            self.trajectory_count,
            self.connection_count,
            self.occurrences,
            self.predecessor_count + self.successor_count,
            self.address,
        )


class StructuralDensityEngineV2:
    """Measure observed topology without banning or semantically labeling hubs."""

    def __init__(self, trajectories: StructuralTrajectoryIndex) -> None:
        self.trajectories = trajectories

    def profiles(
        self,
        *,
        hierarchy_id: str,
    ) -> tuple[StructuralDensityProfileV2, ...]:
        hierarchy = str(hierarchy_id).strip()
        if not hierarchy:
            raise ValueError("hierarchy_id must be non-empty")

        occurrences: dict[int, int] = defaultdict(int)
        supporting: dict[int, set[str]] = defaultdict(set)
        predecessors: dict[int, set[int]] = defaultdict(set)
        successors: dict[int, set[int]] = defaultdict(set)

        for trajectory in self.trajectories.snapshot():
            if trajectory.hierarchy_id != hierarchy:
                continue
            addresses = trajectory.addresses
            for index, address in enumerate(addresses):
                occurrences[address] += 1
                supporting[address].add(trajectory.trajectory_id)
                if index > 0:
                    predecessors[address].add(addresses[index - 1])
                if index + 1 < len(addresses):
                    successors[address].add(addresses[index + 1])

        rows = [
            StructuralDensityProfileV2(
                hierarchy_id=hierarchy,
                address=address,
                occurrences=occurrences[address],
                trajectory_count=len(supporting[address]),
                predecessor_count=len(predecessors[address]),
                successor_count=len(successors[address]),
                connection_count=len(predecessors[address] | successors[address]),
            )
            for address in occurrences
        ]
        rows.sort(key=lambda item: item.density_key, reverse=True)
        return tuple(rows)

    def profile(
        self,
        address: int,
        *,
        hierarchy_id: str,
    ) -> StructuralDensityProfileV2 | None:
        target = int(address)
        for row in self.profiles(hierarchy_id=hierarchy_id):
            if row.address == target:
                return row
        return None
