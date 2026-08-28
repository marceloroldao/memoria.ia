from __future__ import annotations

from dataclasses import dataclass
import json

from .evidence_core import EvidenceCore

SOURCE_AUTHORITY = {
    "direct_observation": 1.00,
    "user_correction": 1.00,
    "user_assertion": 0.95,
    "external_import": 0.85,
    "derived_relation": 0.75,
    "assistant_generated": 0.25,
    "retrieved_replay": 0.10,
}

_VALID_TYPES = frozenset(SOURCE_AUTHORITY)


@dataclass(frozen=True, slots=True)
class MemoryProvenance:
    memory_id: str
    source_type: str
    authority: float
    parent_memory_ids: tuple[str, ...] = ()
    created_order: int | None = None
    created_time: str | None = None
    superseded_by: str | None = None


@dataclass(frozen=True, slots=True)
class ProvenanceCandidate:
    memory_id: str
    confidence: float
    created_order: int = 0


class MemoryProvenanceIndex:
    """Persisted provenance/authority metadata over EvidenceCore.

    Authority describes source quality and is deliberately independent from
    confidence/similarity. Derived memories inherit authority from their ultimate
    source instead of becoming authoritative merely because a derivation exists.
    """

    META_SOURCE = "provenance_source_type"
    META_PARENTS = "provenance_parents"
    META_ORDER = "provenance_created_order"
    META_TIME = "provenance_created_time"
    META_SUPERSEDED = "provenance_superseded_by"

    def __init__(self, core: EvidenceCore) -> None:
        self.core = core

    @staticmethod
    def authority_for(source_type: str) -> float:
        if source_type not in _VALID_TYPES:
            raise ValueError(f"unsupported source_type: {source_type}")
        return SOURCE_AUTHORITY[source_type]

    @staticmethod
    def _subject(memory_id: str) -> str:
        if not memory_id.strip():
            raise ValueError("memory_id must be non-empty")
        return f"memory:{memory_id}"

    def register(
        self,
        memory_id: str,
        *,
        source_type: str,
        parent_memory_ids: tuple[str, ...] | list[str] = (),
        created_order: int | None = None,
        created_time: str | None = None,
        namespace: str | None = None,
    ) -> MemoryProvenance:
        self.authority_for(source_type)
        if created_order is not None and created_order < 0:
            raise ValueError("created_order must be >= 0")
        parents = tuple(dict.fromkeys(str(x) for x in parent_memory_ids if str(x)))
        subject = self._subject(memory_id)
        common = dict(
            source_text=f"provenance:{memory_id}",
            provenance="memory-provenance",
            origin="memory-provenance",
            confidence=1.0,
            namespace=namespace,
        )
        self.core.observe_relation(subject, self.META_SOURCE, source_type, evidence_id=f"prov:{memory_id}:source", **common)
        self.core.observe_relation(subject, self.META_PARENTS, json.dumps(parents, separators=(",", ":")), evidence_id=f"prov:{memory_id}:parents", **common)
        if created_order is not None:
            self.core.observe_relation(subject, self.META_ORDER, str(created_order), evidence_id=f"prov:{memory_id}:order", **common)
        if created_time:
            self.core.observe_relation(subject, self.META_TIME, created_time, evidence_id=f"prov:{memory_id}:time", **common)
        return self.inspect(memory_id, namespace=namespace)

    def supersede(self, memory_id: str, *, by_memory_id: str, namespace: str | None = None) -> None:
        subject = self._subject(memory_id)
        self.core.observe_relation(
            subject, self.META_SUPERSEDED, by_memory_id,
            evidence_id=f"prov:{memory_id}:superseded:{by_memory_id}",
            source_text=f"provenance:{memory_id}", provenance="memory-provenance",
            origin="memory-provenance", confidence=1.0, namespace=namespace,
        )

    def inspect(self, memory_id: str, *, namespace: str | None = None) -> MemoryProvenance:
        subject = self._subject(memory_id).casefold()
        rows = [e for e in self.core.active_edges(namespace=namespace) if e.subject.casefold() == subject]
        by_predicate = {e.predicate: e.object for e in rows}
        source_type = by_predicate.get(self.META_SOURCE, "retrieved_replay")
        self.authority_for(source_type)
        try:
            parents = tuple(json.loads(by_predicate.get(self.META_PARENTS, "[]")))
        except (TypeError, ValueError, json.JSONDecodeError):
            parents = ()
        order_raw = by_predicate.get(self.META_ORDER)
        return MemoryProvenance(
            memory_id=memory_id,
            source_type=source_type,
            authority=self.authority_for(source_type),
            parent_memory_ids=parents,
            created_order=None if order_raw is None else int(order_raw),
            created_time=by_predicate.get(self.META_TIME),
            superseded_by=by_predicate.get(self.META_SUPERSEDED),
        )

    def ultimate_source(self, memory_id: str, *, namespace: str | None = None) -> MemoryProvenance:
        """Trace derived/replayed/generated echoes to the strongest root source.

        Assistant-generated content only inherits an upstream authority when its
        lineage is explicit through parent_memory_ids. Generated content without
        parents remains an assistant-generated root and therefore low-authority.
        """
        queue = [memory_id]
        seen: set[str] = set()
        roots: list[MemoryProvenance] = []
        while queue:
            current = queue.pop(0)
            if current in seen:
                continue
            seen.add(current)
            meta = self.inspect(current, namespace=namespace)
            if meta.superseded_by is not None:
                continue
            traceable = meta.source_type in {"derived_relation", "retrieved_replay", "assistant_generated"}
            if traceable and meta.parent_memory_ids:
                queue.extend(meta.parent_memory_ids)
            else:
                roots.append(meta)
        if not roots:
            return self.inspect(memory_id, namespace=namespace)
        roots.sort(key=lambda m: (-m.authority, -(m.created_order or 0), m.memory_id))
        return roots[0]

    def select(self, candidates: list[ProvenanceCandidate], *, namespace: str | None = None) -> ProvenanceCandidate | None:
        eligible: list[tuple[float, float, int, ProvenanceCandidate]] = []
        for candidate in candidates:
            direct = self.inspect(candidate.memory_id, namespace=namespace)
            if direct.superseded_by is not None:
                continue
            source = self.ultimate_source(candidate.memory_id, namespace=namespace)
            eligible.append((
                source.authority,
                float(candidate.confidence),
                int(candidate.created_order),
                candidate,
            ))
        if not eligible:
            return None
        eligible.sort(key=lambda row: (-row[0], -row[1], -row[2], row[3].memory_id))
        return eligible[0][3]
