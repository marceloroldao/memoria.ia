from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping, Sequence

from .structural_equivalence_v2 import StructuralEquivalenceCandidate, StructuralEquivalenceState


@dataclass(frozen=True)
class EquivalenceResolution:
    resolved: bool
    terminal_region_id: str | None
    source: str
    ambiguous: bool
    equivalent_signature_ids: tuple[str, ...] = ()
    supporting_witnesses: tuple[str, ...] = ()


def resolve_via_structural_equivalence(
    *,
    query_signature_id: str,
    equivalence_state: StructuralEquivalenceState,
    signature_terminals: Mapping[str, str],
    known_signature_ids: Sequence[str],
    direct_terminal_region_id: str | None = None,
) -> EquivalenceResolution:
    """Experimental opt-in bridge for an otherwise unresolved signature.

    Precedence is deliberately lexicographic and conservative:
    1. direct evidence wins immediately;
    2. only `supported` equivalence candidates are considered;
    3. supported routes must converge to one terminal region;
    4. conflicting terminal regions fail closed.

    This function is read-only and is not wired into the default resolver.
    """
    if direct_terminal_region_id is not None:
        return EquivalenceResolution(
            resolved=True,
            terminal_region_id=direct_terminal_region_id,
            source="direct",
            ambiguous=False,
        )

    routes: list[tuple[str, str, StructuralEquivalenceCandidate]] = []
    for candidate_signature_id in sorted(set(known_signature_ids)):
        if candidate_signature_id == query_signature_id:
            continue
        terminal = signature_terminals.get(candidate_signature_id)
        if terminal is None:
            continue
        candidate = equivalence_state.evaluate(query_signature_id, candidate_signature_id)
        if candidate.state != "supported":
            continue
        routes.append((candidate_signature_id, terminal, candidate))

    if not routes:
        return EquivalenceResolution(False, None, "unresolved", False)

    terminals = {terminal for _, terminal, _ in routes}
    if len(terminals) != 1:
        return EquivalenceResolution(
            resolved=False,
            terminal_region_id=None,
            source="equivalence-conflict",
            ambiguous=True,
            equivalent_signature_ids=tuple(route[0] for route in routes),
            supporting_witnesses=tuple(sorted({w for _, _, c in routes for w in c.supporting_witnesses})),
        )

    terminal = next(iter(terminals))
    return EquivalenceResolution(
        resolved=True,
        terminal_region_id=terminal,
        source="structural-equivalence",
        ambiguous=False,
        equivalent_signature_ids=tuple(route[0] for route in routes),
        supporting_witnesses=tuple(sorted({w for _, _, c in routes for w in c.supporting_witnesses})),
    )
