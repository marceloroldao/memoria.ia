from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence

from .structural_relation_abstraction_v2 import (
    StructuralRelationProfile,
    build_relation_profile,
    compare_structural_relations,
)
from .structural_role_abstraction_v2 import (
    StructuralRoleProfile,
    compare_structural_roles,
)
from .structural_witness_discovery_v2 import TrajectoryOccurrence


@dataclass(frozen=True, slots=True)
class StructuralFutureCandidate:
    candidate_id: str
    role_profile: StructuralRoleProfile
    context_relation: StructuralRelationProfile | None = None
    occurrences: tuple[TrajectoryOccurrence, ...] = ()
    focus_address: str | None = None


@dataclass(frozen=True, slots=True)
class StructuralTransferForecast:
    resolved: bool
    candidate_id: str | None
    source: str
    ambiguous: bool
    competing_candidate_ids: tuple[str, ...] = ()


def _derive_candidate_contexts(
    candidate: StructuralFutureCandidate,
    *,
    relation_width: int,
    min_independent_lineages: int,
) -> tuple[StructuralRelationProfile, ...]:
    """Derive relation contexts immediately preceding a candidate future.

    No semantic labels are used.  A context is simply a contiguous prefix of the
    same width as the held-out relation that occurs immediately before the
    candidate address.  Concrete prefixes are grouped by exact address sequence
    only inside the candidate's own corpus; each group must have independent
    lineage support before it becomes a structural relation profile.
    """
    if relation_width < 1 or not candidate.occurrences or candidate.focus_address is None:
        return ()

    grouped: dict[tuple[str, ...], list[TrajectoryOccurrence]] = {}
    for occurrence in candidate.occurrences:
        addresses = occurrence.trajectory.addresses
        for index, address in enumerate(addresses):
            if address != candidate.focus_address or index < relation_width:
                continue
            prefix = tuple(addresses[index - relation_width:index])
            grouped.setdefault(prefix, []).append(occurrence)

    profiles: list[StructuralRelationProfile] = []
    for prefix, occurrences in sorted(grouped.items()):
        lineages = {occurrence.lineage_id for occurrence in occurrences}
        if len(lineages) < min_independent_lineages:
            continue
        profiles.append(build_relation_profile(tuple(occurrences), prefix))
    return tuple(profiles)


def forecast_structural_future(
    *,
    learned_relation: StructuralRelationProfile,
    heldout_relation: StructuralRelationProfile,
    learned_future_role: StructuralRoleProfile,
    heldout_candidates: Sequence[StructuralFutureCandidate],
    min_independent_lineages: int = 2,
) -> StructuralTransferForecast:
    """Select a held-out future only when structural evidence is uniquely compatible.

    Transfer is conservative and three-stage.  The observed relation must first
    be structurally transferable. Candidate futures must match the learned future
    role. Candidate relational provenance is then either supplied explicitly or
    derived automatically from the candidate's own trajectory occurrences.

    Missing context is treated as missing evidence, never as negative evidence.
    A multi-candidate conflict with unresolved context therefore remains ambiguous.
    No literal cross-corpus address mapping, learned scalar weight, semantic label,
    intent enum or candidate-order tiebreak is used.
    """
    relation_match = compare_structural_relations(
        learned_relation,
        heldout_relation,
        min_independent_lineages=min_independent_lineages,
    )
    if not relation_match.supported:
        return StructuralTransferForecast(False, None, "relation-not-transferable", False)

    role_compatible: list[StructuralFutureCandidate] = []
    context_supported: list[StructuralFutureCandidate] = []
    context_missing = False
    relation_width = len(heldout_relation.focus_addresses)

    for candidate in heldout_candidates:
        role_match = compare_structural_roles(
            learned_future_role,
            candidate.role_profile,
            min_independent_lineages=min_independent_lineages,
        )
        if not role_match.supported:
            continue

        role_compatible.append(candidate)
        contexts: tuple[StructuralRelationProfile, ...]
        if candidate.context_relation is not None:
            contexts = (candidate.context_relation,)
        else:
            contexts = _derive_candidate_contexts(
                candidate,
                relation_width=relation_width,
                min_independent_lineages=min_independent_lineages,
            )

        if not contexts:
            context_missing = True
            continue

        matching_contexts = 0
        for context in contexts:
            context_match = compare_structural_relations(
                context,
                heldout_relation,
                min_independent_lineages=min_independent_lineages,
            )
            if context_match.supported:
                matching_contexts += 1

        # More than one matching derived context is itself ambiguous provenance;
        # do not collapse it into false certainty.
        if matching_contexts == 1:
            context_supported.append(candidate)
        elif matching_contexts == 0:
            continue
        else:
            context_missing = True

    role_ids = tuple(sorted({candidate.candidate_id for candidate in role_compatible}))
    if not role_ids:
        return StructuralTransferForecast(False, None, "no-compatible-future-role", False)

    if len(role_ids) == 1:
        only = role_compatible[0]
        if context_supported:
            return StructuralTransferForecast(
                True,
                only.candidate_id,
                "structural-transfer-context",
                False,
                role_ids,
            )
        if context_missing:
            # Backward-compatible conservative behavior for a unique role match:
            # missing contextual evidence does not negate the direct role evidence.
            return StructuralTransferForecast(True, only.candidate_id, "structural-transfer", False, role_ids)
        return StructuralTransferForecast(False, None, "future-context-mismatch", False)

    if context_missing:
        return StructuralTransferForecast(False, None, "structural-future-conflict", True, role_ids)

    contextual_ids = tuple(sorted({candidate.candidate_id for candidate in context_supported}))
    if not contextual_ids:
        return StructuralTransferForecast(False, None, "no-compatible-future-context", False)
    if len(contextual_ids) > 1:
        return StructuralTransferForecast(
            False,
            None,
            "structural-future-context-conflict",
            True,
            contextual_ids,
        )

    return StructuralTransferForecast(
        True,
        contextual_ids[0],
        "structural-transfer-context",
        False,
        contextual_ids,
    )
