from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timezone
import json
from pathlib import Path

from .temporal_state_v103 import TemporalSemanticMemoryV103
from .semantic_structure_v101 import StructuredObservationV101


@dataclass(frozen=True, slots=True)
class StateChangeEventV104:
    event_id: str
    entity: str
    predicate: str
    before: tuple[str, ...]
    after: tuple[str, ...]
    memory_id: str
    source_text: str
    observed_at: str
    kind: str = "state_change"


class EventSemanticMemoryV104:
    """Generate explicit events from certified temporal state transitions.

    Conservative rule: an event is emitted only when v1.03 itself classifies
    the new assertion as an explicit temporal change. Conflicts without an
    explicit temporal marker remain conflicts and do not become events.
    """

    def __init__(
        self,
        *,
        threshold: float = 0.42,
        ambiguity_margin: float = 0.04,
        path: str | Path | None = None,
        events_path: str | Path | None = None,
    ) -> None:
        self.temporal = TemporalSemanticMemoryV103(
            threshold=threshold,
            ambiguity_margin=ambiguity_margin,
            path=path,
        )
        self.events_path = Path(events_path) if events_path is not None else None
        self._events: list[StateChangeEventV104] = []
        self._sequence = 0
        if self.events_path and self.events_path.exists():
            self._load_events()

    @staticmethod
    def _key(value: str) -> str:
        return " ".join(value.strip().split()).casefold()

    def _snapshot(self, entity: str) -> dict[str, tuple[str, ...]]:
        state = self.temporal.entity_state(entity)
        if state is None:
            return {}
        return {p.predicate: p.current for p in state.predicates}

    def _candidate_entities(self, observed: StructuredObservationV101) -> tuple[str, ...]:
        return tuple(sorted({e.name for e in observed.frame.entities}, key=str.casefold))

    def observe(
        self,
        text: str,
        *,
        provenance: str = "conversation",
        namespace: str | None = None,
    ) -> StructuredObservationV101:
        # Extract first so we know which entity states must be snapshotted.
        provisional = self.temporal.convergent.structured.extractor.extract(text, memory_id="pending")
        entities = tuple(sorted({e.name for e in provisional.entities}, key=str.casefold))
        before = {entity: self._snapshot(entity) for entity in entities}

        observed = self.temporal.observe(text, provenance=provenance, namespace=namespace)

        for entity in self._candidate_entities(observed):
            state = self.temporal.entity_state(entity)
            if state is None:
                continue
            previous = before.get(entity, {})
            for predicate_state in state.predicates:
                if predicate_state.status != "changed":
                    continue
                old = previous.get(predicate_state.predicate)
                if old is None or old == predicate_state.current:
                    continue
                self._sequence += 1
                self._events.append(
                    StateChangeEventV104(
                        event_id=f"event:{self._sequence:08d}",
                        entity=state.name,
                        predicate=predicate_state.predicate,
                        before=tuple(old),
                        after=tuple(predicate_state.current),
                        memory_id=observed.memory_id,
                        source_text=text,
                        observed_at=datetime.now(timezone.utc).isoformat(),
                    )
                )
        self._persist_events()
        return observed

    def query(self, text: str, *, top_k: int = 3):
        return self.temporal.query(text, top_k=top_k)

    def events(self) -> tuple[StateChangeEventV104, ...]:
        return tuple(self._events)

    def events_for_entity(self, name: str) -> tuple[StateChangeEventV104, ...]:
        needle = self._key(name)
        return tuple(event for event in self._events if self._key(event.entity) == needle)

    def latest_event(self, name: str) -> StateChangeEventV104 | None:
        events = self.events_for_entity(name)
        return events[-1] if events else None

    def _persist_events(self) -> None:
        if self.events_path is None:
            return
        self.events_path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "schema": "events-v104",
            "sequence": self._sequence,
            "events": [asdict(event) for event in self._events],
        }
        tmp = self.events_path.with_suffix(self.events_path.suffix + ".tmp")
        tmp.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        tmp.replace(self.events_path)

    def _load_events(self) -> None:
        raw = json.loads(self.events_path.read_text(encoding="utf-8"))
        if raw.get("schema") != "events-v104":
            raise ValueError("unsupported events schema")
        self._sequence = int(raw.get("sequence", 0))
        self._events = [
            StateChangeEventV104(
                event_id=item["event_id"],
                entity=item["entity"],
                predicate=item["predicate"],
                before=tuple(item.get("before", [])),
                after=tuple(item.get("after", [])),
                memory_id=item["memory_id"],
                source_text=item["source_text"],
                observed_at=item["observed_at"],
                kind=item.get("kind", "state_change"),
            )
            for item in raw.get("events", [])
        ]
