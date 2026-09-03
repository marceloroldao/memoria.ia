from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass

from .evidence_core import EvidenceCore
from .memory_provenance import MemoryProvenanceIndex


@dataclass(frozen=True, slots=True)
class StructuralAbstractionCandidate:
    predicate: str
    object: str
    subjects: tuple[str, ...]
    support_memory_ids: tuple[str, ...]
    support_count: int


class StructuralAbstractionDetector:
    """Discover recurring factual relation patterns without semantic models.

    A candidate is a repeated factual `(predicate, object)` pattern observed on
    multiple distinct subjects. Detection is intentionally structural only: it
    does not parse text, invent labels, or promote anything by itself. Promotion
    remains the responsibility of FactualConsolidationService.
    """

    def __init__(self, core: EvidenceCore) -> None:
        self.core = core
        self.provenance = MemoryProvenanceIndex(core)

    def discover(
        self,
        *,
        namespace: str | None = None,
        min_support: int = 2,
        min_distinct_subjects: int = 2,
    ) -> tuple[StructuralAbstractionCandidate, ...]:
        if min_support < 2:
            raise ValueError("min_support must be >= 2")
        if min_distinct_subjects < 2:
            raise ValueError("min_distinct_subjects must be >= 2")

        grouped: dict[tuple[str, str], list[tuple[str, str, str]]] = defaultdict(list)
        for edge in self.core.active_edges(namespace=namespace):
            if self.provenance.factual_ultimate_source(edge.evidence_id, namespace=namespace) is None:
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
                )
            )

        candidates.sort(
            key=lambda c: (-c.support_count, c.predicate.casefold(), c.object.casefold(), tuple(s.casefold() for s in c.subjects))
        )
        return tuple(candidates)
