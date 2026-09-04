from __future__ import annotations

from dataclasses import dataclass
import hashlib
from typing import Iterable
import unicodedata

from .evidence_core import EvidenceCore, EvidenceEdge
from .factual_consolidation import FactualAbstraction, FactualConsolidationService
from .memory_provenance import MemoryProvenanceIndex


@dataclass(frozen=True, slots=True)
class RepeatedFactCandidate:
    subject: str
    predicate: str
    object: str
    support_memory_ids: tuple[str, ...]
    factual_root_ids: tuple[str, ...]


def _key(value: str) -> str:
    value = unicodedata.normalize("NFKD", value)
    value = "".join(ch for ch in value if not unicodedata.combining(ch))
    return " ".join(value.casefold().strip().split())


def _claim_key(edge: EvidenceEdge) -> tuple[str, str, str]:
    return (_key(edge.subject), _key(edge.predicate), _key(edge.object))


def _consolidated_memory_id(namespace: str | None, claim: tuple[str, str, str]) -> str:
    raw = "\0".join((namespace or "", *claim)).encode("utf-8")
    return "fact:consolidated:" + hashlib.sha256(raw).hexdigest()[:24]


class RepeatedFactConsolidator:
    """Consolidate exact repeated factual claims without erasing their supports.

    This semantic-consolidation path is intentionally precision-first. A claim is
    eligible only when the same normalized subject/predicate/object is supported
    by at least ``min_independent_roots`` distinct active factual roots and every
    selected support meets the semantic-promotion confidence floor. Lower-
    confidence relations remain in evidence/context but do not self-promote into
    factual semantic memory. Multiple derived relations from the same root count
    once. Generative roots never count because ``factual_ultimate_source`` rejects
    them.

    Candidate discovery scans preserved evidence history rather than the collapsed
    current-state projection returned by ``active_edges``. Each historical row is
    still accepted only when its complete factual provenance remains active.

    The resulting memory is a normal ``FactualConsolidationService`` abstraction,
    so its support memories remain explicit conjunctive parents and correction
    invalidation continues to flow through provenance.
    """

    MIN_SUPPORT_CONFIDENCE = 0.90

    _IGNORED_PREDICATES = {
        "conversation_text",
        FactualConsolidationService.META_LEVEL,
    }

    def __init__(self, core: EvidenceCore) -> None:
        self.core = core
        self.provenance = MemoryProvenanceIndex(core)
        self.consolidation = FactualConsolidationService(core)

    def candidates(
        self,
        *,
        namespace: str | None = None,
        min_independent_roots: int = 2,
    ) -> tuple[RepeatedFactCandidate, ...]:
        if min_independent_roots < 2:
            raise ValueError("min_independent_roots must be >= 2")

        grouped: dict[tuple[str, str, str], list[EvidenceEdge]] = {}
        for edge in self.core.evidence_history(namespace=namespace):
            if self._ignored(edge):
                continue
            grouped.setdefault(_claim_key(edge), []).append(edge)

        result: list[RepeatedFactCandidate] = []
        for claim in sorted(grouped):
            supports = self._independent_supports(grouped[claim], namespace=namespace)
            if len(supports) < min_independent_roots:
                continue
            representative = supports[0][0]
            result.append(RepeatedFactCandidate(
                subject=representative.subject,
                predicate=representative.predicate,
                object=representative.object,
                support_memory_ids=tuple(edge.evidence_id for edge, _root in supports),
                factual_root_ids=tuple(root_id for _edge, root_id in supports),
            ))
        return tuple(result)

    def consolidate_all(
        self,
        *,
        namespace: str | None = None,
        min_independent_roots: int = 2,
        max_level: int = 8,
    ) -> tuple[FactualAbstraction, ...]:
        abstractions: list[FactualAbstraction] = []
        for candidate in self.candidates(
            namespace=namespace,
            min_independent_roots=min_independent_roots,
        ):
            claim = (_key(candidate.subject), _key(candidate.predicate), _key(candidate.object))
            memory_id = _consolidated_memory_id(namespace, claim)
            if self._already_consolidated(memory_id, namespace=namespace):
                continue

            support_confidence = min(
                self._edge_by_id(memory_id=support_id, namespace=namespace).confidence
                for support_id in candidate.support_memory_ids
            )
            abstractions.append(self.consolidation.consolidate(
                memory_id=memory_id,
                subject=candidate.subject,
                predicate=candidate.predicate,
                object=candidate.object,
                support_memory_ids=candidate.support_memory_ids,
                namespace=namespace,
                confidence=support_confidence,
                min_support=min_independent_roots,
                max_level=max_level,
            ))
        return tuple(abstractions)

    def _independent_supports(
        self,
        edges: Iterable[EvidenceEdge],
        *,
        namespace: str | None,
    ) -> list[tuple[EvidenceEdge, str]]:
        selected: dict[str, EvidenceEdge] = {}
        for edge in sorted(edges, key=lambda row: (row.epoch, row.evidence_id), reverse=True):
            if edge.confidence < self.MIN_SUPPORT_CONFIDENCE:
                continue
            root = self.provenance.factual_ultimate_source(edge.evidence_id, namespace=namespace)
            if root is None:
                continue
            selected.setdefault(root.memory_id, edge)
        return sorted(
            ((edge, root_id) for root_id, edge in selected.items()),
            key=lambda item: (item[0].epoch, item[0].evidence_id),
        )

    def _ignored(self, edge: EvidenceEdge) -> bool:
        return (
            edge.predicate in self._IGNORED_PREDICATES
            or edge.predicate.startswith("provenance_")
            or edge.origin in {"factual-consolidation", "factual-consolidation-metadata"}
        )

    def _already_consolidated(self, memory_id: str, *, namespace: str | None) -> bool:
        return any(
            edge.evidence_id == memory_id and edge.origin == "factual-consolidation"
            for edge in self.core.evidence_history(namespace=namespace)
        )

    def _edge_by_id(self, *, memory_id: str, namespace: str | None) -> EvidenceEdge:
        for edge in self.core.evidence_history(namespace=namespace):
            if edge.evidence_id == memory_id:
                return edge
        raise ValueError(f"support memory was not found: {memory_id}")
