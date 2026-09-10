from __future__ import annotations

from dataclasses import dataclass
from hashlib import blake2b
from typing import Iterable, Sequence

from .structural_role_abstraction_v2 import build_role_profile
from .structural_witness_discovery_v2 import TrajectoryOccurrence


def _digest(parts: tuple[str, ...]) -> str:
    payload = ("memoria.structural-relation.v2\x00" + "\x1f".join(parts)).encode("utf-8")
    return "srel2:" + blake2b(payload, digest_size=16).hexdigest()


@dataclass(frozen=True, slots=True)
class StructuralRelationProfile:
    focus_addresses: tuple[str, ...]
    relation_id: str
    role_ids: tuple[str, ...]
    independent_lineages: int
    supporting_occurrences: int
    continuation_diversity_by_depth: tuple[int, ...]
    discriminative: bool


@dataclass(frozen=True, slots=True)
class StructuralRelationMatch:
    supported: bool
    left_relation_id: str
    right_relation_id: str
    reason: str


def _find_contiguous(addresses: Sequence[str], needle: Sequence[str]) -> int | None:
    if not needle or len(needle) > len(addresses):
        return None
    width = len(needle)
    for index in range(len(addresses) - width + 1):
        if tuple(addresses[index:index + width]) == tuple(needle):
            return index
    return None


def build_relation_profile(
    occurrences: Iterable[TrajectoryOccurrence],
    focus_addresses: Sequence[str],
    *,
    max_continuation_depth: int = 3,
    max_neighbor_diversity: int = 32,
) -> StructuralRelationProfile:
    """Describe an ordered multi-address relation using only observed topology.

    Literal address identities are used only to locate the concrete relation inside
    one corpus. They are not part of the resulting relation fingerprint. The
    fingerprint combines the ordered structural-role sequence with an anonymous
    continuation branching regime after the relation. This blocks transfer between
    locally similar motifs whose future topology differs.
    """
    focus = tuple(focus_addresses)
    if not focus:
        raise ValueError("focus_addresses must not be empty")
    if max_continuation_depth < 0:
        raise ValueError("max_continuation_depth must be >= 0")

    occurrence_list = tuple(occurrences)
    role_profiles = tuple(
        build_role_profile(occurrence_list, address, max_neighbor_diversity=max_neighbor_diversity)
        for address in focus
    )

    lineages: set[str] = set()
    supporting_occurrences = 0
    continuation_by_depth: list[set[str]] = [set() for _ in range(max_continuation_depth)]

    for occurrence in occurrence_list:
        addresses = occurrence.trajectory.addresses
        start = _find_contiguous(addresses, focus)
        if start is None:
            continue
        supporting_occurrences += 1
        lineages.add(occurrence.lineage_id)
        after = start + len(focus)
        for depth in range(max_continuation_depth):
            pos = after + depth
            if pos < len(addresses):
                continuation_by_depth[depth].add(addresses[pos])

    continuation_diversity = tuple(len(values) for values in continuation_by_depth)
    discriminative = (
        supporting_occurrences > 0
        and all(profile.discriminative for profile in role_profiles)
        and all(value <= max_neighbor_diversity for value in continuation_diversity)
    )

    role_ids = tuple(profile.role_id for profile in role_profiles)
    relation_id = _digest(
        tuple(f"role:{role_id}" for role_id in role_ids)
        + tuple(f"future-div:{depth}:{value}" for depth, value in enumerate(continuation_diversity))
    )
    return StructuralRelationProfile(
        focus_addresses=focus,
        relation_id=relation_id,
        role_ids=role_ids,
        independent_lineages=len(lineages),
        supporting_occurrences=supporting_occurrences,
        continuation_diversity_by_depth=continuation_diversity,
        discriminative=discriminative,
    )


def compare_structural_relations(
    left: StructuralRelationProfile,
    right: StructuralRelationProfile,
    *,
    min_independent_lineages: int = 2,
) -> StructuralRelationMatch:
    if min_independent_lineages < 1:
        raise ValueError("min_independent_lineages must be >= 1")
    if not left.discriminative or not right.discriminative:
        return StructuralRelationMatch(False, left.relation_id, right.relation_id, "non-discriminative")
    if left.independent_lineages < min_independent_lineages or right.independent_lineages < min_independent_lineages:
        return StructuralRelationMatch(False, left.relation_id, right.relation_id, "insufficient-independent-support")
    if left.relation_id != right.relation_id:
        return StructuralRelationMatch(False, left.relation_id, right.relation_id, "relation-topology-mismatch")
    return StructuralRelationMatch(True, left.relation_id, right.relation_id, "exact-structural-relation")
