from __future__ import annotations

import json
from dataclasses import asdict, dataclass

from memoria_resolutiva.evidence_core import EvidenceCore
from memoria_resolutiva.factual_consolidation import FactualConsolidationService
from memoria_resolutiva.memory_provenance import MemoryProvenanceIndex
from memoria_resolutiva.structural_abstraction import StructuralAbstractionDetector


@dataclass(frozen=True, slots=True)
class ArchitectureABResult:
    flat_false_positives: int
    layered_false_positives: int
    flat_stale_facts: int
    layered_stale_facts: int
    flat_stale_derivations: int
    layered_stale_derivations: int
    flat_pattern_context_items: int
    layered_pattern_context_items: int
    pattern_context_reduction: float
    flat_safety_score: float
    layered_safety_score: float


def _observe(core: EvidenceCore, prov: MemoryProvenanceIndex, memory_id: str, subject: str, predicate: str, obj: str, source_type: str) -> None:
    core.observe_relation(
        subject,
        predicate,
        obj,
        evidence_id=memory_id,
        source_text=f"{subject} {predicate} {obj}",
        provenance="architecture-ab-benchmark",
        origin=source_type,
        namespace="ab",
    )
    prov.register(memory_id, source_type=source_type, namespace="ab")


def run_architecture_ab() -> ArchitectureABResult:
    """Compare a deliberately flat memory policy with the provenance/layer policy.

    The flat baseline treats every persisted edge as current factual material.
    The layered policy uses the current Memoria.ia factual-lineage and abstraction
    rules. This is a deterministic architecture benchmark, not a language-model
    quality benchmark.
    """

    # 1) Generated-only hallucination.
    core = EvidenceCore()
    prov = MemoryProvenanceIndex(core)
    _observe(core, prov, "g1", "Atlas", "has_color", "purple", "assistant_generated")
    flat_false_positives = 1  # flat storage exposes the persisted generated claim
    layered_false_positives = int(prov.factual_ultimate_source("g1", namespace="ab") is not None)

    # 2) Correction: historical fact must stop participating in factual state.
    _observe(core, prov, "u1", "Atlas", "has_color", "blue", "user_assertion")
    _observe(core, prov, "u2", "Atlas", "has_color", "green", "user_correction")
    prov.supersede("u1", by_memory_id="u2", namespace="ab")
    flat_stale_facts = 1  # a flat list still contains u1 as an apparently usable row
    layered_stale_facts = int(prov.factual_ultimate_source("u1", namespace="ab") is not None)

    # 3) Conjunctive derivation must die when one premise is corrected.
    _observe(core, prov, "p1", "Motor", "is_a", "machine", "user_assertion")
    _observe(core, prov, "p2", "Motor", "uses", "electricity", "user_assertion")
    core.observe_relation(
        "Motor", "class", "electric-machine",
        evidence_id="d1", source_text="derived", provenance="architecture-ab-benchmark",
        origin="derived_relation", namespace="ab",
    )
    prov.register("d1", source_type="derived_relation", parent_memory_ids=("p1", "p2"), namespace="ab")
    _observe(core, prov, "p2v2", "Motor", "uses", "hydrogen", "user_correction")
    prov.supersede("p2", by_memory_id="p2v2", namespace="ab")
    flat_stale_derivations = 1
    layered_stale_derivations = int(prov.factual_ultimate_source("d1", namespace="ab") is not None)

    # 4) Repeated factual pattern can be represented by one promoted abstraction.
    pattern_core = EvidenceCore()
    pattern_prov = MemoryProvenanceIndex(pattern_core)
    for idx, subject in enumerate(("Alt", "Alt2", "Mia", "Nina"), start=1):
        _observe(pattern_core, pattern_prov, f"cat{idx}", subject, "is_a", "cat", "user_assertion")
    candidates = StructuralAbstractionDetector(pattern_core).discover(namespace="ab", support_level=0)
    cat = next(row for row in candidates if row.predicate == "is_a" and row.object.casefold() == "cat")
    abstraction = FactualConsolidationService(pattern_core).consolidate(
        memory_id="abs-cat",
        subject="pattern:is_a:cat",
        predicate="summarizes",
        object="cat-membership-pattern",
        support_memory_ids=cat.support_memory_ids,
        namespace="ab",
    )
    flat_pattern_context_items = cat.support_count
    layered_pattern_context_items = 1 if abstraction.level == 1 else cat.support_count
    reduction = 1.0 - (layered_pattern_context_items / flat_pattern_context_items)

    flat_errors = flat_false_positives + flat_stale_facts + flat_stale_derivations
    layered_errors = layered_false_positives + layered_stale_facts + layered_stale_derivations
    cases = 3

    return ArchitectureABResult(
        flat_false_positives=flat_false_positives,
        layered_false_positives=layered_false_positives,
        flat_stale_facts=flat_stale_facts,
        layered_stale_facts=layered_stale_facts,
        flat_stale_derivations=flat_stale_derivations,
        layered_stale_derivations=layered_stale_derivations,
        flat_pattern_context_items=flat_pattern_context_items,
        layered_pattern_context_items=layered_pattern_context_items,
        pattern_context_reduction=reduction,
        flat_safety_score=(cases - flat_errors) / cases,
        layered_safety_score=(cases - layered_errors) / cases,
    )


def main() -> None:
    print(json.dumps(asdict(run_architecture_ab()), indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
