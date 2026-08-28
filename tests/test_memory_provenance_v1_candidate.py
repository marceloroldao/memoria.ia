from memoria_resolutiva.evidence_core import EvidenceCore
from memoria_resolutiva.memory_provenance import MemoryProvenanceIndex, ProvenanceCandidate


def test_user_source_beats_assistant_echo_even_with_lower_similarity():
    core = EvidenceCore()
    index = MemoryProvenanceIndex(core)
    index.register("user-fact", source_type="user_assertion", created_order=1, namespace="s")
    index.register("assistant-echo", source_type="assistant_generated", parent_memory_ids=("user-fact",), created_order=2, namespace="s")
    selected = index.select([
        ProvenanceCandidate("assistant-echo", 0.99, 2),
        ProvenanceCandidate("user-fact", 0.80, 1),
    ], namespace="s")
    assert selected is not None
    assert selected.memory_id == "user-fact"


def test_repeated_assistant_answers_do_not_gain_authority():
    core = EvidenceCore()
    index = MemoryProvenanceIndex(core)
    index.register("user-fact", source_type="user_assertion", created_order=1, namespace="s")
    for i in range(20):
        index.register(f"echo-{i}", source_type="assistant_generated", parent_memory_ids=("user-fact",), created_order=2 + i, namespace="s")
    candidates = [ProvenanceCandidate(f"echo-{i}", 1.0, 2 + i) for i in range(20)]
    candidates.append(ProvenanceCandidate("user-fact", 0.60, 1))
    selected = index.select(candidates, namespace="s")
    assert selected is not None
    assert selected.memory_id == "user-fact"
    assert index.inspect("echo-19", namespace="s").authority == index.inspect("echo-0", namespace="s").authority


def test_user_correction_supersedes_wrong_generated_answer():
    core = EvidenceCore()
    index = MemoryProvenanceIndex(core)
    index.register("wrong", source_type="assistant_generated", created_order=1, namespace="s")
    index.register("correction", source_type="user_correction", parent_memory_ids=("wrong",), created_order=2, namespace="s")
    index.supersede("wrong", by_memory_id="correction", namespace="s")
    selected = index.select([
        ProvenanceCandidate("wrong", 1.0, 1),
        ProvenanceCandidate("correction", 0.70, 2),
    ], namespace="s")
    assert selected is not None
    assert selected.memory_id == "correction"
    assert index.inspect("wrong", namespace="s").superseded_by == "correction"


def test_provenance_survives_evidence_replay():
    core = EvidenceCore()
    index = MemoryProvenanceIndex(core)
    index.register("source", source_type="direct_observation", created_order=7, created_time="2026-08-28T12:00:00Z", namespace="s")
    index.register("derived", source_type="derived_relation", parent_memory_ids=("source",), created_order=8, namespace="s")

    replay = EvidenceCore()
    for edge in core._edges:
        replay.observe_relation(edge.subject, edge.predicate, edge.object, evidence_id=edge.evidence_id, source_text=edge.source_text, provenance=edge.provenance, origin=edge.origin, confidence=edge.confidence, namespace=edge.namespace, epoch=edge.epoch)
    restored = MemoryProvenanceIndex(replay).inspect("derived", namespace="s")
    assert restored.source_type == "derived_relation"
    assert restored.parent_memory_ids == ("source",)
    assert restored.created_order == 8


def test_generated_only_evidence_remains_explicitly_generated():
    core = EvidenceCore()
    index = MemoryProvenanceIndex(core)
    index.register("generated", source_type="assistant_generated", created_order=1, namespace="s")
    meta = index.inspect("generated", namespace="s")
    assert meta.source_type == "assistant_generated"
    assert meta.authority < index.authority_for("user_assertion")
