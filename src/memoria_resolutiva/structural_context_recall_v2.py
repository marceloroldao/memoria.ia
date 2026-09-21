from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

from .structural_context_observation_v2 import (
    StructuralContextHypothesis,
    StructuralContextObservationMemory,
    _canonical_context,
)
from .structural_context_admission_state_v2 import (
    StructuralContextAdmissionStateMemory,
)


@dataclass(frozen=True, slots=True)
class StructuralContextNeighbor:
    consequence_pattern: str
    hypothesis: StructuralContextHypothesis


@dataclass(frozen=True, slots=True)
class StructuralContextRecall:
    antecedent_patterns: tuple[str, str]
    neighbors: tuple[StructuralContextNeighbor, ...]


def recall_structural_context(
    memory: StructuralContextObservationMemory,
    antecedent_patterns: Iterable[str],
    *,
    min_independent_slices: int = 3,
) -> StructuralContextRecall:
    """Recall supported consequences for one exact opaque two-pattern context."""
    if min_independent_slices < 1:
        raise ValueError("min_independent_slices must be >= 1")

    antecedents = tuple(sorted(str(value) for value in antecedent_patterns))
    if len(antecedents) != 2:
        raise ValueError("context recall requires exactly two antecedent patterns")
    # Reuse validation while supplying a temporary distinct consequence.
    probe = "context:probe"
    if probe in antecedents:
        probe = "context:probe:2"
    canonical, _ = _canonical_context(antecedents, probe)

    consequences = sorted(
        {
            item.consequence_pattern
            for item in memory.snapshot()
            if item.antecedent_patterns == canonical
        }
    )

    neighbors: list[StructuralContextNeighbor] = []
    for consequence in consequences:
        hypothesis = memory.resolve(
            canonical,
            consequence,
            min_independent_slices=min_independent_slices,
        )
        if hypothesis is None or not hypothesis.supported:
            continue
        neighbors.append(
            StructuralContextNeighbor(
                consequence_pattern=consequence,
                hypothesis=hypothesis,
            )
        )

    neighbors.sort(key=lambda item: item.consequence_pattern)
    return StructuralContextRecall(
        antecedent_patterns=canonical,
        neighbors=tuple(neighbors),
    )



def recall_active_structural_context(
    memory: StructuralContextObservationMemory,
    admission_state: StructuralContextAdmissionStateMemory,
    antecedent_patterns: Iterable[str],
    *,
    min_independent_slices: int = 3,
) -> StructuralContextRecall:
    """Recall only historically supported consequences still admitted in current state."""
    historical = recall_structural_context(
        memory,
        antecedent_patterns,
        min_independent_slices=min_independent_slices,
    )
    current = admission_state.current(historical.antecedent_patterns)
    if current is None:
        return StructuralContextRecall(
            antecedent_patterns=historical.antecedent_patterns,
            neighbors=(),
        )

    active = set(current.active_candidate_ids)
    neighbors = tuple(
        item
        for item in historical.neighbors
        if active.intersection(item.hypothesis.source_candidate_ids)
    )
    return StructuralContextRecall(
        antecedent_patterns=historical.antecedent_patterns,
        neighbors=neighbors,
    )
