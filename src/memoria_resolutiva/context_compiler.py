from __future__ import annotations

from dataclasses import asdict, dataclass
import json
from typing import Iterable

from .evidence_temporal_bridge import EvidenceProjection
from .temporal_query_resolver import TemporalQueryResolution, TemporalQueryResolver
from .topological_memory import CognitiveResult, TemporalEvent, TemporalEventStore, TemporalOperator, Transition


_SCHEMA_VERSION = 1


@dataclass(frozen=True, slots=True)
class CognitiveFact:
    sequence: int
    subject: str
    attribute: str
    value: str
    source: str
    evidence_id: str | None = None
    confidence: float | None = None
    provenance: str | None = None
    origin: str | None = None


@dataclass(frozen=True, slots=True)
class CognitiveTransition:
    from_sequence: int
    from_value: str
    to_sequence: int
    to_value: str


@dataclass(frozen=True, slots=True)
class CognitivePacket:
    """Compact factual context to hand to a language/reasoning model.

    Raw memories and quarantined evidence are intentionally absent. This object is a
    compiled cognitive view, not a memory dump and not a learning instruction.
    """

    schema_version: int
    question: str
    operator: str
    subject: str
    attribute: str
    requested_value: str | None
    exists: bool | None
    facts: tuple[CognitiveFact, ...]
    transitions: tuple[CognitiveTransition, ...]
    activated_addresses: tuple[str, ...]
    candidate_sequences: tuple[int, ...]
    omitted_history_count: int = 0

    def to_payload(self) -> dict[str, object]:
        return asdict(self)

    def to_json(self) -> str:
        return json.dumps(
            self.to_payload(),
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        )


class ContextCompiler:
    """Compile deterministic memory resolution into a bounded cognitive packet.

    The compiler never calls an LLM and never mutates memory. Epistemic audit is used
    only to enrich already-promoted temporal events with provenance metadata.
    Quarantined projections are never emitted as factual context.
    """

    def __init__(
        self,
        store: TemporalEventStore,
        *,
        projections: Iterable[EvidenceProjection] = (),
        max_history: int = 8,
    ) -> None:
        if max_history <= 0:
            raise ValueError("max_history must be positive")
        self.store = store
        self.resolver = TemporalQueryResolver(store)
        self.max_history = int(max_history)
        self._projection_by_sequence: dict[int, EvidenceProjection] = {}
        for projection in projections:
            if not projection.promoted or projection.temporal_event is None:
                continue
            sequence = projection.temporal_event.sequence
            existing = self._projection_by_sequence.get(sequence)
            if existing is not None and existing.evidence_id != projection.evidence_id:
                raise ValueError("multiple promoted projections reference the same temporal sequence")
            self._projection_by_sequence[sequence] = projection

    def _event(self, sequence: int) -> TemporalEvent:
        for event in self.store.iter_events():
            if event.sequence == sequence:
                return event
        raise LookupError(f"temporal event sequence not found: {sequence}")

    def _fact(self, sequence: int) -> CognitiveFact:
        event = self._event(sequence)
        subject = self.store.addresses.node(event.subject_address)
        attribute = self.store.addresses.node(event.attribute_address)
        value = self.store.addresses.node(event.value_address)
        if subject is None or attribute is None or value is None:
            raise LookupError("temporal event references unresolved topology")
        projection = self._projection_by_sequence.get(sequence)
        return CognitiveFact(
            sequence=sequence,
            subject=subject.canonical_value,
            attribute=attribute.canonical_value,
            value=value.canonical_value,
            source=event.source,
            evidence_id=None if projection is None else projection.evidence_id,
            confidence=None if projection is None else projection.confidence,
            provenance=None if projection is None else projection.provenance,
            origin=None if projection is None else projection.origin,
        )

    def _transition(self, transition: Transition) -> CognitiveTransition:
        from_value = self.store.value_text(transition.from_value_address)
        to_value = self.store.value_text(transition.to_value_address)
        if from_value is None or to_value is None:
            raise LookupError("transition references unresolved value")
        return CognitiveTransition(
            from_sequence=transition.from_sequence,
            from_value=from_value,
            to_sequence=transition.to_sequence,
            to_value=to_value,
        )

    @staticmethod
    def _selected_sequences(result: CognitiveResult) -> tuple[int, ...]:
        if result.sequence is not None:
            return (result.sequence,)
        return ()

    def _compile_resolution(self, question: str, resolution: TemporalQueryResolution) -> CognitivePacket:
        plan = resolution.plan
        result = resolution.result
        facts: tuple[CognitiveFact, ...]
        transitions: tuple[CognitiveTransition, ...] = ()
        omitted = 0

        if result.operator is TemporalOperator.HISTORY:
            all_sequences = tuple(sequence for sequence, _ in result.history)
            omitted = max(0, len(all_sequences) - self.max_history)
            selected = all_sequences[-self.max_history :]
            facts = tuple(self._fact(sequence) for sequence in selected)
        elif result.operator is TemporalOperator.STATE_DIFF:
            all_transitions = result.transitions
            omitted = max(0, len(all_transitions) - self.max_history)
            selected_transitions = all_transitions[-self.max_history :]
            transitions = tuple(self._transition(item) for item in selected_transitions)
            sequences: list[int] = []
            for item in selected_transitions:
                if item.from_sequence not in sequences:
                    sequences.append(item.from_sequence)
                if item.to_sequence not in sequences:
                    sequences.append(item.to_sequence)
            facts = tuple(self._fact(sequence) for sequence in sequences)
        else:
            facts = tuple(self._fact(sequence) for sequence in self._selected_sequences(result))

        return CognitivePacket(
            schema_version=_SCHEMA_VERSION,
            question=question.strip(),
            operator=plan.operator.value,
            subject=plan.subject,
            attribute=plan.attribute,
            requested_value=plan.value,
            exists=result.exists,
            facts=facts,
            transitions=transitions,
            activated_addresses=plan.activated_addresses,
            candidate_sequences=plan.candidate_sequences,
            omitted_history_count=omitted,
        )

    def compile(self, question: str) -> CognitivePacket:
        if not question or not question.strip():
            raise ValueError("question must be non-empty")
        resolution = self.resolver.resolve(question)
        return self._compile_resolution(question, resolution)
