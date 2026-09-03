from __future__ import annotations

from .evidence_core import EvidenceCore, EvidenceInferenceResult
from .memory_provenance import MemoryProvenanceIndex


class _FactualEvidenceView(EvidenceCore):
    """Ephemeral EvidenceCore view containing only factual-root evidence.

    The view delegates origin reliability reads to the source core so inference
    thresholds keep the same adjudicated reliability semantics. No persistent
    state is mutated and provenance metadata edges are not copied into the
    structural graph.
    """

    def __init__(self, source: EvidenceCore, *, namespace: str | None, epoch: int | None) -> None:
        super().__init__()
        self._source = source
        provenance = MemoryProvenanceIndex(source)
        for edge in source.active_edges(namespace=namespace, epoch=epoch):
            root = provenance.factual_ultimate_source(edge.evidence_id, namespace=namespace)
            if root is None:
                continue
            self.observe_relation(
                edge.subject,
                edge.predicate,
                edge.object,
                evidence_id=edge.evidence_id,
                source_text=edge.source_text,
                provenance=edge.provenance,
                origin=edge.origin,
                confidence=edge.confidence,
                namespace=edge.namespace,
                epoch=edge.epoch,
            )

    def origin_reliability(self, origin: str, *, metric: str = "posterior") -> float:
        return self._source.origin_reliability(origin, metric=metric)


class FactualInferenceService:
    """Run structural inference using only evidence with an active factual root.

    Generated and replayed memories remain in the source EvidenceCore for history
    and auditability. They enter this factual view only when their provenance
    explicitly traces to an active factual root, preventing a standalone LLM
    hallucination from becoming an inference premise. Derived relations with
    explicit parents additionally require every premise to remain active.
    """

    def __init__(self, core: EvidenceCore) -> None:
        self.core = core

    def infer_path(
        self,
        source: str,
        target: str,
        *,
        max_hops: int = 3,
        max_paths: int = 5,
        namespace: str | None = None,
        epoch: int | None = None,
        min_confidence: float = 0.0,
        min_independent_origins: int = 1,
        min_origin_reliability: float | None = None,
        reliability_metric: str = "posterior",
    ) -> EvidenceInferenceResult:
        view = _FactualEvidenceView(self.core, namespace=namespace, epoch=epoch)
        return view.infer_path(
            source,
            target,
            max_hops=max_hops,
            max_paths=max_paths,
            namespace=namespace,
            epoch=epoch,
            min_confidence=min_confidence,
            min_independent_origins=min_independent_origins,
            min_origin_reliability=min_origin_reliability,
            reliability_metric=reliability_metric,
        )
