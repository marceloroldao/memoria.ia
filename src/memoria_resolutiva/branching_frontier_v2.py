from __future__ import annotations

from dataclasses import dataclass
from collections import defaultdict

from memoria_resolutiva.address_trajectory_v2 import AddressTrajectoryMemory
from memoria_resolutiva.trajectory_frontier_v2 import (
    FrontierCandidate,
    TrajectoryFrontierResolver,
)


@dataclass(frozen=True, slots=True)
class BranchHypothesis:
    address: str
    surface: str | None
    trajectory_ids: tuple[str, ...]
    supporting_depths: tuple[int, ...]
    matched_address_union: tuple[str, ...]
    min_distance: int
    max_distance: int
    candidate_count: int

    @property
    def structural_key(self) -> tuple[int, int, int, int, str]:
        # Structural consensus only: no learned scalar weights.
        return (
            len(self.supporting_depths),
            self.candidate_count,
            len(self.matched_address_union),
            -self.min_distance,
            self.address,
        )


@dataclass(frozen=True, slots=True)
class BranchResolution:
    query: str
    hypotheses: tuple[BranchHypothesis, ...]
    collapsed: BranchHypothesis | None
    ambiguous: bool


class BranchingFrontierResolver:
    """Keep multiple possible trajectory continuations alive until separated.

    Frontier candidates are grouped by continuation address. Independent stored
    trajectories that converge on the same next address reinforce the same branch
    structurally. Competing addresses remain separate hypotheses. No probability,
    semantic intent class, learned weight or domain rule is introduced.
    """

    def __init__(self, memory: AddressTrajectoryMemory, *, max_depth: int = 3) -> None:
        self.memory = memory
        self.frontier = TrajectoryFrontierResolver(memory, max_depth=max_depth)

    @staticmethod
    def _aggregate(candidates: tuple[FrontierCandidate, ...]) -> tuple[BranchHypothesis, ...]:
        grouped: dict[str, list[FrontierCandidate]] = defaultdict(list)
        for candidate in candidates:
            if candidate.address is not None:
                grouped[candidate.address].append(candidate)

        hypotheses: list[BranchHypothesis] = []
        for address, members in grouped.items():
            depths = sorted({depth for member in members for depth in member.supporting_depths})
            matched = sorted({item for member in members for item in member.matched_addresses})
            trajectory_ids = tuple(sorted({member.trajectory_id for member in members}))
            distances = [member.distance for member in members]
            surface = next((member.surface for member in members if member.surface is not None), None)
            hypotheses.append(
                BranchHypothesis(
                    address=address,
                    surface=surface,
                    trajectory_ids=trajectory_ids,
                    supporting_depths=tuple(depths),
                    matched_address_union=tuple(matched),
                    min_distance=min(distances),
                    max_distance=max(distances),
                    candidate_count=len(members),
                )
            )

        hypotheses.sort(key=lambda item: item.structural_key, reverse=True)
        return tuple(hypotheses)

    @staticmethod
    def _same_structural_evidence(left: BranchHypothesis, right: BranchHypothesis) -> bool:
        return left.structural_key[:-1] == right.structural_key[:-1]

    def resolve(self, text: str, *, limit: int = 8) -> BranchResolution:
        # Pull a wider frontier so grouping does not lose alternate branches too early.
        candidates = self.frontier.resolve(text, limit=max(limit * 8, 32))
        hypotheses = self._aggregate(candidates)
        visible = hypotheses[: max(0, limit)]
        if not visible:
            return BranchResolution(text, (), None, False)
        if len(visible) == 1:
            return BranchResolution(text, visible, visible[0], False)

        # Fail open to ambiguity when the leading branches have exactly the same
        # structural evidence. Deterministic address order is never treated as
        # cognitive superiority.
        ambiguous = self._same_structural_evidence(visible[0], visible[1])
        collapsed = None if ambiguous else visible[0]
        return BranchResolution(text, visible, collapsed, ambiguous)
