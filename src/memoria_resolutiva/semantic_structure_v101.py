from __future__ import annotations

from dataclasses import dataclass
import re

from .autonomous_memory_v100 import AutonomousTextMemoryV100

_VOLT = re.compile(r"\b(\d+(?:[.,]\d+)?)\s*(V|kV|mV)\b", re.IGNORECASE)
_CURRENT = re.compile(r"\b(\d+(?:[.,]\d+)?)\s*(A|mA)\b", re.IGNORECASE)


@dataclass(frozen=True, slots=True)
class EntityV101:
    name: str
    kind: str = "unknown"


@dataclass(frozen=True, slots=True)
class RelationV101:
    subject: str
    predicate: str
    object: str
    confidence: float


@dataclass(frozen=True, slots=True)
class SemanticFrameV101:
    source_text: str
    memory_id: str
    entities: tuple[EntityV101, ...]
    relations: tuple[RelationV101, ...]
    concepts: tuple[str, ...]
    unresolved: bool = False


@dataclass(frozen=True, slots=True)
class StructuredObservationV101:
    memory_id: str
    decision: str
    frame: SemanticFrameV101


class DeterministicSemanticExtractorV101:
    """Conservative Portuguese-first semantic structure extractor."""

    _TYPE_PATTERNS = (re.compile(r"\b(?:a|o)\s+(fonte|sensor|controlador|inversor|módulo|modulo|estação|estacao|robô|robo)\s+([A-ZÁÉÍÓÚÂÊÔÃÕÇ][\wÀ-ÿ.-]*)", re.IGNORECASE),)
    _PROVIDES = re.compile(r"\b(?:a|o)\s+(?P<kind>fonte|módulo|modulo|inversor)\s+(?P<name>[\wÀ-ÿ.-]+)\s+(?:fornece|entrega)\s+(?P<value>\d+(?:[.,]\d+)?\s*(?:mV|V|kV))\s+(?:ao|à|a)\s+(?P<target>[\wÀ-ÿ.-]+)", re.IGNORECASE)
    _POWERS = re.compile(r"\b(?:a|o)\s+(?P<kind>fonte|módulo|modulo|inversor)\s+(?P<name>[\wÀ-ÿ.-]+)\s+(?:alimenta|energiza)\s+(?:o|a)?\s*(?P<target>[\wÀ-ÿ.-]+)", re.IGNORECASE)
    _MEASURES = re.compile(r"\b(?:o|a)\s+(?P<kind>sensor)\s+(?P<name>[\wÀ-ÿ.-]+)\s+(?:mede|monitora)\s+(?P<quantity>[\wÀ-ÿ.-]+)(?:\s+(?:na|no)\s+(?P<place>.+?))?[.!?]?$", re.IGNORECASE)
    _BELONGS = re.compile(r"\b(?:o|a)\s+(?P<kind>[\wÀ-ÿ.-]+)\s+(?P<name>[\wÀ-ÿ.-]+)\s+pertence\s+(?:ao|à|a)\s+(?P<target>[\wÀ-ÿ.-]+)", re.IGNORECASE)

    @staticmethod
    def _norm(value: str) -> str:
        return " ".join(value.strip().strip(".,;:!?\"").split())

    def extract(self, text: str, *, memory_id: str) -> SemanticFrameV101:
        entities: dict[str, EntityV101] = {}
        relations: list[RelationV101] = []
        concepts: set[str] = set()

        def entity(name: str, kind: str = "unknown") -> str:
            n = self._norm(name)
            key = n.casefold()
            current = entities.get(key)
            if current is None or current.kind == "unknown":
                entities[key] = EntityV101(n, self._norm(kind).casefold())
            concepts.add(n.casefold())
            if kind != "unknown":
                concepts.add(self._norm(kind).casefold())
            return entities[key].name

        for pattern in self._TYPE_PATTERNS:
            for match in pattern.finditer(text):
                entity(match.group(2), match.group(1))
        m = self._PROVIDES.search(text)
        if m:
            src, target, value = entity(m.group("name"), m.group("kind")), entity(m.group("target")), self._norm(m.group("value"))
            concepts.update({"tensão", "alimentação"})
            relations.extend((RelationV101(src, "has_voltage", value, 1.0), RelationV101(src, "powers", target, 0.95)))
        m = self._POWERS.search(text)
        if m:
            src, target = entity(m.group("name"), m.group("kind")), entity(m.group("target"))
            concepts.add("alimentação")
            relations.append(RelationV101(src, "powers", target, 1.0))
        m = self._MEASURES.search(text)
        if m:
            src, quantity = entity(m.group("name"), m.group("kind")), self._norm(m.group("quantity"))
            concepts.add(quantity.casefold())
            relations.append(RelationV101(src, "measures", quantity, 1.0))
            if m.group("place"):
                relations.append(RelationV101(src, "located_at", entity(self._norm(m.group("place"))), 0.9))
        m = self._BELONGS.search(text)
        if m:
            relations.append(RelationV101(entity(m.group("name"), m.group("kind")), "belongs_to", entity(m.group("target")), 1.0))
        if _VOLT.search(text): concepts.add("tensão")
        if _CURRENT.search(text): concepts.add("corrente")
        return SemanticFrameV101(text, memory_id, tuple(sorted(entities.values(), key=lambda e: (e.name.casefold(), e.kind))), tuple(relations), tuple(sorted(concepts)), not relations)


class StructuredAutonomousMemoryV101:
    """v1.00 autonomous retrieval plus an explicit semantic-structure layer."""

    def __init__(self, *, threshold: float = 0.42, ambiguity_margin: float = 0.04) -> None:
        self.memory = AutonomousTextMemoryV100(threshold=threshold, ambiguity_margin=ambiguity_margin)
        self.extractor = DeterministicSemanticExtractorV101()
        self._frames: dict[str, SemanticFrameV101] = {}

    def observe(self, text: str, *, provenance: str = "conversation", namespace: str | None = None) -> StructuredObservationV101:
        # v1.00 inherits the v0.98 contract (provenance, not namespace).
        effective_provenance = provenance if namespace is None else f"{provenance}:{namespace}"
        observed = self.memory.observe(text, provenance=effective_provenance)
        frame = self.extractor.extract(text, memory_id=observed.memory_id)
        self._frames[observed.memory_id] = frame
        return StructuredObservationV101(observed.memory_id, observed.decision, frame)

    def query(self, text: str, *, top_k: int = 3):
        return self.memory.query(text, top_k=top_k)

    def frame(self, memory_id: str) -> SemanticFrameV101 | None:
        return self._frames.get(memory_id)

    def frames_for_entity(self, name: str) -> tuple[SemanticFrameV101, ...]:
        needle = name.casefold()
        return tuple(frame for frame in self._frames.values() if any(entity.name.casefold() == needle for entity in frame.entities))

    def relations_for(self, name: str) -> tuple[RelationV101, ...]:
        needle = name.casefold()
        out: list[RelationV101] = []
        for frame in self.frames_for_entity(name):
            out.extend(r for r in frame.relations if r.subject.casefold() == needle or r.object.casefold() == needle)
        return tuple(out)
