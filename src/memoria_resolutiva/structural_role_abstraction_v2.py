from __future__ import annotations

from dataclasses import dataclass
from hashlib import blake2b
from typing import Iterable

from .structural_witness_discovery_v2 import TrajectoryOccurrence


def _digest(parts: tuple[str, ...]) -> str:
    payload = ("memoria.structural-role.v2\x00" + "\x1f".join(parts)).encode("utf-8")
    return "sr2:" + blake2b(payload, digest_size=16).hexdigest()


@dataclass(frozen=True, slots=True)
class StructuralRoleProfile:
    focus_address: str
    role_id: str
    local_shapes: tuple[tuple[int, int], ...]
    predecessor_diversity: int
    successor_diversity: int
    predecessor_degree_spectrum: tuple[int, ...]
    successor_degree_spectrum: tuple[int, ...]
    incidence_support_spectrum: tuple[int, ...]
    independent_lineages: int
    occurrence_count: int
    discriminative: bool


@dataclass(frozen=True, slots=True)
class StructuralRoleMatch:
    supported: bool
    left_role_id: str
    right_role_id: str
    reason: str


def build_role_profile(
    occurrences: Iterable[TrajectoryOccurrence],
    focus_address: str,
    *,
    max_neighbor_diversity: int = 32,
) -> StructuralRoleProfile:
    """Describe an address by observed trajectory topology, never by its label.

    Concrete predecessor/successor identities are discarded.  The fingerprint
    preserves only structural invariants: local position, neighbor diversity,
    anonymous predecessor/successor degree spectra and the independent-lineage
    support spectrum of predecessor->focus->successor incidence pairs.

    This makes disjoint address spaces comparable while preventing two local
    neighborhoods with equal counts but different coupling geometry from being
    treated as the same role.  Hyperdense neighborhoods fail closed.
    """
    if max_neighbor_diversity < 1:
        raise ValueError("max_neighbor_diversity must be >= 1")

    shapes: set[tuple[int, int]] = set()
    predecessors: set[str] = set()
    successors: set[str] = set()
    lineages: set[str] = set()
    pred_successors: dict[str, set[str]] = {}
    succ_predecessors: dict[str, set[str]] = {}
    incidence_lineages: dict[tuple[str, str], set[str]] = {}
    count = 0

    for occurrence in occurrences:
        addresses = occurrence.trajectory.addresses
        for index, address in enumerate(addresses):
            if address != focus_address:
                continue
            count += 1
            lineages.add(occurrence.lineage_id)
            shapes.add((index, len(addresses) - index - 1))
            predecessor = addresses[index - 1] if index > 0 else "<START>"
            successor = addresses[index + 1] if index + 1 < len(addresses) else "<END>"
            predecessors.add(predecessor)
            successors.add(successor)
            pred_successors.setdefault(predecessor, set()).add(successor)
            succ_predecessors.setdefault(successor, set()).add(predecessor)
            incidence_lineages.setdefault((predecessor, successor), set()).add(occurrence.lineage_id)

    local_shapes = tuple(sorted(shapes))
    pred_div = len(predecessors)
    succ_div = len(successors)
    pred_spectrum = tuple(sorted(len(values) for values in pred_successors.values()))
    succ_spectrum = tuple(sorted(len(values) for values in succ_predecessors.values()))
    incidence_spectrum = tuple(sorted(len(values) for values in incidence_lineages.values()))
    discriminative = (
        bool(local_shapes)
        and pred_div <= max_neighbor_diversity
        and succ_div <= max_neighbor_diversity
    )
    role_id = _digest(
        tuple(f"shape:{left}:{right}" for left, right in local_shapes)
        + (f"pred-div:{pred_div}", f"succ-div:{succ_div}")
        + tuple(f"pred-degree:{value}" for value in pred_spectrum)
        + tuple(f"succ-degree:{value}" for value in succ_spectrum)
        + tuple(f"incidence-support:{value}" for value in incidence_spectrum)
    )
    return StructuralRoleProfile(
        focus_address=focus_address,
        role_id=role_id,
        local_shapes=local_shapes,
        predecessor_diversity=pred_div,
        successor_diversity=succ_div,
        predecessor_degree_spectrum=pred_spectrum,
        successor_degree_spectrum=succ_spectrum,
        incidence_support_spectrum=incidence_spectrum,
        independent_lineages=len(lineages),
        occurrence_count=count,
        discriminative=discriminative,
    )


def compare_structural_roles(
    left: StructuralRoleProfile,
    right: StructuralRoleProfile,
    *,
    min_independent_lineages: int = 2,
) -> StructuralRoleMatch:
    """Conservative exact-role comparison for the transfer experiment."""
    if min_independent_lineages < 1:
        raise ValueError("min_independent_lineages must be >= 1")
    if not left.discriminative or not right.discriminative:
        return StructuralRoleMatch(False, left.role_id, right.role_id, "non-discriminative")
    if left.independent_lineages < min_independent_lineages or right.independent_lineages < min_independent_lineages:
        return StructuralRoleMatch(False, left.role_id, right.role_id, "insufficient-independent-support")
    if left.role_id != right.role_id:
        return StructuralRoleMatch(False, left.role_id, right.role_id, "topology-mismatch")
    return StructuralRoleMatch(True, left.role_id, right.role_id, "exact-topological-role")
