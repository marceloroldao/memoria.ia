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

    The role fingerprint deliberately excludes concrete predecessor/successor
    identities. It preserves only local path geometry: distance from trajectory
    start/end plus predecessor/successor diversity. Hyperdense neighborhoods are
    marked non-discriminative and therefore fail closed.
    """
    if max_neighbor_diversity < 1:
        raise ValueError("max_neighbor_diversity must be >= 1")

    shapes: set[tuple[int, int]] = set()
    predecessors: set[str] = set()
    successors: set[str] = set()
    lineages: set[str] = set()
    count = 0

    for occurrence in occurrences:
        addresses = occurrence.trajectory.addresses
        for index, address in enumerate(addresses):
            if address != focus_address:
                continue
            count += 1
            lineages.add(occurrence.lineage_id)
            shapes.add((index, len(addresses) - index - 1))
            if index > 0:
                predecessors.add(addresses[index - 1])
            if index + 1 < len(addresses):
                successors.add(addresses[index + 1])

    local_shapes = tuple(sorted(shapes))
    pred_div = len(predecessors)
    succ_div = len(successors)
    discriminative = bool(local_shapes) and pred_div <= max_neighbor_diversity and succ_div <= max_neighbor_diversity
    role_id = _digest(
        tuple(f"{left}:{right}" for left, right in local_shapes)
        + (f"pred:{pred_div}", f"succ:{succ_div}")
    )
    return StructuralRoleProfile(
        focus_address=focus_address,
        role_id=role_id,
        local_shapes=local_shapes,
        predecessor_diversity=pred_div,
        successor_diversity=succ_div,
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
    """Conservative exact-role comparison for the first transfer experiment."""
    if min_independent_lineages < 1:
        raise ValueError("min_independent_lineages must be >= 1")
    if not left.discriminative or not right.discriminative:
        return StructuralRoleMatch(False, left.role_id, right.role_id, "non-discriminative")
    if left.independent_lineages < min_independent_lineages or right.independent_lineages < min_independent_lineages:
        return StructuralRoleMatch(False, left.role_id, right.role_id, "insufficient-independent-support")
    if left.role_id != right.role_id:
        return StructuralRoleMatch(False, left.role_id, right.role_id, "topology-mismatch")
    return StructuralRoleMatch(True, left.role_id, right.role_id, "exact-topological-role")
