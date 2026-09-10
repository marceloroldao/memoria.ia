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


def _shared_suffix_before_terminal(
    left: tuple[str, ...], right: tuple[str, ...]
) -> tuple[str, ...]:
    """Return the maximal contiguous shared suffix excluding the terminal.

    The terminal itself is intentionally excluded so that a globally dense hub
    cannot manufacture a witness merely because many trajectories end there.
    """
    if len(left) < 2 or len(right) < 2 or left[-1] != right[-1]:
        return ()
    left_body = left[:-1]
    right_body = right[:-1]
    size = 0
    max_size = min(len(left_body), len(right_body))
    while size < max_size and left_body[-1 - size] == right_body[-1 - size]:
        size += 1
    if size == 0:
        return ()
    return left_body[-size:]


def discover_witnesses(
    occurrences: Iterable[TrajectoryOccurrence],
    *,
    min_bridge_addresses: int = 2,
) -> tuple[DiscoveredWitness, ...]:
    """Derive convergence witnesses without semantic labels.

    Two occurrences may witness structural convergence only when:
    - their lineages are independent;
    - their terminal address is identical;
    - they share a contiguous bridge immediately before that terminal;
    - the source prefixes before that bridge are both non-empty and distinct.

    Each trajectory pair is one witness. Replaying the same lineage therefore
    cannot multiply epistemic support. No transitive closure is produced.
    """
    if min_bridge_addresses < 1:
        raise ValueError("min_bridge_addresses must be >= 1")

    items = tuple(occurrences)
    found: list[DiscoveredWitness] = []
    seen: set[str] = set()

    for left, right in combinations(items, 2):
        if left.lineage_id == right.lineage_id:
            continue
        la = left.trajectory.addresses
        ra = right.trajectory.addresses
        bridge = _shared_suffix_before_terminal(la, ra)
        if len(bridge) < min_bridge_addresses:
            continue

        left_prefix = la[: -(len(bridge) + 1)]
        right_prefix = ra[: -(len(bridge) + 1)]
        if not left_prefix or not right_prefix or left_prefix == right_prefix:
            continue

        left_sig = structural_signature(left_prefix)
        right_sig = structural_signature(right_prefix)
        terminal = la[-1]
        pair_occurrences = tuple(sorted((left.occurrence_id, right.occurrence_id)))
        witness_id = _digest(
            "witness",
            pair_occurrences + bridge + (terminal,),
        )
        if witness_id in seen:
            continue
        seen.add(witness_id)

        if left_sig <= right_sig:
            witness = DiscoveredWitness(
                witness_id=witness_id,
                left_signature_id=left_sig,
                right_signature_id=right_sig,
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
                left_signature_id=right_sig,
                right_signature_id=left_sig,
                terminal_region_id=terminal,
                bridge_addresses=bridge,
                left_occurrence_id=right.occurrence_id,
                right_occurrence_id=left.occurrence_id,
                left_lineage_id=right.lineage_id,
                right_lineage_id=left.lineage_id,
            )
        found.append(witness)

    found.sort(key=lambda item: item.witness_id)
    return tuple(found)


def events_from_discovered_witnesses(
    witnesses: Iterable[DiscoveredWitness],
) -> tuple[ConvergenceEvent, ...]:
    events: list[ConvergenceEvent] = []
    for sequence, witness in enumerate(witnesses, start=1):
        events.extend(witness.events(sequence=sequence))
    return tuple(sorted(set(events)))
