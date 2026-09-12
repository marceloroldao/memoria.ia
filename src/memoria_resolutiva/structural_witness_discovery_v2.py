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


def discover_witnesses(
    occurrences: Iterable[TrajectoryOccurrence],
    *,
    min_bridge_addresses: int = 2,
    max_bucket_signatures: int = 32,
    max_witnesses_per_pair: int = 8,
) -> tuple[DiscoveredWitness, ...]:
    """Derive bounded structural witnesses from observed trajectory convergence.

    The index key is the minimal contiguous bridge immediately before a common
    terminal. Shared terminal alone never qualifies. Hyperdense bridge buckets
    fail closed. Repetition inside a valid bucket is grouped by source signature,
    so generating witnesses does not require a quadratic scan over occurrences.
    """
    if min_bridge_addresses < 1:
        raise ValueError("min_bridge_addresses must be >= 1")
    if max_bucket_signatures < 2:
        raise ValueError("max_bucket_signatures must be >= 2")
    if max_witnesses_per_pair < 1:
        raise ValueError("max_witnesses_per_pair must be >= 1")

    # (bridge, terminal) -> source_signature -> independent occurrences
    buckets: dict[
        tuple[tuple[str, ...], str],
        dict[str, list[TrajectoryOccurrence]],
    ] = {}

    for occurrence in occurrences:
        addresses = occurrence.trajectory.addresses
        if len(addresses) < min_bridge_addresses + 2:
            continue
        bridge = addresses[-(min_bridge_addresses + 1) : -1]
        terminal = addresses[-1]
        prefix = addresses[: -(min_bridge_addresses + 1)]
        if not prefix:
            continue
        signature_id = structural_signature(prefix)
        by_signature = buckets.setdefault((bridge, terminal), {})
        by_signature.setdefault(signature_id, []).append(occurrence)

    found: list[DiscoveredWitness] = []

    for (bridge, terminal), by_signature in sorted(buckets.items()):
        signature_ids = tuple(sorted(by_signature))
        if len(signature_ids) < 2:
            continue
        if len(signature_ids) > max_bucket_signatures:
            # Too many distinct origins converge through the same local bridge:
            # this region is structurally hyperdense, so equivalence is withheld.
            continue

        for left_sig, right_sig in combinations(signature_ids, 2):
            left_occurrences = sorted(
                by_signature[left_sig],
                key=lambda item: (item.lineage_id, item.occurrence_id),
            )
            right_occurrences = sorted(
                by_signature[right_sig],
                key=lambda item: (item.lineage_id, item.occurrence_id),
            )

            emitted = 0
            used_left_lineages: set[str] = set()
            used_right_lineages: set[str] = set()
            for left in left_occurrences:
                if emitted >= max_witnesses_per_pair:
                    break
                if left.lineage_id in used_left_lineages:
                    continue
                match = next(
                    (
                        right
                        for right in right_occurrences
                        if right.lineage_id != left.lineage_id
                        and right.lineage_id not in used_right_lineages
                    ),
                    None,
                )
                if match is None:
                    continue

                pair_occurrences = tuple(sorted((left.occurrence_id, match.occurrence_id)))
                witness_id = _digest("witness", pair_occurrences + bridge + (terminal,))
                found.append(
                    DiscoveredWitness(
                        witness_id=witness_id,
                        left_signature_id=left_sig,
                        right_signature_id=right_sig,
                        terminal_region_id=terminal,
                        bridge_addresses=bridge,
                        left_occurrence_id=left.occurrence_id,
                        right_occurrence_id=match.occurrence_id,
                        left_lineage_id=left.lineage_id,
                        right_lineage_id=match.lineage_id,
                    )
                )
                used_left_lineages.add(left.lineage_id)
                used_right_lineages.add(match.lineage_id)
                emitted += 1

    found.sort(key=lambda item: item.witness_id)
    return tuple(found)


def events_from_discovered_witnesses(witnesses: Iterable[DiscoveredWitness]) -> tuple[ConvergenceEvent, ...]:
    events: list[ConvergenceEvent] = []
    for sequence, witness in enumerate(witnesses, start=1):
        events.extend(witness.events(sequence=sequence))
    return tuple(sorted(set(events)))
