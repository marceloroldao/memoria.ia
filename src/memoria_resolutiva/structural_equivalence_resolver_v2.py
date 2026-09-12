from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping, Sequence

from .structural_equivalence_v2 import StructuralEquivalenceCandidate, StructuralEquivalenceState


TerminalValue = str | Sequence[str]


@dataclass(frozen=True)
class EquivalenceResolution:
    resolved: bool
    terminal_region_id: str | None
    source: str
    ambiguous: bool
    equivalent_signature_ids: tuple[str, ...] = ()
    supporting_witnesses: tuple[str, ...] = ()
    competing_terminal_region_ids: tuple[str, ...] = ()


def _normalize_terminals(value: TerminalValue | None) -> tuple[str, ...]:
    if value is None:
        return ()
    if isinstance(value, str):
        return (value,) if value else ()
    return tuple(sorted({item for item in value if item}))


def resolve_via_structural_equivalence(
    *,
    query_signature_id: str,
    equivalence_state: StructuralEquivalenceState,
    signature_terminals: Mapping[str, TerminalValue],
    known_signature_ids: Sequence[str],
    direct_terminal_region_id: str | None = None,
) -> EquivalenceResolution:
    """Experimental opt-in bridge for an otherwise unresolved signature.

    Precedence is deliberately conservative:
    1. direct evidence wins immediately;
    2. only `supported` equivalence candidates are considered;
    3. every structurally retained future remains visible;
    4. resolution occurs only when all supported routes collapse to one region;
    5. multiple futures fail closed as explicit ambiguity.

    The function is query-read-only and is not wired into the default resolver.
    """
    if direct_terminal_region_id is not None:
        return EquivalenceResolution(
            resolved=True,
            terminal_region_id=direct_terminal_region_id,
            source="direct",
            ambiguous=False,
        )

    routes: list[tuple[str, tuple[str, ...], StructuralEquivalenceCandidate]] = []
    for candidate_signature_id in sorted(set(known_signature_ids)):
        if candidate_signature_id == query_signature_id:
            continue
        terminals = _normalize_terminals(signature_terminals.get(candidate_signature_id))
        if not terminals:
            continue
        candidate = equivalence_state.evaluate(query_signature_id, candidate_signature_id)
        if candidate.state != "supported":
            continue
        routes.append((candidate_signature_id, terminals, candidate))

    if not routes:
        return EquivalenceResolution(False, None, "unresolved", False)

    terminal_set = {terminal for _, terminals, _ in routes for terminal in terminals}
    equivalent_ids = tuple(route[0] for route in routes)
    witnesses = tuple(sorted({w for _, _, candidate in routes for w in candidate.supporting_witnesses}))

    if len(terminal_set) != 1:
        return EquivalenceResolution(
            resolved=False,
            terminal_region_id=None,
            source="equivalence-conflict",
            ambiguous=True,
            equivalent_signature_ids=equivalent_ids,
            supporting_witnesses=witnesses,
            competing_terminal_region_ids=tuple(sorted(terminal_set)),
        )

    terminal = next(iter(terminal_set))
    return EquivalenceResolution(
        resolved=True,
        terminal_region_id=terminal,
        source="structural-equivalence",
        ambiguous=False,
        equivalent_signature_ids=equivalent_ids,
        supporting_witnesses=witnesses,
        competing_terminal_region_ids=(terminal,),
    )
