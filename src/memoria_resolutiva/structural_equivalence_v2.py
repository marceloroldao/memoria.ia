from __future__ import annotations

from dataclasses import dataclass, field
from typing import Iterable


@dataclass(frozen=True, order=True)
class ConvergenceEvent:
    signature_id: str
    terminal_region_id: str
    lineage_id: str
    occurrence_id: str
    witness_id: str
    sequence: int


@dataclass(frozen=True)
class StructuralEquivalenceCandidate:
    left_signature_id: str
    right_signature_id: str
    shared_terminal_regions: tuple[str, ...]
    supporting_witnesses: tuple[str, ...]
    contradicting_witnesses: tuple[str, ...]
    state: str

    @property
    def independent_convergence(self) -> int:
        return len(self.supporting_witnesses)

    @property
    def independent_divergence(self) -> int:
        return len(self.contradicting_witnesses)


@dataclass
class StructuralEquivalenceState:
    """Deterministic, revocable, query-read-only structural equivalence state.

    A witness is a structurally paired observation context. Merely reaching the
    same globally dense terminal is not enough: both signatures must be present
    inside the same witness and must arrive through distinct lineages.
    """

    events: list[ConvergenceEvent] = field(default_factory=list)
    min_supporting_witnesses: int = 2

    def observe(self, event: ConvergenceEvent) -> None:
        if event not in self.events:
            self.events.append(event)
            self.events.sort()

    def observe_many(self, events: Iterable[ConvergenceEvent]) -> None:
        for event in events:
            self.observe(event)

    def evaluate(self, left_signature_id: str, right_signature_id: str) -> StructuralEquivalenceCandidate:
        left, right = sorted((left_signature_id, right_signature_id))
        by_witness: dict[str, dict[str, list[ConvergenceEvent]]] = {}
        for event in self.events:
            if event.signature_id not in {left, right}:
                continue
            by_witness.setdefault(event.witness_id, {}).setdefault(event.signature_id, []).append(event)

        support: set[str] = set()
        contradiction: set[str] = set()
        shared_regions: set[str] = set()

        for witness_id, signatures in by_witness.items():
            left_events = signatures.get(left, [])
            right_events = signatures.get(right, [])
            if not left_events or not right_events:
                continue

            same_region = {
                (a.terminal_region_id, a.lineage_id, b.lineage_id)
                for a in left_events
                for b in right_events
                if a.terminal_region_id == b.terminal_region_id and a.lineage_id != b.lineage_id
            }
            if same_region:
                support.add(witness_id)
                shared_regions.update(item[0] for item in same_region)
                continue

            independently_divergent = any(
                a.terminal_region_id != b.terminal_region_id and a.lineage_id != b.lineage_id
                for a in left_events
                for b in right_events
            )
            if independently_divergent:
                contradiction.add(witness_id)

        supporting = tuple(sorted(support))
        contradicting = tuple(sorted(contradiction))
        support_count = len(supporting)
        contradiction_count = len(contradicting)

        if support_count >= self.min_supporting_witnesses and contradiction_count < support_count:
            state = "supported"
        elif contradiction_count and contradiction_count >= support_count:
            state = "contradicted"
        elif support_count:
            state = "candidate"
        else:
            state = "insufficient"

        return StructuralEquivalenceCandidate(
            left_signature_id=left,
            right_signature_id=right,
            shared_terminal_regions=tuple(sorted(shared_regions)),
            supporting_witnesses=supporting,
            contradicting_witnesses=contradicting,
            state=state,
        )

    def snapshot(self) -> tuple[ConvergenceEvent, ...]:
        return tuple(sorted(self.events))
