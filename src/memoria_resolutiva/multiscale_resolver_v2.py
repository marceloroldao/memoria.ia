from __future__ import annotations

from dataclasses import dataclass

from .hierarchical_composition_v2 import (
    HierarchicalCompositionEngineV2,
    ScaleAddress,
)
from .structural_density_v2 import StructuralDensityEngineV2, StructuralDensityProfileV2
from .structural_trajectory_v2 import StructuralTrajectoryIndex


@dataclass(frozen=True, slots=True)
class ScaleEvidenceV2:
    depth: int
    query_addresses: tuple[ScaleAddress, ...]
    trajectory_addresses: tuple[ScaleAddress, ...]
    overlap: int
    ordered_overlap: int
    adjacency_overlap: int
    query_coverage_num: int
    query_coverage_den: int

    @property
    def structural_key(self) -> tuple[int, int, int, int, int]:
        return (
            self.query_coverage_num,
            -max(1, self.query_coverage_den),
            self.ordered_overlap,
            self.adjacency_overlap,
            self.overlap,
        )


@dataclass(frozen=True, slots=True)
class MultiscaleTrajectoryMatchV2:
    trajectory_id: str
    source_id: str
    sequence: int
    scale_evidence: tuple[ScaleEvidenceV2, ...]
    supporting_depths: tuple[int, ...]
    terminal_density: StructuralDensityProfileV2 | None

    @property
    def atomic_evidence(self) -> ScaleEvidenceV2:
        for evidence in self.scale_evidence:
            if evidence.depth == 0:
                return evidence
        raise ValueError("multiscale match requires atomic evidence")

    @property
    def multiscale_key(
        self,
    ) -> tuple[
        tuple[int, int, int, int, int],
        int,
        tuple[tuple[int, int, int, int, int], ...],
        str,
    ]:
        """Atomic evidence always dominates derived hierarchical evidence.

        This blocks a recurrent derived composition from manufacturing consensus
        for a trajectory that has weaker support at the non-derived observation
        boundary. No learned scalar weights or semantic rules are used.
        """
        derived = tuple(
            sorted(
                (
                    evidence.structural_key
                    for evidence in self.scale_evidence
                    if evidence.depth != 0
                ),
                reverse=True,
            )
        )
        return (
            self.atomic_evidence.structural_key,
            len(self.supporting_depths),
            derived,
            self.trajectory_id,
        )


