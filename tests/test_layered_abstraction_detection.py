from memoria_resolutiva.evidence_core import EvidenceCore
from memoria_resolutiva.factual_consolidation import FactualConsolidationService
from memoria_resolutiva.memory_provenance import MemoryProvenanceIndex
from memoria_resolutiva.structural_abstraction import StructuralAbstractionDetector


def _fact(core, prov, memory_id, subject, predicate, obj):
    core.observe_relation(
        subject,
        predicate,
        obj,
        evidence_id=memory_id,
        source_text=f"{subject} {predicate} {obj}",
        provenance="conversation",
        origin="user",
        namespace="s",
    )
    prov.register(memory_id, source_type="user_assertion", namespace="s")


def test_default_detection_uses_raw_fact_layer_only():
    core = EvidenceCore()
    prov = MemoryProvenanceIndex(core)
    _fact(core, prov, "u1", "Alt", "is_a", "cat")
    _fact(core, prov, "u2", "Alt2", "is_a", "cat")

    rows = StructuralAbstractionDetector(core).discover(namespace="s")
    assert len(rows) == 1
    assert rows[0].support_level == 0
    assert rows[0].candidate_level == 1


def test_level_one_detection_ignores_level_zero_evidence():
    core = EvidenceCore()
    prov = MemoryProvenanceIndex(core)
    svc = FactualConsolidationService(core)
    for mid, subject in (("u1", "A"), ("u2", "B"), ("u3", "C"), ("u4", "D")):
        _fact(core, prov, mid, subject, "is_a", "cat")

    svc.consolidate(memory_id="a1", subject="GroupA", predicate="kind", object="cat-group", support_memory_ids=("u1", "u2"), namespace="s")
    svc.consolidate(memory_id="a2", subject="GroupB", predicate="kind", object="cat-group", support_memory_ids=("u3", "u4"), namespace="s")

    rows = StructuralAbstractionDetector(core).discover(namespace="s", support_level=1)
    assert len(rows) == 1
    assert rows[0].subjects == ("GroupA", "GroupB")
    assert rows[0].support_memory_ids == ("a1", "a2")
    assert rows[0].candidate_level == 2


def test_layers_are_not_mixed_implicitly():
    core = EvidenceCore()
    prov = MemoryProvenanceIndex(core)
    svc = FactualConsolidationService(core)
    _fact(core, prov, "u1", "A", "kind", "shared")
    _fact(core, prov, "u2", "B", "base", "x")
    _fact(core, prov, "u3", "C", "base", "x")
    svc.consolidate(memory_id="a1", subject="Group", predicate="kind", object="shared", support_memory_ids=("u2", "u3"), namespace="s")

    level0 = StructuralAbstractionDetector(core).discover(namespace="s", support_level=0)
    assert len(level0) == 1
    assert level0[0].predicate == "base"
    assert level0[0].support_memory_ids == ("u2", "u3")
    assert "u1" not in level0[0].support_memory_ids
    assert "a1" not in level0[0].support_memory_ids

    level1 = StructuralAbstractionDetector(core).discover(namespace="s", support_level=1)
    assert level1 == ()


def test_negative_support_level_is_rejected():
    core = EvidenceCore()
    try:
        StructuralAbstractionDetector(core).discover(support_level=-1)
    except ValueError as exc:
        assert "support_level" in str(exc)
    else:
        raise AssertionError("negative support level should be rejected")
