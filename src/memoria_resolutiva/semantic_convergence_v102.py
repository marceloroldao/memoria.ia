from __future__ import annotations

from dataclasses import asdict, dataclass
import json
from pathlib import Path
from typing import Iterable

from .semantic_structure_v101 import (
    EntityV101,
    RelationV101,
    SemanticFrameV101,
    StructuredAutonomousMemoryV101,
    StructuredObservationV101,
)

_SINGLE_VALUED = frozenset({"has_voltage", "located_at"})


@dataclass(frozen=True, slots=True)
class EvidenceV102:
    memory_id: str
    source_text: str


@dataclass(frozen=True, slots=True)
class EntityStateV102:
    name: str
    kinds: tuple[str, ...]
    relations: tuple[RelationV101, ...]
    evidence: tuple[EvidenceV102, ...]
    conflicts: tuple[str, ...]


class ConvergentSemanticMemoryV102:
    """Accumulate v1.01 frames into explicit persistent entity states.

    The original frame remains authoritative evidence. Convergence never deletes
    a conflicting assertion: incompatible single-valued relations are retained
    and surfaced through ``conflicts`` instead of being silently overwritten.
    """

    def __init__(
        self,
        *,
        threshold: float = 0.42,
        ambiguity_margin: float = 0.04,
        path: str | Path | None = None,
    ) -> None:
        self.structured = StructuredAutonomousMemoryV101(
            threshold=threshold, ambiguity_margin=ambiguity_margin
        )
        self.path = Path(path) if path is not None else None
        self._frames: dict[str, SemanticFrameV101] = {}
        self._entity_frames: dict[str, list[str]] = {}
        if self.path and self.path.exists():
            self._load()

    @staticmethod
    def _key(name: str) -> str:
        return " ".join(name.strip().split()).casefold()

    def observe(
        self,
        text: str,
        *,
        provenance: str = "conversation",
        namespace: str | None = None,
    ) -> StructuredObservationV101:
        observed = self.structured.observe(
            text, provenance=provenance, namespace=namespace
        )
        self._register_frame(observed.frame)
        self._persist()
        return observed

    def query(self, text: str, *, top_k: int = 3):
        return self.structured.query(text, top_k=top_k)

    def _register_frame(self, frame: SemanticFrameV101) -> None:
        self._frames[frame.memory_id] = frame
        for entity in frame.entities:
            key = self._key(entity.name)
            ids = self._entity_frames.setdefault(key, [])
            if frame.memory_id not in ids:
                ids.append(frame.memory_id)

    def frames_for_entity(self, name: str) -> tuple[SemanticFrameV101, ...]:
        ids = self._entity_frames.get(self._key(name), ())
        return tuple(self._frames[mid] for mid in ids if mid in self._frames)

    def entity_state(self, name: str) -> EntityStateV102 | None:
        frames = self.frames_for_entity(name)
        if not frames:
            return None
        needle = self._key(name)
        display = name.strip()
        kinds: set[str] = set()
        relations: list[RelationV101] = []
        seen_rel: set[tuple[str, str, str]] = set()
        evidence: list[EvidenceV102] = []
        values_by_predicate: dict[str, set[str]] = {}
        for frame in frames:
            evidence.append(EvidenceV102(frame.memory_id, frame.source_text))
            for entity in frame.entities:
                if self._key(entity.name) == needle:
                    display = entity.name
                    if entity.kind != "unknown":
                        kinds.add(entity.kind)
            for relation in frame.relations:
                if self._key(relation.subject) != needle and self._key(relation.object) != needle:
                    continue
                sig = (
                    self._key(relation.subject),
                    relation.predicate,
                    self._key(relation.object),
                )
                if sig not in seen_rel:
                    seen_rel.add(sig)
                    relations.append(relation)
                if self._key(relation.subject) == needle and relation.predicate in _SINGLE_VALUED:
                    values_by_predicate.setdefault(relation.predicate, set()).add(
                        self._key(relation.object)
                    )
        conflicts = tuple(
            sorted(pred for pred, values in values_by_predicate.items() if len(values) > 1)
        )
        return EntityStateV102(
            name=display,
            kinds=tuple(sorted(kinds)),
            relations=tuple(relations),
            evidence=tuple(evidence),
            conflicts=conflicts,
        )

    def all_entity_states(self) -> tuple[EntityStateV102, ...]:
        states = [self.entity_state(key) for key in sorted(self._entity_frames)]
        return tuple(state for state in states if state is not None)

    def _persist(self) -> None:
        if self.path is None:
            return
        self.path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "schema": "semantic-convergence-v102",
            "frames": [
                {
                    "source_text": f.source_text,
                    "memory_id": f.memory_id,
                    "entities": [asdict(e) for e in f.entities],
                    "relations": [asdict(r) for r in f.relations],
                    "concepts": list(f.concepts),
                    "unresolved": f.unresolved,
                }
                for f in self._frames.values()
            ],
        }
        tmp = self.path.with_suffix(self.path.suffix + ".tmp")
        tmp.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        tmp.replace(self.path)

    def _load(self) -> None:
        raw = json.loads(self.path.read_text(encoding="utf-8"))
        if raw.get("schema") != "semantic-convergence-v102":
            raise ValueError("unsupported semantic convergence schema")
        for item in raw.get("frames", []):
            frame = SemanticFrameV101(
                source_text=item["source_text"],
                memory_id=item["memory_id"],
                entities=tuple(EntityV101(**e) for e in item.get("entities", [])),
                relations=tuple(RelationV101(**r) for r in item.get("relations", [])),
                concepts=tuple(item.get("concepts", [])),
                unresolved=bool(item.get("unresolved", False)),
            )
            self._register_frame(frame)

    def ingest_frames(self, frames: Iterable[SemanticFrameV101]) -> None:
        for frame in frames:
            self._register_frame(frame)
        self._persist()
