from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
from typing import Iterable

from .structural_observation import StructuralObservationStore


STRUCTURAL_TRAJECTORY_FORMAT = "memoria.ia-structural-trajectory-v2"


def _collapse_immediate(addresses: Iterable[int]) -> tuple[int, ...]:
    collapsed: list[int] = []
    current: int | None = None
    for raw in addresses:
        address = int(raw)
        if address < 0:
            raise ValueError("structural addresses must be >= 0")
        if current == address:
            continue
        collapsed.append(address)
        current = address
    return tuple(collapsed)


def _stable_id(
    *,
    hierarchy_id: str,
    source_id: str,
    sequence: int,
    observation_id: str | None,
    addresses: tuple[int, ...],
) -> str:
    payload = {
        "format": STRUCTURAL_TRAJECTORY_FORMAT,
        "hierarchy_id": hierarchy_id,
        "source_id": source_id,
        "sequence": int(sequence),
        "observation_id": observation_id,
        "addresses": list(addresses),
    }
    encoded = json.dumps(
        payload,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return "trajectory:" + hashlib.blake2b(encoded, digest_size=20).hexdigest()


@dataclass(frozen=True, slots=True)
class StructuralTrajectory:
    """One immutable occurrence trajectory over opaque structural addresses."""

    trajectory_id: str
    hierarchy_id: str
    source_id: str
    sequence: int
    addresses: tuple[int, ...]
    observation_id: str | None = None


@dataclass(frozen=True, slots=True)
class StructuralTrajectoryMatch:
    trajectory_id: str
    source_id: str
    sequence: int
    overlap: int
    ordered_overlap: int
    adjacency_overlap: int
    query_coverage_num: int
    query_coverage_den: int

    @property
    def structural_key(self) -> tuple[int, int, int, int, int, str]:
        """Lexicographic structural ranking with no learned scalar weights."""
        return (
            self.query_coverage_num,
            -max(1, self.query_coverage_den),
            self.ordered_overlap,
            self.adjacency_overlap,
            self.overlap,
            self.trajectory_id,
        )


@dataclass(frozen=True, slots=True)
class TrajectoryNeighborCandidate:
    address: int
    supporting_trajectory_ids: tuple[str, ...]
    occurrence_count: int


@dataclass(frozen=True, slots=True)
class TrajectoryFrontierResolution:
    direction: str
    query_addresses: tuple[int, ...]
    candidates: tuple[TrajectoryNeighborCandidate, ...]
    resolved_address: int | None
    resolved: bool
    ambiguous: bool
    reason: str


class StructuralTrajectoryIndex:
    """Read-mostly trajectory substrate recovered from the historical V2 lab.

    The index consumes the opaque symbols already produced by the current V2
    StructuralObservation pipeline. It does not tokenize language, create
    predicates, assign semantic labels, or learn scalar ranking weights.

    A trajectory is an occurrence. Resolution never stitches two occurrences
    together through a globally shared address. Queries are read-only.
    """

    def __init__(self) -> None:
        self._trajectories: list[StructuralTrajectory] = []
        self._by_id: dict[str, StructuralTrajectory] = {}

    @property
    def count(self) -> int:
        return len(self._trajectories)

    def snapshot(self) -> tuple[StructuralTrajectory, ...]:
        return tuple(self._trajectories)

    def ingest_addresses(
        self,
        addresses: Iterable[int],
        *,
        hierarchy_id: str,
        source_id: str,
        sequence: int,
        observation_id: str | None = None,
    ) -> StructuralTrajectory:
        hierarchy = str(hierarchy_id).strip()
        source = str(source_id).strip()
        if not hierarchy:
            raise ValueError("hierarchy_id must be non-empty")
        if not source:
            raise ValueError("source_id must be non-empty")
        if int(sequence) < 0:
            raise ValueError("sequence must be >= 0")
        collapsed = _collapse_immediate(addresses)
        if not collapsed:
            raise ValueError("trajectory must contain at least one structural address")

        trajectory_id = _stable_id(
            hierarchy_id=hierarchy,
            source_id=source,
            sequence=int(sequence),
            observation_id=None if observation_id is None else str(observation_id),
            addresses=collapsed,
        )
        candidate = StructuralTrajectory(
            trajectory_id=trajectory_id,
            hierarchy_id=hierarchy,
            source_id=source,
            sequence=int(sequence),
            addresses=collapsed,
            observation_id=None if observation_id is None else str(observation_id),
        )
        existing = self._by_id.get(trajectory_id)
        if existing is not None:
            if existing != candidate:
                raise ValueError("structural trajectory id collision")
            return existing

        self._trajectories.append(candidate)
        self._by_id[trajectory_id] = candidate
        return candidate

    def sync_observations(self, store: StructuralObservationStore) -> int:
        """Import canonical raw observations as immutable occurrence trajectories.

        Replaying the same StructuralObservationStore is idempotent because
        trajectory identity includes the source occurrence and its collapsed trail.
        """
        added = 0
        for envelope in store.ordered_from(0):
            event = envelope.get("event")
            provenance = envelope.get("provenance")
            if not isinstance(event, dict):
                raise ValueError("structural observation event must be an object")
            if not isinstance(provenance, dict):
                raise ValueError("structural observation provenance must be an object")
            hierarchy_id = str(provenance.get("hierarchy_id") or "").strip()
            if not hierarchy_id:
                raise ValueError("structural observation requires provenance.hierarchy_id")
            before = self.count
            self.ingest_addresses(
                event.get("trail", ()),
                hierarchy_id=hierarchy_id,
                source_id=str(event.get("source_id") or ""),
                sequence=int(event.get("sequence", -1)),
                observation_id=str(envelope.get("observation_id") or ""),
            )
            if self.count > before:
                added += 1
        return added

    @staticmethod
    def _ordered_overlap(query: tuple[int, ...], candidate: tuple[int, ...]) -> int:
        if not query or not candidate:
            return 0
        cursor = 0
        matched = 0
        for address in candidate:
            if cursor < len(query) and address == query[cursor]:
                matched += 1
                cursor += 1
        return matched

    @staticmethod
    def _adjacency_overlap(query: tuple[int, ...], candidate: tuple[int, ...]) -> int:
        if len(query) < 2 or len(candidate) < 2:
            return 0
        query_pairs = set(zip(query, query[1:]))
        return sum(1 for pair in zip(candidate, candidate[1:]) if pair in query_pairs)

    def resolve_addresses(
        self,
        addresses: Iterable[int],
        *,
        hierarchy_id: str,
        limit: int = 8,
    ) -> tuple[StructuralTrajectoryMatch, ...]:
        """Rank stored occurrences by structural geometry only.

        The method is deliberately read-only. Repeating a query cannot create,
        reinforce or mutate a trajectory.
        """
        hierarchy = str(hierarchy_id).strip()
        if not hierarchy:
            raise ValueError("hierarchy_id must be non-empty")
        if limit < 1:
            raise ValueError("limit must be >= 1")
        query = _collapse_immediate(addresses)
        if not query:
            raise ValueError("query must contain at least one structural address")

        query_set = set(query)
        matches: list[StructuralTrajectoryMatch] = []
        for trajectory in self._trajectories:
            if trajectory.hierarchy_id != hierarchy:
                continue
            candidate_set = set(trajectory.addresses)
            overlap = len(query_set & candidate_set)
            if overlap == 0:
                continue
            matches.append(
                StructuralTrajectoryMatch(
                    trajectory_id=trajectory.trajectory_id,
                    source_id=trajectory.source_id,
                    sequence=trajectory.sequence,
                    overlap=overlap,
                    ordered_overlap=self._ordered_overlap(query, trajectory.addresses),
                    adjacency_overlap=self._adjacency_overlap(query, trajectory.addresses),
                    query_coverage_num=overlap,
                    query_coverage_den=len(query_set),
                )
            )
        matches.sort(key=lambda item: item.structural_key, reverse=True)
        return tuple(matches[:limit])

    @staticmethod
    def _contiguous_starts(
        query: tuple[int, ...],
        candidate: tuple[int, ...],
    ) -> tuple[int, ...]:
        if not query or len(query) > len(candidate):
            return ()
        width = len(query)
        return tuple(
            start
            for start in range(len(candidate) - width + 1)
            if candidate[start : start + width] == query
        )

    def frontier(
        self,
        addresses: Iterable[int],
        *,
        hierarchy_id: str,
        direction: str = "forward",
    ) -> TrajectoryFrontierResolution:
        """Resolve the immediate structural neighbor of an exact occurrence.

        Forward/reverse traversal is occurrence-local. If different stored
        occurrences expose different continuations they remain competing
        candidates; this layer does not collapse them by recency or frequency.
        """
        hierarchy = str(hierarchy_id).strip()
        if not hierarchy:
            raise ValueError("hierarchy_id must be non-empty")
        if direction not in {"forward", "reverse"}:
            raise ValueError("direction must be 'forward' or 'reverse'")
        query = _collapse_immediate(addresses)
        if not query:
            raise ValueError("query must contain at least one structural address")

        support: dict[int, list[str]] = {}
        for trajectory in self._trajectories:
            if trajectory.hierarchy_id != hierarchy:
                continue
            for start in self._contiguous_starts(query, trajectory.addresses):
                if direction == "forward":
                    neighbor_index = start + len(query)
                    if neighbor_index >= len(trajectory.addresses):
                        continue
                else:
                    neighbor_index = start - 1
                    if neighbor_index < 0:
                        continue
                neighbor = trajectory.addresses[neighbor_index]
                support.setdefault(neighbor, []).append(trajectory.trajectory_id)

        candidates = tuple(
            TrajectoryNeighborCandidate(
                address=address,
                supporting_trajectory_ids=tuple(sorted(ids)),
                occurrence_count=len(ids),
            )
            for address, ids in sorted(support.items(), key=lambda item: item[0])
        )
        if not candidates:
            return TrajectoryFrontierResolution(
                direction=direction,
                query_addresses=query,
                candidates=(),
                resolved_address=None,
                resolved=False,
                ambiguous=False,
                reason="no-structural-neighbor",
            )
        if len(candidates) == 1:
            return TrajectoryFrontierResolution(
                direction=direction,
                query_addresses=query,
                candidates=candidates,
                resolved_address=candidates[0].address,
                resolved=True,
                ambiguous=False,
                reason="single-structural-neighbor",
            )
        return TrajectoryFrontierResolution(
            direction=direction,
            query_addresses=query,
            candidates=candidates,
            resolved_address=None,
            resolved=False,
            ambiguous=True,
            reason="competing-structural-neighbors",
        )
