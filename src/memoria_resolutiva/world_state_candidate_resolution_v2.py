from __future__ import annotations

from dataclasses import dataclass

from .intervention_consequence_v2 import InterventionConsequenceMemory
from .structural_intervention_transfer_v2 import (
    StructuralConsequencePattern,
    StructuralInterventionResolution,
    _relative_pattern,
    resolve_structural_intervention,
)


@dataclass(frozen=True, slots=True)
class WorldStateCandidate:
    """Concrete consequence candidate supplied by an external world adapter.

    The V2 engine never manufactures these addresses. A simulator, sensor frontend,
    or world-state adapter proposes concrete candidates; the engine only checks
    whether their literal-free geometry matches supported structural experience.
    """

    candidate_id: str
    consequence_addresses: tuple[str, ...]
    next_state_addresses: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class WorldStateCandidateMatch:
    candidate: WorldStateCandidate
    matched_patterns: tuple[StructuralConsequencePattern, ...]


@dataclass(frozen=True, slots=True)
class WorldStateCandidateResolution:
    structural: StructuralInterventionResolution
    matches: tuple[WorldStateCandidateMatch, ...]
    resolved_candidate: WorldStateCandidate | None
    resolved: bool
    ambiguous: bool
    reason: str


def resolve_world_state_candidates(
    memory: InterventionConsequenceMemory,
    state_addresses: tuple[str, ...],
    intervention_address: str,
    candidates: tuple[WorldStateCandidate, ...],
    *,
    min_independent_episodes: int = 2,
) -> WorldStateCandidateResolution:
    """Select only concrete candidates whose geometry is structurally supported.

    Structural transfer constrains what a valid future should look like; the external
    world supplies what concrete futures are currently observable/available. This
    resolver intersects those sets without inventing literals or breaking ambiguity.
    """
    structural = resolve_structural_intervention(
        memory,
        state_addresses,
        intervention_address,
        min_independent_episodes=min_independent_episodes,
    )
    state = InterventionConsequenceMemory._collapse(state_addresses)

    if not structural.patterns:
        return WorldStateCandidateResolution(
            structural=structural,
            matches=(),
            resolved_candidate=None,
            resolved=False,
            ambiguous=False,
            reason="no-supported-structural-pattern",
        )

    matches: list[WorldStateCandidateMatch] = []
    for candidate in candidates:
        if not candidate.candidate_id:
            continue
        consequence = InterventionConsequenceMemory._collapse(candidate.consequence_addresses)
        next_state = InterventionConsequenceMemory._collapse(candidate.next_state_addresses)
        if not consequence or not next_state:
            continue

        consequence_pattern = _relative_pattern(
            state,
            intervention_address,
            consequence,
        )
        next_state_pattern = _relative_pattern(
            state,
            intervention_address,
            next_state,
        )
        matched = tuple(
            pattern
            for pattern in structural.patterns
            if pattern.consequence_pattern == consequence_pattern
            and pattern.next_state_pattern == next_state_pattern
        )
        if matched:
            matches.append(WorldStateCandidateMatch(candidate, matched))

    matches.sort(key=lambda item: item.candidate.candidate_id)
    visible = tuple(matches)
    if not visible:
        return WorldStateCandidateResolution(
            structural=structural,
            matches=(),
            resolved_candidate=None,
            resolved=False,
            ambiguous=False,
            reason="no-compatible-world-candidate",
        )
    if len(visible) > 1:
        return WorldStateCandidateResolution(
            structural=structural,
            matches=visible,
            resolved_candidate=None,
            resolved=False,
            ambiguous=True,
            reason="multiple-compatible-world-candidates",
        )

    return WorldStateCandidateResolution(
        structural=structural,
        matches=visible,
        resolved_candidate=visible[0].candidate,
        resolved=True,
        ambiguous=False,
        reason="single-compatible-world-candidate",
    )
