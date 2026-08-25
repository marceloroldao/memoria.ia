from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import re
from pathlib import Path

from .semantic_convergence_v102 import ConvergentSemanticMemoryV102, EntityStateV102
from .semantic_structure_v101 import RelationV101, StructuredObservationV101

_TEMPORAL_MARKERS = (
    "agora",
    "atualmente",
    "hoje",
    "antes",
    "ontem",
    "depois",
    "passou a",
    "mudou para",
    "foi alterado para",
)


@dataclass(frozen=True, slots=True)
class TemporalAssertionV103:
    entity: str
    predicate: str
    value: str
    memory_id: str
    source_text: str
    observed_at: str
    temporal: bool


@dataclass(frozen=True, slots=True)
class TemporalPredicateStateV103:
    predicate: str
    current: tuple[str, ...]
    history: tuple[str, ...]
    status: str  # stable | changed | conflict
    evidence_ids: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class TemporalEntityStateV103:
    name: str
    base: EntityStateV102
    predicates: tuple[TemporalPredicateStateV103, ...]


class TemporalSemanticMemoryV103:
    """Temporal interpretation over convergent semantic memory.

    Conservative rule: incompatible values are only interpreted as a temporal
    change when the newer source contains an explicit temporal/change marker.
    Otherwise both values remain current candidates and the predicate is marked
    as conflict. Original assertions are always retained in history/evidence.
    """

    def __init__(
        self,
        *,
        threshold: float = 0.42,
        ambiguity_margin: float = 0.04,
        path: str | Path | None = None,
    ) -> None:
        self.convergent = ConvergentSemanticMemoryV102(
            threshold=threshold,
            ambiguity_margin=ambiguity_margin,
            path=path,
        )
        self._assertions: dict[tuple[str, str], list[TemporalAssertionV103]] = {}
        # Rebuild the temporal index from any frames loaded by v1.02.
        for state in self.convergent.all_entity_states():
            for evidence in state.evidence:
                frame = self.convergent._frames.get(evidence.memory_id)
                if frame is not None:
                    self._register_frame(frame)

    @staticmethod
    def _key(value: str) -> str:
        return " ".join(value.strip().split()).casefold()

    @staticmethod
    def _has_temporal_marker(text: str) -> bool:
        folded = text.casefold()
        return any(marker in folded for marker in _TEMPORAL_MARKERS)

    def _register_relation(self, relation: RelationV101, *, memory_id: str, source_text: str) -> None:
        subject = self._key(relation.subject)
        key = (subject, relation.predicate)
        assertion = TemporalAssertionV103(
            entity=relation.subject,
            predicate=relation.predicate,
            value=relation.object,
            memory_id=memory_id,
            source_text=source_text,
            observed_at=datetime.now(timezone.utc).isoformat(),
            temporal=self._has_temporal_marker(source_text),
        )
        bucket = self._assertions.setdefault(key, [])
        if not any(a.memory_id == memory_id and self._key(a.value) == self._key(assertion.value) for a in bucket):
            bucket.append(assertion)

    def _register_frame(self, frame) -> None:
        for relation in frame.relations:
            self._register_relation(
                relation,
                memory_id=frame.memory_id,
                source_text=frame.source_text,
            )

    def observe(
        self,
        text: str,
        *,
        provenance: str = "conversation",
        namespace: str | None = None,
    ) -> StructuredObservationV101:
        observed = self.convergent.observe(
            text,
            provenance=provenance,
            namespace=namespace,
        )
        self._register_frame(observed.frame)
        return observed

    def query(self, text: str, *, top_k: int = 3):
        return self.convergent.query(text, top_k=top_k)

    def predicate_state(self, entity: str, predicate: str) -> TemporalPredicateStateV103 | None:
        bucket = self._assertions.get((self._key(entity), predicate), ())
        if not bucket:
            return None
        values: list[str] = []
        for item in bucket:
            if self._key(item.value) not in {self._key(v) for v in values}:
                values.append(item.value)

        if len(values) == 1:
            current = (values[-1],)
            status = "stable"
        else:
            # Only an explicit temporal marker on the latest incompatible
            # assertion is allowed to convert conflict into state transition.
            latest = bucket[-1]
            previous_values = {self._key(a.value) for a in bucket[:-1]}
            changed = latest.temporal and self._key(latest.value) not in previous_values
            if changed:
                current = (latest.value,)
                status = "changed"
            else:
                current = tuple(values)
                status = "conflict"

        return TemporalPredicateStateV103(
            predicate=predicate,
            current=current,
            history=tuple(a.value for a in bucket),
            status=status,
            evidence_ids=tuple(a.memory_id for a in bucket),
        )

    def entity_state(self, name: str) -> TemporalEntityStateV103 | None:
        base = self.convergent.entity_state(name)
        if base is None:
            return None
        predicates = sorted({p for (entity, p) in self._assertions if entity == self._key(name)})
        states = tuple(
            state for p in predicates
            if (state := self.predicate_state(name, p)) is not None
        )
        return TemporalEntityStateV103(name=base.name, base=base, predicates=states)
