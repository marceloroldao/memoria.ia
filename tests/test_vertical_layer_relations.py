from memoria_resolutiva.evidence_core import EvidenceCore
from memoria_resolutiva.factual_consolidation import FactualConsolidationService
from memoria_resolutiva.layer_relations import VerticalLayerRelationService
from memoria_resolutiva.memory_provenance import MemoryProvenanceIndex


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


def test_vertical_edge_connects_adjacent_layers_only():
    core = EvidenceCore()
    prov = MemoryProvenanceIndex(core)
    svc = FactualConsolidationService(core)
    _fact(core, prov, "u1", "A", "is_a", "cat")
    _fact(core, prov, "u2", "B", "is_a", "cat")
    abstraction = svc.consolidate(
        memory_id="a1",
        subject="GroupA",
        predicate="kind",
        object="cat-group",
        support_memory_ids=("u1", "u2"),
        namespace="s",
    )

    edge = VerticalLayerRelationService(core).connect(
        source_memory_id="u1", target_memory_id=abstraction.memory_id, namespace="s"
    )
    assert (edge.source_level, edge.target_level) == (0, 1)


def test_vertical_edge_rejects_same_layer():
    core = EvidenceCore()
    prov = MemoryProvenanceIndex(core)
    _fact(core, prov, "u1", "A", "is_a", "cat")
    _fact(core, prov, "u2", "B", "is_a", "cat")

    try:
        VerticalLayerRelationService(core).connect(
            source_memory_id="u1", target_memory_id="u2", namespace="s"
        )
    except ValueError as exc:
        assert "adjacent levels" in str(exc)
    else:
        raise AssertionError("same-layer relation must not become a vertical edge")


def test_vertical_edges_remain_distinct_from_horizontal_semantics():
    core = EvidenceCore()
    prov = MemoryProvenanceIndex(core)
    svc = FactualConsolidationService(core)
    _fact(core, prov, "u1", "A", "is_a", "cat")
    _fact(core, prov, "u2", "B", "is_a", "cat")
    svc.consolidate(
        memory_id="a1",
        subject="GroupA",
        predicate="kind",
        object="cat-group",
        support_memory_ids=("u1", "u2"),
        namespace="s",
    )
    vertical = VerticalLayerRelationService(core)
    vertical.connect(source_memory_id="u1", target_memory_id="a1", namespace="s")

    rows = vertical.edges(namespace="s")
    assert len(rows) == 1
    assert rows[0].relation_type == "supports_abstraction"
    assert all(edge.predicate != vertical.PREDICATE for edge in core.active_edges(namespace="s") if edge.evidence_id in {"u1", "u2", "a1"})


def test_vertical_edge_rejects_inactive_or_missing_memory():
    core = EvidenceCore()
    try:
        VerticalLayerRelationService(core).connect(
            source_memory_id="missing", target_memory_id="also-missing", namespace="s"
        )
    except ValueError as exc:
        assert "not factually active" in str(exc)
    else:
        raise AssertionError("missing memories cannot form vertical edges")