class MultiscaleStructuralResolverV2:
    """Resolve opaque queries across atomic and derived hierarchy views."""

    def __init__(
        self,
        trajectories: StructuralTrajectoryIndex,
        *,
        max_depth: int = 3,
        min_occurrences: int = 2,
        min_trajectory_count: int = 2,
        min_size: int = 2,
        max_size: int = 3,
        max_compositions_per_level: int = 2048,
    ) -> None:
        self.trajectories = trajectories
        self.hierarchy = HierarchicalCompositionEngineV2(
            trajectories,
            max_depth=max_depth,
            min_occurrences=min_occurrences,
            min_trajectory_count=min_trajectory_count,
            min_size=min_size,
            max_size=max_size,
            max_compositions_per_level=max_compositions_per_level,
        )
        self.density = StructuralDensityEngineV2(trajectories)

    @staticmethod
    def _ordered_overlap(
        query: tuple[ScaleAddress, ...],
        candidate: tuple[ScaleAddress, ...],
    ) -> int:
        if not query or not candidate:
            return 0
        previous = [0] * (len(candidate) + 1)
        for q in query:
            current = [0]
            for index, value in enumerate(candidate, start=1):
                if q == value:
                    current.append(previous[index - 1] + 1)
                else:
                    current.append(max(current[-1], previous[index]))
            previous = current
        return previous[-1]

    @staticmethod
    def _adjacency_overlap(
        query: tuple[ScaleAddress, ...],
        candidate: tuple[ScaleAddress, ...],
    ) -> int:
        if len(query) < 2 or len(candidate) < 2:
            return 0
        pairs = set(zip(query, query[1:]))
        return sum(1 for pair in zip(candidate, candidate[1:]) if pair in pairs)

    def _query_views(
        self,
        addresses: tuple[int, ...],
        *,
        hierarchy_id: str,
    ) -> tuple[tuple[int, tuple[ScaleAddress, ...]], ...]:
        current: tuple[ScaleAddress, ...] = tuple(addresses)
        views: list[tuple[int, tuple[ScaleAddress, ...]]] = [(0, current)]
        for level in self.hierarchy.build(hierarchy_id=hierarchy_id):
            current = self.hierarchy.collapse_with_catalogue(
                current,
                level.compositions,
            )
            views.append((level.depth, current))
        return tuple(views)

    def resolve_addresses(
        self,
        addresses: tuple[int, ...] | list[int],
        *,
        hierarchy_id: str,
        limit: int = 8,
    ) -> tuple[MultiscaleTrajectoryMatchV2, ...]:
        hierarchy = str(hierarchy_id).strip()
        if not hierarchy:
            raise ValueError("hierarchy_id must be non-empty")
        if limit < 1:
            raise ValueError("limit must be >= 1")
        query = tuple(int(value) for value in addresses)
        if not query:
            raise ValueError("query must contain at least one structural address")
        if any(value < 0 for value in query):
            raise ValueError("structural addresses must be >= 0")

        levels = self.hierarchy.build(hierarchy_id=hierarchy)
        query_views = dict(self._query_views(query, hierarchy_id=hierarchy))
        trajectory_views: dict[str, dict[int, tuple[ScaleAddress, ...]]] = {}
        trajectory_by_id = {}

        for trajectory in self.trajectories.snapshot():
            if trajectory.hierarchy_id != hierarchy:
                continue
            trajectory_by_id[trajectory.trajectory_id] = trajectory
            trajectory_views[trajectory.trajectory_id] = {
                0: tuple(trajectory.addresses),
            }

        for level in levels:
            for trajectory_id, transformed in level.transformed_trajectories:
                if trajectory_id in trajectory_views:
                    trajectory_views[trajectory_id][level.depth] = transformed

        density_by_address = {
            profile.address: profile
            for profile in self.density.profiles(hierarchy_id=hierarchy)
        }

        matches: list[MultiscaleTrajectoryMatchV2] = []
        for trajectory_id, by_depth in trajectory_views.items():
            atomic_candidate = by_depth.get(0, ())
            atomic_overlap = len(set(query) & set(atomic_candidate))
            if atomic_overlap == 0:
                # A derived scale may reinforce observed atomic convergence but
                # may never create a candidate from zero atomic evidence.
                continue

            evidence_rows: list[ScaleEvidenceV2] = []
            for depth, query_view in query_views.items():
                candidate = by_depth.get(depth)
                if candidate is None or not query_view or not candidate:
                    continue
                overlap = len(set(query_view) & set(candidate))
                if overlap == 0:
                    continue
                evidence_rows.append(
                    ScaleEvidenceV2(
                        depth=depth,
                        query_addresses=query_view,
                        trajectory_addresses=candidate,
                        overlap=overlap,
                        ordered_overlap=self._ordered_overlap(query_view, candidate),
                        adjacency_overlap=self._adjacency_overlap(query_view, candidate),
                        query_coverage_num=overlap,
                        query_coverage_den=len(set(query_view)),
                    )
                )

            if not evidence_rows:
                continue
            trajectory = trajectory_by_id[trajectory_id]
            terminal = trajectory.addresses[-1] if trajectory.addresses else None
            matches.append(
                MultiscaleTrajectoryMatchV2(
                    trajectory_id=trajectory_id,
                    source_id=trajectory.source_id,
                    sequence=trajectory.sequence,
                    scale_evidence=tuple(evidence_rows),
                    supporting_depths=tuple(sorted(row.depth for row in evidence_rows)),
                    terminal_density=(
                        None if terminal is None else density_by_address.get(terminal)
                    ),
                )
            )

        matches.sort(key=lambda item: item.multiscale_key, reverse=True)
        return tuple(matches[:limit])
