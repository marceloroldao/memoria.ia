from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass

from .evidence_core import EvidenceCore
from .factual_consolidation import FactualConsolidationService
from .memory_provenance import MemoryProvenanceIndex


@dataclass(frozen=True, slots=True)
class StructuralAbstractionCandidate:
    predicate: str
    object: str
    subjects: tuple[str, ...]
    support_memory_ids: tuple[str, ...]
    support_count: int
    support_level: int = 0
    candidate_level: int = 1


class StructuralAbstractionDetector:
    """Discover recurring factual relation patterns without semantic models.

    Detection is layer-aware: by default, one discovery pass considers only
    evidence from one support level and therefore proposes candidates exactly one
    level above it. This prevents raw facts and higher abstractions from being
    mixed implicitly. Detection remains structural only and never promotes a
    candidate by itself.
    """

    def __init__(self, core: EvidenceCore) -> None:
        self.core = core
        self.provenance = MemoryProvenanceIndex(core)
        self.consolidation = FactualConsolidationService(core)

    def discover(
        self,
        *,
        namespace: str | None = None,
        min_support: int = 2,
        min_distinct_subjects: int = 2,
        support_level: int = 0,
    ) -> tuple[StructuralAbstractionCandidate, ...]:
        if min_support < 2:
            raise ValueError("min_support must be >= 2")
        if min_distinct_subjects < 2:
            raise ValueError("min_distinct_subjects must be >= 2")
        if support_level < 0:
            raise ValueError("support_level must be >= 0")

        grouped: dict[tuple[str, str], list[tuple[str, str, str]]] = defaultdict(list)
        for edge in self.core.active_edges(namespace=namespace):
            if self.provenance.factual_ultimate_source(edge.evidence_id, namespace=namespace) is None:
                continue
            if self.consolidation.abstraction_level(edge.evidence_id, namespace=namespace) != support_level:
                continue
            grouped[(edge.predicate, edge.object.casefold())].append((edge.subject, edge.object, edge.evidence_id))

        candidates: list[StructuralAbstractionCandidate] = []
        for (predicate, _object_key), rows in grouped.items():
            by_subject: dict[str, tuple[str, str, str]] = {}
            for subject, obj, evidence_id in rows:
                by_subject.setdefault(subject.casefold(), (subject, obj, evidence_id))
            if len(by_subject) < min_distinct_subjects:
                continue

            selected = tuple(by_subject[key] for key in sorted(by_subject))
            support_ids = tuple(row[2] for row in selected)
            if len(support_ids) < min_support:
                continue
            candidates.append(
                StructuralAbstractionCandidate(
                    predicate=predicate,
                    object=selected[0][1],
                    subjects=tuple(row[0] for row in selected),
                    support_memory_ids=support_ids,
                    support_count=len(support_ids),
                    support_level=support_level,
                    candidate_level=support_level + 1,
                )
            )

        candidates.sort(
            key=lambda c: (-c.support_count, c.predicate.casefold(), c.object.casefold(), tuple(s.casefold() for s in c.subjects))
        )
        return tuple(candidates)
