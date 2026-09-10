from __future__ import annotations

from dataclasses import dataclass

from memoria_resolutiva.address_trajectory_v2 import AddressTrajectoryMemory
from memoria_resolutiva.hierarchical_composition_v2 import HierarchicalCompositionEngine


@dataclass(frozen=True, slots=True)
class ScaleEvidence:
    depth: int
    query_addresses: tuple[str, ...]
    trajectory_addresses: tuple[str, ...]
    overlap: int
    ordered_overlap: int
    max_hops_to_terminal: int
    sum_hops_to_terminal: int

    @property
    def structural_key(self) -> tuple[int, int, int, int, int]:
        return (
            self.overlap,
            self.ordered_overlap,
            -self.max_hops_to_terminal,
            -self.sum_hops_to_terminal,
            -len(self.trajectory_addresses),
        )


@dataclass(frozen=True, slots=True)
class MultiscaleMatch:
    trajectory_id: str
    raw_text: str
    terminal_surface: str | None
    scale_evidence: tuple[ScaleEvidence, ...]
    supporting_depths: tuple[int, ...]

    @property
    def multiscale_key(self) -> tuple[int, tuple[tuple[int, int, int, int, int], ...], str]:
        # More distinct hierarchy levels agreeing on the same trajectory is the
        # primary signal. Within that, compare scale evidence lexicographically.
        # No learned scalar weights are introduced.
        ranked = tuple(
            sorted((evidence.structural_key for evidence in self.scale_evidence), reverse=True)
        )
        return (len(self.supporting_depths), ranked, self.trajectory_id)


class MultiscaleAddressResolver:
    """Resolve the same query simultaneously in atomic and hierarchical address spaces.

    The resolver does not preselect a semantic level. Depth 0 is the atomic stream;
    deeper levels are deterministic recurring-composition views. A stored trajectory
    gains support when the same query structurally converges on it at several scales.
    """

    def __init__(
        self,
        memory: AddressTrajectoryMemory,
        *,
        max_depth: int = 3,
        min_occurrences: int = 2,
        min_trajectory_count: int = 2,
        min_size: int = 2,
        max_size: int = 3,
        max_compositions_per_level: int = 2048,
    ) -> None:
        self.memory = memory
        self.hierarchy = HierarchicalCompositionEngine(
            memory,
            max_depth=max_depth,
            min_occurrences=min_occurrences,
            min_trajectory_count=min_trajectory_count,
            min_size=min_size,
            max_size=max_size,
            max_compositions_per_level=max_compositions_per_level,
        )

    @staticmethod
    def _ordered_overlap(query: tuple[str, ...], candidate: tuple[str, ...]) -> int:
        if not query or not candidate:
            return 0
        prev = [0] * (len(candidate) + 1)
        for q in query:
            curr = [0]
            for index, c in enumerate(candidate, start=1):
                if q == c:
                    curr.append(prev[index - 1] + 1)
                else:
                    curr.append(max(curr[-1], prev[index]))
            prev = curr
        return prev[-1]

    @staticmethod
    def _route_hops(query: tuple[str, ...], candidate: tuple[str, ...]) -> tuple[int, ...]:
        if not candidate:
            return ()
        terminal_index = len(candidate) - 1
        hops: list[int] = []
        for address in dict.fromkeys(query):
            positions = [index for index, item in enumerate(candidate) if item == address]
            if positions:
                hops.append(terminal_index - max(positions))
        return tuple(sorted(hops))

    def _views(self, text: str) -> tuple[tuple[int, tuple[str, ...]], ...]:
        tokens = self.memory._collapse_immediate_tokens(self.memory.decompose(text))
        current = tuple(token.address for token in tokens)
        views: list[tuple[int, tuple[str, ...]]] = [(0, current)]
        for level in self.hierarchy.build():
            current = self.hierarchy._collapse_with_catalogue(current, level.compositions)
            views.append((level.depth, current))
        return tuple(views)

    def resolve(self, text: str, *, limit: int = 5) -> tuple[MultiscaleMatch, ...]:
        query_views = dict(self._views(text))
        levels = self.hierarchy.build()

        trajectory_views: dict[str, dict[int, tuple[str, ...]]] = {
            trajectory.trajectory_id: {0: trajectory.addresses}
            for trajectory in self.memory.snapshot()
        }
        for level in levels:
            for trajectory_id, addresses in level.transformed_trajectories:
                trajectory_views.setdefault(trajectory_id, {})[level.depth] = addresses

        matches: list[MultiscaleMatch] = []
        trajectory_by_id = {trajectory.trajectory_id: trajectory for trajectory in self.memory.snapshot()}

        for trajectory_id, by_depth in trajectory_views.items():
            evidence: list[ScaleEvidence] = []
            for depth, query in query_views.items():
                candidate = by_depth.get(depth)
                if candidate is None or not query or not candidate:
                    continue
                overlap = len(set(query) & set(candidate))
                if overlap == 0:
                    continue
                hops = self._route_hops(query, candidate)
                evidence.append(
                    ScaleEvidence(
                        depth=depth,
                        query_addresses=query,
                        trajectory_addresses=candidate,
                        overlap=overlap,
                        ordered_overlap=self._ordered_overlap(query, candidate),
                        max_hops_to_terminal=max(hops) if hops else 0,
                        sum_hops_to_terminal=sum(hops),
                    )
                )

            if not evidence:
                continue
            trajectory = trajectory_by_id[trajectory_id]
            supporting_depths = tuple(sorted(item.depth for item in evidence))
            matches.append(
                MultiscaleMatch(
                    trajectory_id=trajectory_id,
                    raw_text=trajectory.raw_text,
                    terminal_surface=trajectory.surfaces[-1] if trajectory.surfaces else None,
                    scale_evidence=tuple(evidence),
                    supporting_depths=supporting_depths,
                )
            )

        matches.sort(key=lambda item: item.multiscale_key, reverse=True)
        return tuple(matches[: max(0, limit)])
