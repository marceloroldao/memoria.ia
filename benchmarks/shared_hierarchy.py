from __future__ import annotations

from dataclasses import dataclass

from memoria_resolutiva.evidence_core import EvidenceCore
from memoria_resolutiva.factual_consolidation import FactualConsolidationService
from memoria_resolutiva.memory_provenance import MemoryProvenanceIndex


@dataclass(frozen=True, slots=True)
class SharedHierarchyResult:
    branch_a_before: bool
    branch_b_before: bool
    root_a_before: bool
    root_b_before: bool
    branch_a_after: bool
    branch_b_after: bool
    root_a_after: bool
    root_b_after: bool


def _fact(core: EvidenceCore, prov: MemoryProvenanceIndex, memory_id: str, subject: str, predicate: str, obj: str) -> None:
    core.observe_relation(
        subject,
        predicate,
        obj,
        evidence_id=memory_id,
        source_text=f"{subject} {predicate} {obj}",
        provenance="shared-hierarchy-benchmark",
        origin="user",
        namespace="hier",
    )
    prov.register(memory_id, source_type="user_assertion", namespace="hier")


def run_shared_hierarchy() -> SharedHierarchyResult:
    core = EvidenceCore()
    prov = MemoryProvenanceIndex(core)
    svc = FactualConsolidationService(core, max_level=4)

    _fact(core, prov, "a1", "Alt", "is_a", "cat")
    _fact(core, prov, "a2", "Alt2", "is_a", "cat")
    _fact(core, prov, "b1", "Mia", "is_a", "cat")
    _fact(core, prov, "b2", "Nina", "is_a", "cat")
    _fact(core, prov, "c1", "Rex", "is_a", "dog")
    _fact(core, prov, "c2", "Bolt", "is_a", "dog")

    svc.consolidate(
        memory_id="abs-a",
        subject="GroupA",
        predicate="kind",
        object="cat-group",
        support_memory_ids=("a1", "a2"),
        namespace="hier",
    )
    svc.consolidate(
        memory_id="abs-b",
        subject="GroupB",
        predicate="kind",
        object="cat-group",
        support_memory_ids=("b1", "b2"),
        namespace="hier",
    )
    svc.consolidate(
        memory_id="abs-c",
        subject="GroupC",
        predicate="kind",
        object="dog-group",
        support_memory_ids=("c1", "c2"),
        namespace="hier",
    )

    svc.consolidate(
        memory_id="root-a",
        subject="Cats",
        predicate="groups",
        object="cat-groups",
        support_memory_ids=("abs-a", "abs-b"),
        namespace="hier",
    )
    svc.consolidate(
        memory_id="root-b",
        subject="Mixed",
        predicate="groups",
        object="mixed-groups",
        support_memory_ids=("abs-b", "abs-c"),
        namespace="hier",
    )

    before = dict(
        branch_a_before=prov.factual_ultimate_source("abs-a", namespace="hier") is not None,
        branch_b_before=prov.factual_ultimate_source("abs-b", namespace="hier") is not None,
        root_a_before=prov.factual_ultimate_source("root-a", namespace="hier") is not None,
        root_b_before=prov.factual_ultimate_source("root-b", namespace="hier") is not None,
    )

    _fact(core, prov, "a2v2", "Alt2", "is_a", "dog")
    prov.supersede("a2", by_memory_id="a2v2", namespace="hier")

    return SharedHierarchyResult(
        **before,
        branch_a_after=prov.factual_ultimate_source("abs-a", namespace="hier") is not None,
        branch_b_after=prov.factual_ultimate_source("abs-b", namespace="hier") is not None,
        root_a_after=prov.factual_ultimate_source("root-a", namespace="hier") is not None,
        root_b_after=prov.factual_ultimate_source("root-b", namespace="hier") is not None,
    )
