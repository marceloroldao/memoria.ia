from __future__ import annotations

from dataclasses import dataclass

from .evidence_core import EvidenceCore
from .factual_consolidation import FactualConsolidationService
from .memory_provenance import MemoryProvenanceIndex


@dataclass(frozen=True, slots=True)
class VerticalLayerEdge:
    source_memory_id: str
    target_memory_id: str
    source_level: int
    target_level: int
    relation_type: str = "supports_abstraction"


class VerticalLayerRelationService:
    """Represent explicit inter-layer promotion relations.

    Horizontal semantic relations remain in EvidenceCore. This service records
    only vertical transitions between memory/abstraction levels, so a projection
    can distinguish within-layer structure from cross-layer support.
    """

    PREDICATE = "supports_abstraction"

    def __init__(self, core: EvidenceCore) -> None:
        self.core = core
        self.provenance = MemoryProvenanceIndex(core)
        self.consolidation = FactualConsolidationService(core)

    @staticmethod
    def _memory_subject(memory_id: str) -> str:
        return f"memory:{memory_id}"

    def connect(
        self,
        *,
        source_memory_id: str,
        target_memory_id: str,
        namespace: str | None = None,
    ) -> VerticalLayerEdge:
        if not source_memory_id.strip() or not target_memory_id.strip():
            raise ValueError("source_memory_id and target_memory_id must be non-empty")
        if source_memory_id == target_memory_id:
            raise ValueError("vertical layer edge cannot be self-referential")
        if self.provenance.factual_ultimate_source(source_memory_id, namespace=namespace) is None:
            raise ValueError("source memory is not factually active")
        if self.provenance.factual_ultimate_source(target_memory_id, namespace=namespace) is None:
            raise ValueError("target memory is not factually active")

        source_level = self.consolidation.abstraction_level(source_memory_id, namespace=namespace)
        target_level = self.consolidation.abstraction_level(target_memory_id, namespace=namespace)
        if target_level != source_level + 1:
            raise ValueError(
                f"vertical edge requires adjacent levels; got {source_level}->{target_level}"
            )

        evidence_id = f"vertical:{source_memory_id}:{target_memory_id}"
        self.core.observe_relation(
            self._memory_subject(source_memory_id),
            self.PREDICATE,
            self._memory_subject(target_memory_id),
            evidence_id=evidence_id,
            source_text=f"vertical-layer:{source_memory_id}->{target_memory_id}",
            provenance="layer-transition",
            origin="layer-transition",
            confidence=1.0,
            namespace=namespace,
        )
        self.provenance.register(
            evidence_id,
            source_type="derived_relation",
            parent_memory_ids=(source_memory_id, target_memory_id),
            namespace=namespace,
        )
        return VerticalLayerEdge(
            source_memory_id=source_memory_id,
            target_memory_id=target_memory_id,
            source_level=source_level,
            target_level=target_level,
        )

    def edges(self, *, namespace: str | None = None) -> tuple[VerticalLayerEdge, ...]:
        out: list[VerticalLayerEdge] = []
        for edge in self.core.active_edges(namespace=namespace):
            if edge.predicate != self.PREDICATE:
                continue
            if not edge.subject.startswith("memory:") or not edge.object.startswith("memory:"):
                continue
            source_id = edge.subject.removeprefix("memory:")
            target_id = edge.object.removeprefix("memory:")
            out.append(
                VerticalLayerEdge(
                    source_memory_id=source_id,
                    target_memory_id=target_id,
                    source_level=self.consolidation.abstraction_level(source_id, namespace=namespace),
                    target_level=self.consolidation.abstraction_level(target_id, namespace=namespace),
                )
            )
        out.sort(key=lambda item: (item.source_level, item.source_memory_id, item.target_memory_id))
        return tuple(out)
