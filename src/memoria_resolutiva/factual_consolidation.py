from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

from .evidence_core import EvidenceCore
from .memory_provenance import MemoryProvenanceIndex


@dataclass(frozen=True, slots=True)
class FactualAbstraction:
    memory_id: str
    subject: str
    predicate: str
    object: str
    support_memory_ids: tuple[str, ...]
    level: int = 1


class FactualConsolidationService:
    """Create conservative hierarchical abstractions from active factual supports.

    Root facts are level 0. Each abstraction is assigned one level above the
    deepest support abstraction. All supports remain explicit conjunctive parents,
    so correction invalidation and provenance remain intact across layers.
    """

    META_LEVEL = "abstraction_level"

    def __init__(self, core: EvidenceCore) -> None:
        self.core = core
        self.provenance = MemoryProvenanceIndex(core)

    @staticmethod
    def _memory_subject(memory_id: str) -> str:
        return f"memory:{memory_id}"

    def abstraction_level(self, memory_id: str, *, namespace: str | None = None) -> int:
        subject = self._memory_subject(memory_id).casefold()
        rows = [
            edge for edge in self.core.active_edges(namespace=namespace)
            if edge.subject.casefold() == subject and edge.predicate == self.META_LEVEL
        ]
        if not rows:
            return 0
        try:
            level = int(rows[-1].object)
        except (TypeError, ValueError):
            return 0
        return max(level, 0)

    def consolidate(
        self,
        *,
        memory_id: str,
        subject: str,
        predicate: str,
        object: str,
        support_memory_ids: Iterable[str],
        namespace: str | None = None,
        confidence: float = 1.0,
        min_support: int = 2,
        max_level: int = 8,
    ) -> FactualAbstraction:
        if min_support < 2:
            raise ValueError("min_support must be >= 2")
        if max_level < 1:
            raise ValueError("max_level must be >= 1")
        if not memory_id.strip():
            raise ValueError("memory_id must be non-empty")

        supports = tuple(dict.fromkeys(str(x) for x in support_memory_ids if str(x)))
        if len(supports) < min_support:
            raise ValueError("insufficient distinct support memories")

        support_levels: list[int] = []
        for support_id in supports:
            if self.provenance.factual_ultimate_source(support_id, namespace=namespace) is None:
                raise ValueError(f"support is not an active factual memory: {support_id}")
            support_levels.append(self.abstraction_level(support_id, namespace=namespace))

        level = 1 + max(support_levels, default=0)
        if level > max_level:
            raise ValueError(f"abstraction level {level} exceeds max_level {max_level}")

        self.core.observe_relation(
            subject,
            predicate,
            object,
            evidence_id=memory_id,
            source_text=f"consolidation:{subject} {predicate} {object}",
            provenance="factual-consolidation",
            origin="factual-consolidation",
            confidence=float(confidence),
            namespace=namespace,
        )
        self.provenance.register(
            memory_id,
            source_type="derived_relation",
            parent_memory_ids=supports,
            namespace=namespace,
        )
        self.core.observe_relation(
            self._memory_subject(memory_id),
            self.META_LEVEL,
            str(level),
            evidence_id=f"abstraction:{memory_id}:level:{level}",
            source_text=f"abstraction-level:{memory_id}:{level}",
            provenance="factual-consolidation-metadata",
            origin="factual-consolidation-metadata",
            confidence=1.0,
            namespace=namespace,
        )
        return FactualAbstraction(
            memory_id=memory_id,
            subject=subject,
            predicate=predicate,
            object=object,
            support_memory_ids=supports,
            level=level,
        )

    def is_factually_active(self, memory_id: str, *, namespace: str | None = None) -> bool:
        return self.provenance.factual_ultimate_source(memory_id, namespace=namespace) is not None
