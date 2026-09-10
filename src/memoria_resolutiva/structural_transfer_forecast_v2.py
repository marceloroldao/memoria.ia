from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence

from .structural_relation_abstraction_v2 import (
    StructuralRelationProfile,
    compare_structural_relations,
)
from .structural_role_abstraction_v2 import (
    StructuralRoleProfile,
    compare_structural_roles,
)


@dataclass(frozen=True, slots=True)
class StructuralFutureCandidate:
    candidate_id: str
    role_profile: StructuralRoleProfile
    context_relation: StructuralRelationProfile | None = None


@dataclass(frozen=True, slots=True)
class StructuralTransferForecast:
    resolved: bool
    candidate_id: str | None
    source: str
    ambiguous: bool
    competing_candidate_ids: tuple[str, ...] = ()


def forecast_structural_future(
    *,
    learned_relation: StructuralRelationProfile,
    heldout_relation: StructuralRelationProfile,
    learned_future_role: StructuralRoleProfile,
    heldout_candidates: Sequence[StructuralFutureCandidate],
    min_independent_lineages: int = 2,
) -> StructuralTransferForecast:
    """Select a held-out future only when structural evidence is uniquely compatible.

    Transfer is conservative and two-stage.  The observed relation must first be
    structurally transferable.  Candidate futures must then match the learned
    future role.  When relational provenance is supplied for a candidate, that
    context must also match the held-out relation; a local-role lookalike in a
    different relation is not allowed to win.

    Missing context is treated as missing evidence, never as negative evidence.
    Therefore a multi-candidate conflict containing context-free candidates remains
    ambiguous rather than silently discarding them.  No literal address mapping,
    learned scalar weight, semantic label or candidate-order tiebreak is used.
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

    for candidate in heldout_candidates:
        role_match = compare_structural_roles(
            learned_future_role,
            candidate.role_profile,
            min_independent_lineages=min_independent_lineages,
        )
        if not role_match.supported:
            continue

        role_compatible.append(candidate)
        if candidate.context_relation is None:
            context_missing = True
            continue

        context_match = compare_structural_relations(
            candidate.context_relation,
            heldout_relation,
            min_independent_lineages=min_independent_lineages,
        )
        if context_match.supported:
            context_supported.append(candidate)

    role_ids = tuple(sorted({candidate.candidate_id for candidate in role_compatible}))
    if not role_ids:
        return StructuralTransferForecast(False, None, "no-compatible-future-role", False)

    # A unique role match remains valid when no contrary contextual evidence exists.
    if len(role_ids) == 1:
        only = role_compatible[0]
        if only.context_relation is None:
            return StructuralTransferForecast(True, only.candidate_id, "structural-transfer", False, role_ids)
        if context_supported:
            return StructuralTransferForecast(
                True,
                only.candidate_id,
                "structural-transfer-context",
                False,
                role_ids,
            )
        return StructuralTransferForecast(False, None, "future-context-mismatch", False)

    # Missing context cannot be used to eliminate a candidate. Fail closed.
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
