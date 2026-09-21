from __future__ import annotations

from dataclasses import dataclass

from .structural_temporal_observation_v2 import (
    StructuralTemporalHypothesis,
    StructuralTemporalObservationMemory,
)


@dataclass(frozen=True, slots=True)
class StructuralTemporalNeighbor:
    pattern_address: str
    relation_to_query: str
    hypothesis: StructuralTemporalHypothesis


@dataclass(frozen=True, slots=True)
class StructuralTemporalRecall:
    query_pattern: str
    neighbors: tuple[StructuralTemporalNeighbor, ...]


@dataclass(frozen=True, slots=True)
class TemporalWorldCandidate:
    """Concrete temporal continuation candidate supplied by an external world.

    Memoria.ia never creates these candidates. The world/runtime/sensor frontend
    supplies concrete currently possible pattern addresses; memory only intersects
    them with supported passive temporal observations.
    """

    candidate_id: str
    pattern_address: str


@dataclass(frozen=True, slots=True)
class TemporalWorldCandidateMatch:
    candidate: TemporalWorldCandidate
    supporting_neighbors: tuple[StructuralTemporalNeighbor, ...]
    competing_neighbors: tuple[StructuralTemporalNeighbor, ...]

    @property
    def contested(self) -> bool:
        return bool(self.competing_neighbors)


@dataclass(frozen=True, slots=True)
class TemporalWorldCandidateResolution:
    current_pattern: str
    candidates: tuple[TemporalWorldCandidate, ...]
    matches: tuple[TemporalWorldCandidateMatch, ...]
    resolved_candidate: TemporalWorldCandidate | None
    resolved: bool
    ambiguous: bool
    reason: str


def _relative_relation(
    *,
    query_pattern: str,
    pattern_a: str,
    pattern_b: str,
    orientation: str,
) -> str:
    if query_pattern == pattern_a:
        return {
            "a_before_b": "after_query",
            "b_before_a": "before_query",
            "simultaneous": "simultaneous",
        }[orientation]
    if query_pattern == pattern_b:
        return {
            "a_before_b": "before_query",
            "b_before_a": "after_query",
            "simultaneous": "simultaneous",
        }[orientation]
    raise ValueError("query pattern is not part of temporal hypothesis")


def recall_structural_temporal_neighbors(
    memory: StructuralTemporalObservationMemory,
    query_pattern: str,
    *,
    min_independent_slices: int = 3,
) -> StructuralTemporalRecall:
    """Recall supported temporal neighbors without turning them into world futures."""
    query = str(query_pattern)
    if not query:
        raise ValueError("query_pattern must be non-empty")
    if min_independent_slices < 1:
        raise ValueError("min_independent_slices must be >= 1")

    other_patterns = {
        observation.pattern_b if observation.pattern_a == query else observation.pattern_a
        for observation in memory.snapshot()
        if observation.pattern_a == query or observation.pattern_b == query
    }

    neighbors: list[StructuralTemporalNeighbor] = []
    for other in sorted(other_patterns):
        resolution = memory.resolve(
            query,
            other,
            min_independent_slices=min_independent_slices,
        )
        for hypothesis in resolution.hypotheses:
            if not hypothesis.supported:
                continue
            relation = _relative_relation(
                query_pattern=query,
                pattern_a=hypothesis.pattern_a,
                pattern_b=hypothesis.pattern_b,
                orientation=hypothesis.orientation,
            )
            neighbors.append(
                StructuralTemporalNeighbor(
                    pattern_address=other,
                    relation_to_query=relation,
                    hypothesis=hypothesis,
                )
            )

    neighbors.sort(
        key=lambda item: (
            item.pattern_address,
            item.relation_to_query,
            item.hypothesis.orientation,
        )
    )
    return StructuralTemporalRecall(query_pattern=query, neighbors=tuple(neighbors))


def resolve_temporal_world_candidates(
    memory: StructuralTemporalObservationMemory,
    current_pattern: str,
    candidates: tuple[TemporalWorldCandidate, ...],
    *,
    min_independent_slices: int = 3,
) -> TemporalWorldCandidateResolution:
    """Intersect supported temporal recall with concrete world-supplied futures.

    Only an after_query relation can support a future candidate. If the same pair
    also has another independently supported relation (reverse or simultaneous), the
    candidate remains contested. Multiple supported/contested concrete candidates
    preserve ambiguity rather than being ranked by evidence metrics.
    """
    current = str(current_pattern)
    if not current:
        raise ValueError("current_pattern must be non-empty")
    if min_independent_slices < 1:
        raise ValueError("min_independent_slices must be >= 1")

    normalized: list[TemporalWorldCandidate] = []
    seen_ids: set[str] = set()
    for candidate in candidates:
        if not candidate.candidate_id or candidate.candidate_id in seen_ids:
            raise ValueError("candidate_id must be unique and non-empty")
        if not candidate.pattern_address:
            raise ValueError("candidate pattern_address must be non-empty")
        seen_ids.add(candidate.candidate_id)
        normalized.append(candidate)
    normalized.sort(key=lambda item: item.candidate_id)
    visible_candidates = tuple(normalized)

    recall = recall_structural_temporal_neighbors(
        memory,
        current,
        min_independent_slices=min_independent_slices,
    )
    by_pattern: dict[str, list[StructuralTemporalNeighbor]] = {}
    for neighbor in recall.neighbors:
        by_pattern.setdefault(neighbor.pattern_address, []).append(neighbor)

    matches: list[TemporalWorldCandidateMatch] = []
    for candidate in visible_candidates:
        remembered = tuple(by_pattern.get(candidate.pattern_address, ()))
        supporting = tuple(
            item for item in remembered if item.relation_to_query == "after_query"
        )
        if not supporting:
            continue
        competing = tuple(
            item for item in remembered if item.relation_to_query != "after_query"
        )
        matches.append(
            TemporalWorldCandidateMatch(
                candidate=candidate,
                supporting_neighbors=supporting,
                competing_neighbors=competing,
            )
        )

    matches.sort(key=lambda item: item.candidate.candidate_id)
    visible_matches = tuple(matches)
    if not visible_matches:
        return TemporalWorldCandidateResolution(
            current_pattern=current,
            candidates=visible_candidates,
            matches=(),
            resolved_candidate=None,
            resolved=False,
            ambiguous=False,
            reason="no-supported-world-continuation",
        )

    uncontested = tuple(item for item in visible_matches if not item.contested)
    if len(visible_matches) == 1 and len(uncontested) == 1:
        return TemporalWorldCandidateResolution(
            current_pattern=current,
            candidates=visible_candidates,
            matches=visible_matches,
            resolved_candidate=uncontested[0].candidate,
            resolved=True,
            ambiguous=False,
            reason="single-supported-world-continuation",
        )

    return TemporalWorldCandidateResolution(
        current_pattern=current,
        candidates=visible_candidates,
        matches=visible_matches,
        resolved_candidate=None,
        resolved=False,
        ambiguous=True,
        reason=(
            "contested-supported-world-continuation"
            if len(visible_matches) == 1
            else "multiple-supported-world-continuations"
        ),
    )
