from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, Sequence

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

    The function never maps literal addresses between corpora.  First the observed
    relation itself must transfer structurally.  Then the learned future role is
    compared against already-observed candidate roles in the held-out topology.
    Zero compatible candidates => unresolved. Multiple compatible candidates =>
    ambiguous/fail-closed. Exactly one => structurally forecastable candidate.

    This deliberately transfers a *role constraint*, not a semantic label or an
    unseen concrete address.
    """
    relation_match = compare_structural_relations(
        learned_relation,
        heldout_relation,
        min_independent_lineages=min_independent_lineages,
    )
    if not relation_match.supported:
        return StructuralTransferForecast(False, None, "relation-not-transferable", False)

    compatible: list[str] = []
    for candidate in heldout_candidates:
        match = compare_structural_roles(
            learned_future_role,
            candidate.role_profile,
            min_independent_lineages=min_independent_lineages,
        )
        if match.supported:
            compatible.append(candidate.candidate_id)

    compatible_ids = tuple(sorted(set(compatible)))
    if not compatible_ids:
        return StructuralTransferForecast(False, None, "no-compatible-future-role", False)
    if len(compatible_ids) > 1:
        return StructuralTransferForecast(
            False,
            None,
            "structural-future-conflict",
            True,
            compatible_ids,
        )
    return StructuralTransferForecast(
        True,
        compatible_ids[0],
        "structural-transfer",
        False,
        compatible_ids,
    )
