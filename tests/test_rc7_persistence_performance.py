from __future__ import annotations

from types import SimpleNamespace

from memoria_resolutiva.evidence_core import EvidenceCore
from memoria_resolutiva.product_identity import MemoryScope, OrganizationIdentity
from memoria_resolutiva.product_persistence import (
    PersistentEnterpriseMemoryService,
    ProductSnapshotPersistence,
)
from memoria_resolutiva.relational_activation import activate


class Resolver:
    def __init__(self, core: EvidenceCore):
        self.evidence = SimpleNamespace(core=core)


def _observe(core, subject, predicate, object_, evidence_id, confidence=1.0, namespace="rc7:e"):
    core.observe_relation(
        subject,
        predicate,
        object_,
        evidence_id=evidence_id,
        source_text=f"{subject} {predicate} {object_}",
        confidence=confidence,
        namespace=namespace,
    )


def test_rc7_sqlite_restart_is_idempotent_across_multiple_boots(tmp_path):
    state = tmp_path / "state"
    durable = tmp_path / "durable"
    persistence = ProductSnapshotPersistence(durable, backend="sqlite", allow_fallback=False)
    service = PersistentEnterpriseMemoryService(
        OrganizationIdentity("org-a", "Org A"),
        persistence=persistence,
    )
    scope = MemoryScope("org-a")
    service.remember(scope, "vehicle-color", "blue", ("profile", "vehicle", "color"), provenance="test")
    service.save(state)

    first = PersistentEnterpriseMemoryService.load(
        state,
        persistence=ProductSnapshotPersistence(durable, backend="sqlite", allow_fallback=False),
    )
    first_record = first.recall(scope, ("profile", "vehicle", "color"))
    assert first_record is not None and first_record.payload == "blue"
    assert first.statistics["persistence_backend"] == "sqlite"
    assert first.statistics["portable_snapshot_fallback"] is False
    first.save(state)

    second = PersistentEnterpriseMemoryService.load(
        state,
        persistence=ProductSnapshotPersistence(durable, backend="sqlite", allow_fallback=False),
    )
    second_record = second.recall(scope, ("profile", "vehicle", "color"))
    assert second_record is not None and second_record.payload == "blue"
    assert second.statistics["persistence_backend"] == "sqlite"
    assert second.statistics["portable_snapshot_fallback"] is False


def test_rc7_repeated_semantic_activation_is_read_only_and_non_amplifying():
    core = EvidenceCore()
    _observe(core, "root", "rel", "mid", "e1", confidence=1.0)
    _observe(core, "mid", "attr", "value", "e2", confidence=0.9)
    resolver = Resolver(core)

    before = tuple(
        (edge.subject, edge.predicate, edge.object, edge.evidence_id, edge.confidence)
        for edge in core.active_edges(namespace="rc7:e")
    )

    outputs = []
    for _ in range(5):
        result = activate(
            resolver,
            concept="root",
            session_id="rc7:e",
            depth=2,
            budget=1200,
            hop_decay=0.72,
            min_confidence=0.45,
        )
        outputs.append((result.status, result.selected_context, result.concepts, result.memory_ids, result.confidence))

    after = tuple(
        (edge.subject, edge.predicate, edge.object, edge.evidence_id, edge.confidence)
        for edge in core.active_edges(namespace="rc7:e")
    )

    assert all(output == outputs[0] for output in outputs[1:])
    assert before == after
    assert outputs[0][0] == "HIT"
    assert outputs[0][1].splitlines() == ["root | rel | mid", "mid | attr | value"]
    assert outputs[0][3] == ("e1", "e2")
