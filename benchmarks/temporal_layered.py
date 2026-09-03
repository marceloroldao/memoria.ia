from __future__ import annotations

import json
from dataclasses import asdict, dataclass

from memoria_resolutiva.evidence_core import EvidenceCore
from memoria_resolutiva.factual_consolidation import FactualConsolidationService
from memoria_resolutiva.memory_provenance import MemoryProvenanceIndex
from memoria_resolutiva.structural_abstraction import StructuralAbstractionDetector


@dataclass(frozen=True, slots=True)
class TemporalPoint:
    step: int
    flat_stale_items: int
    layered_stale_items: int
    flat_pattern_context_items: int
    layered_pattern_context_items: int


@dataclass(frozen=True, slots=True)
class TemporalLayeredResult:
    points: tuple[TemporalPoint, ...]
    flat_final_stale_items: int
    layered_final_stale_items: int
    flat_final_pattern_context_items: int
    layered_final_pattern_context_items: int
    final_context_reduction: float


def _observe(core, prov, memory_id, subject, predicate, obj, source_type):
    core.observe_relation(
        subject,
        predicate,
        obj,
        evidence_id=memory_id,
        source_text=f"{subject} {predicate} {obj}",
        provenance="temporal-layered-benchmark",
        origin=source_type,
        namespace="temporal",
    )
    prov.register(memory_id, source_type=source_type, namespace="temporal")


def run_temporal_layered() -> TemporalLayeredResult:
    core = EvidenceCore()
    prov = MemoryProvenanceIndex(core)
    consolidation = FactualConsolidationService(core)
    points: list[TemporalPoint] = []

    latest_by_subject: dict[str, str] = {}
    all_fact_ids: list[str] = []
    cat_ids: list[str] = []

    # Four rounds: growth, correction, more growth, another correction.
    events = [
        ("Alt", "cat", "user_assertion"),
        ("Alt2", "cat", "user_assertion"),
        ("Mia", "cat", "user_assertion"),
        ("Nina", "cat", "user_assertion"),
        ("Alt2", "dog", "user_correction"),
        ("Leo", "cat", "user_assertion"),
        ("Luna", "cat", "user_assertion"),
        ("Mia", "dog", "user_correction"),
    ]

    abstraction_id: str | None = None
    abstraction_supports: tuple[str, ...] = ()

    for step, (subject, obj, source_type) in enumerate(events, start=1):
        memory_id = f"m{step}"
        _observe(core, prov, memory_id, subject, "is_a", obj, source_type)
        all_fact_ids.append(memory_id)

        previous = latest_by_subject.get(subject)
        if previous is not None and source_type == "user_correction":
            prov.supersede(previous, by_memory_id=memory_id, namespace="temporal")
        latest_by_subject[subject] = memory_id

        if obj == "cat":
            cat_ids.append(memory_id)

        # Flat baseline retains every old assertion/correction row as usable.
        flat_stale = sum(
            1
            for subject_name, latest_id in latest_by_subject.items()
            for mid in all_fact_ids
            if mid != latest_id
            and prov.inspect(mid, namespace="temporal").superseded_by is not None
        )
        # The layered policy excludes superseded rows from factual state.
        layered_stale = sum(
            1
            for mid in all_fact_ids
            if prov.inspect(mid, namespace="temporal").superseded_by is not None
            and prov.factual_ultimate_source(mid, namespace="temporal") is not None
        )

        active_cat_ids = tuple(
            mid for mid in cat_ids
            if prov.factual_ultimate_source(mid, namespace="temporal") is not None
        )
        flat_context = len(active_cat_ids)
        layered_context = flat_context

        if len(active_cat_ids) >= 2:
            candidates = StructuralAbstractionDetector(core).discover(
                namespace="temporal", support_level=0
            )
            cat_candidates = [
                row for row in candidates
                if row.predicate == "is_a" and row.object.casefold() == "cat"
            ]
            if cat_candidates:
                supports = cat_candidates[0].support_memory_ids
                if supports != abstraction_supports:
                    abstraction_id = f"abs-cat-{step}"
                    consolidation.consolidate(
                        memory_id=abstraction_id,
                        subject="pattern:is_a:cat",
                        predicate="summarizes",
                        object="cat-membership-pattern",
                        support_memory_ids=supports,
                        namespace="temporal",
                    )
                    abstraction_supports = supports
                if abstraction_id and consolidation.is_factually_active(
                    abstraction_id, namespace="temporal"
                ):
                    layered_context = 1

        points.append(
            TemporalPoint(
                step=step,
                flat_stale_items=flat_stale,
                layered_stale_items=layered_stale,
                flat_pattern_context_items=flat_context,
                layered_pattern_context_items=layered_context,
            )
        )

    last = points[-1]
    reduction = 0.0 if last.flat_pattern_context_items == 0 else 1.0 - (
        last.layered_pattern_context_items / last.flat_pattern_context_items
    )
    return TemporalLayeredResult(
        points=tuple(points),
        flat_final_stale_items=last.flat_stale_items,
        layered_final_stale_items=last.layered_stale_items,
        flat_final_pattern_context_items=last.flat_pattern_context_items,
        layered_final_pattern_context_items=last.layered_pattern_context_items,
        final_context_reduction=reduction,
    )


def main() -> None:
    print(json.dumps(asdict(run_temporal_layered()), indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
