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


class FactualConsolidationService:
    """Create conservative abstractions from explicit active factual supports.

    This service does not discover concepts heuristically. A caller proposes an
    abstraction and supplies the memories that support it. The abstraction is
    admitted only when at least ``min_support`` distinct supports retain active
    factual roots. Its provenance is registered as ``derived_relation`` with all
    supports as conjunctive parents, so the abstraction automatically loses
    factual validity if any required support is later superseded.
    """

    def __init__(self, core: EvidenceCore) -> None:
        self.core = core
        self.provenance = MemoryProvenanceIndex(core)

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
    ) -> FactualAbstraction:
        if min_support < 2:
            raise ValueError("min_support must be >= 2")
        if not memory_id.strip():
            raise ValueError("memory_id must be non-empty")

        supports = tuple(dict.fromkeys(str(x) for x in support_memory_ids if str(x)))
        if len(supports) < min_support:
            raise ValueError("insufficient distinct support memories")

        for support_id in supports:
            if self.provenance.factual_ultimate_source(support_id, namespace=namespace) is None:
                raise ValueError(f"support is not an active factual memory: {support_id}")

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
        return FactualAbstraction(
            memory_id=memory_id,
            subject=subject,
            predicate=predicate,
            object=object,
            support_memory_ids=supports,
        )

    def is_factually_active(self, memory_id: str, *, namespace: str | None = None) -> bool:
        return self.provenance.factual_ultimate_source(memory_id, namespace=namespace) is not None
