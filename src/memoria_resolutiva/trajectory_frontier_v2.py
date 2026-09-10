from __future__ import annotations

from dataclasses import dataclass

from memoria_resolutiva.address_trajectory_v2 import AddressTrajectoryMemory, AddressTrajectory
from memoria_resolutiva.multiscale_resolver_v2 import MultiscaleAddressResolver, MultiscaleMatch


@dataclass(frozen=True, slots=True)
class FrontierCandidate:
    trajectory_id: str
    surface: str | None
    address: str | None
    anchor_index: int
    frontier_index: int
    distance: int
    matched_addresses: tuple[str, ...]
    supporting_depths: tuple[int, ...]

    @property
    def structural_key(self) -> tuple[int, int, int, int, str]:
        return (
            len(self.supporting_depths),
            len(self.matched_addresses),
            -self.distance,
            -self.frontier_index,
            self.trajectory_id,
        )


class TrajectoryFrontierResolver:
    """Find the unresolved continuation of a structurally matched trajectory.

    The frontier is defined only by address geometry. The resolver does not know
    whether a surface is a name, colour, entity, answer or attribute. It finds the
    first address after the latest matched anchor that is not already present in
    the query. If no forward frontier exists it searches backward from the earliest
    anchor. Queries are read-only.
    """

    def __init__(self, memory: AddressTrajectoryMemory, *, max_depth: int = 3) -> None:
        self.memory = memory
        self.multiscale = MultiscaleAddressResolver(memory, max_depth=max_depth)

    @staticmethod
    def _frontier(
        trajectory: AddressTrajectory,
        query_addresses: tuple[str, ...],
        supporting_depths: tuple[int, ...],
    ) -> FrontierCandidate | None:
        query_set = set(query_addresses)
        matched_positions = [
            index for index, address in enumerate(trajectory.addresses)
            if address in query_set
        ]
        if not matched_positions:
            return None

        matched_addresses = tuple(
            dict.fromkeys(trajectory.addresses[index] for index in matched_positions)
        )
        latest = max(matched_positions)
        for index in range(latest + 1, len(trajectory.addresses)):
            address = trajectory.addresses[index]
            if address not in query_set:
                return FrontierCandidate(
                    trajectory_id=trajectory.trajectory_id,
                    surface=trajectory.surfaces[index],
                    address=address,
                    anchor_index=latest,
                    frontier_index=index,
                    distance=index - latest,
                    matched_addresses=matched_addresses,
                    supporting_depths=supporting_depths,
                )

        earliest = min(matched_positions)
        for index in range(earliest - 1, -1, -1):
            address = trajectory.addresses[index]
            if address not in query_set:
                return FrontierCandidate(
                    trajectory_id=trajectory.trajectory_id,
                    surface=trajectory.surfaces[index],
                    address=address,
                    anchor_index=earliest,
                    frontier_index=index,
                    distance=earliest - index,
                    matched_addresses=matched_addresses,
                    supporting_depths=supporting_depths,
                )
        return None

    def resolve(self, text: str, *, limit: int = 5) -> tuple[FrontierCandidate, ...]:
        query_tokens = self.memory._collapse_immediate_tokens(self.memory.decompose(text))
        query_addresses = tuple(token.address for token in query_tokens)
        if not query_addresses:
            return ()

        matches: tuple[MultiscaleMatch, ...] = self.multiscale.resolve(
            text, limit=max(limit * 4, 16)
        )
        by_id = {trajectory.trajectory_id: trajectory for trajectory in self.memory.snapshot()}
        candidates: list[FrontierCandidate] = []
        for match in matches:
            trajectory = by_id.get(match.trajectory_id)
            if trajectory is None:
                continue
            candidate = self._frontier(
                trajectory,
                query_addresses,
                match.supporting_depths,
            )
            if candidate is not None:
                candidates.append(candidate)

        candidates.sort(key=lambda item: item.structural_key, reverse=True)
        return tuple(candidates[: max(0, limit)])
