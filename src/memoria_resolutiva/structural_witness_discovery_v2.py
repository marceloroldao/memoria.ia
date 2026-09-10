from __future__ import annotations

from dataclasses import dataclass
from hashlib import blake2b
from itertools import combinations
from typing import Iterable

from .address_trajectory_v2 import AddressTrajectory
from .structural_equivalence_v2 import ConvergenceEvent


def _digest(kind: str, parts: tuple[str, ...]) -> str:
    payload = (kind + "\x00" + "\x1f".join(parts)).encode("utf-8")
    return "sw2:" + blake2b(payload, digest_size=16).hexdigest()


def structural_signature(addresses: tuple[str, ...]) -> str:
    return _digest("signature", addresses)


@dataclass(frozen=True, slots=True)
class TrajectoryOccurrence:
    trajectory: AddressTrajectory
    lineage_id: str
    occurrence_id: str


@dataclass(frozen=True, slots=True)
class DiscoveredWitness:
    witness_id: str
    left_signature_id: str
    right_signature_id: str
    terminal_region_id: str
    bridge_addresses: tuple[str, ...]
    left_occurrence_id: str
    right_occurrence_id: str
    left_lineage_id: str
    right_lineage_id: str

    def events(self, *, sequence: int = 0) -> tuple[ConvergenceEvent, ConvergenceEvent]:
        return (
            ConvergenceEvent(
                signature_id=self.left_signature_id,
                terminal_region_id=self.terminal_region_id,
                lineage_id=self.left_lineage_id,
                occurrence_id=self.left_occurrence_id,
                witness_id=self.witness_id,
                sequence=sequence,
            ),
            ConvergenceEvent(
                signature_id=self.right_signature_id,
                terminal_region_id=self.terminal_region_id,
                lineage_id=self.right_lineage_id,
                occurrence_id=self.right_occurrence_id,
                witness_id=self.witness_id,
                sequence=sequence,
            ),
        )


def _shared_suffix_before_terminal(left: tuple[str, ...], right: tuple[str, ...]) -> tuple[str, ...]:
    if len(left) < 2 or len(right) < 2 or left[-1] != right[-1]:
        return ()
    left_body = left[:-1]
    right_body = right[:-1]
    size = 0
    max_size = min(len(left_body), len(right_body))
    while size < max_size and left_body[-1 - size] == right_body[-1 - size]:
        size += 1
    return left_body[-size:] if size else ()


def discover_witnesses(
    occurrences: Iterable[TrajectoryOccurrence],
    *,
    min_bridge_addresses: int = 2,
    max_bucket_signatures: int = 32,
    max_witnesses_per_pair: int = 8,
) -> tuple[DiscoveredWitness, ...]:
    """Derive convergence witnesses from topology only.

    Candidate discovery is indexed by the minimal contiguous bridge immediately
    before a common terminal. A bucket with excessive distinct source signatures
    fails closed instead of manufacturing a combinatorial cloud of equivalences.
    """
    if min_bridge_addresses < 1:
        raise ValueError("min_bridge_addresses must be >= 1")
    if max_bucket_signatures < 2:
        raise ValueError("max_bucket_signatures must be >= 2")
    if max_witnesses_per_pair < 1:
        raise ValueError("max_witnesses_per_pair must be >= 1")

    buckets: dict[tuple[tuple[str, ...], str], list[TrajectoryOccurrence]] = {}
    for occurrence in occurrences:
        addresses = occurrence.trajectory.addresses
        if len(addresses) < min_bridge_addresses + 2:
            continue
        bridge = addresses[-(min_bridge_addresses + 1) : -1]
        terminal = addresses[-1]
        buckets.setdefault((bridge, terminal), []).append(occurrence)

    found: list[DiscoveredWitness] = []

    for (minimal_bridge, terminal), bucket in sorted(buckets.items()):
        prepared: list[tuple[TrajectoryOccurrence, tuple[str, ...], str]] = []
        distinct_signatures: set[str] = set()
        for occurrence in bucket:
            addresses = occurrence.trajectory.addresses
            prefix = addresses[: -(min_bridge_addresses + 1)]
            if not prefix:
                continue
            signature_id = structural_signature(prefix)
            distinct_signatures.add(signature_id)
            prepared.append((occurrence, prefix, signature_id))

        if len(distinct_signatures) < 2:
            continue
        if len(distinct_signatures) > max_bucket_signatures:
            # Hyperdense structural bridge: unresolved by design.
            continue

        per_pair_count: dict[tuple[str, str], int] = {}
        for (left, left_prefix, left_sig), (right, right_prefix, right_sig) in combinations(prepared, 2):
            if left.lineage_id == right.lineage_id or left_sig == right_sig:
                continue

            bridge = _shared_suffix_before_terminal(left.trajectory.addresses, right.trajectory.addresses)
            if len(bridge) < min_bridge_addresses:
                continue

            # Recompute source signatures against the maximal shared bridge so
            # witness identity follows the actual observed convergence geometry.
            left_source = left.trajectory.addresses[: -(len(bridge) + 1)]
            right_source = right.trajectory.addresses[: -(len(bridge) + 1)]
            if not left_source or not right_source or left_source == right_source:
                continue
            left_source_sig = structural_signature(left_source)
            right_source_sig = structural_signature(right_source)
            pair = tuple(sorted((left_source_sig, right_source_sig)))
            if per_pair_count.get(pair, 0) >= max_witnesses_per_pair:
                continue

            pair_occurrences = tuple(sorted((left.occurrence_id, right.occurrence_id)))
            witness_id = _digest("witness", pair_occurrences + bridge + (terminal,))

            if left_source_sig <= right_source_sig:
                witness = DiscoveredWitness(
                    witness_id=witness_id,
                    left_signature_id=left_source_sig,
                    right_signature_id=right_source_sig,
                    terminal_region_id=terminal,
                    bridge_addresses=bridge,
                    left_occurrence_id=left.occurrence_id,
                    right_occurrence_id=right.occurrence_id,
                    left_lineage_id=left.lineage_id,
                    right_lineage_id=right.lineage_id,
                )
            else:
                witness = DiscoveredWitness(
                    witness_id=witness_id,
                    left_signature_id=right_source_sig,
                    right_signature_id=left_source_sig,
                    terminal_region_id=terminal,
                    bridge_addresses=bridge,
                    left_occurrence_id=right.occurrence_id,
                    right_occurrence_id=left.occurrence_id,
                    left_lineage_id=right.lineage_id,
                    right_lineage_id=left.lineage_id,
                )
            found.append(witness)
            per_pair_count[pair] = per_pair_count.get(pair, 0) + 1

    found.sort(key=lambda item: item.witness_id)
    return tuple(found)


def events_from_discovered_witnesses(witnesses: Iterable[DiscoveredWitness]) -> tuple[ConvergenceEvent, ...]:
    events: list[ConvergenceEvent] = []
    for sequence, witness in enumerate(witnesses, start=1):
        events.extend(witness.events(sequence=sequence))
    return tuple(sorted(set(events)))
