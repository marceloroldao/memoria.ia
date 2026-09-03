from memoria_resolutiva.evidence_core import EvidenceCore
from memoria_resolutiva.factual_inference import FactualInferenceService
from memoria_resolutiva.memory_provenance import MemoryProvenanceIndex


def _edge(core: EvidenceCore, subject: str, predicate: str, obj: str, evidence_id: str, *, origin: str = "user"):
    return core.observe_relation(
        subject,
        predicate,
        obj,
        evidence_id=evidence_id,
        source_text=f"{subject} {predicate} {obj}",
        provenance="conversation",
        origin=origin,
        confidence=1.0,
        namespace="s",
    )


def test_factual_chain_infers_when_all_premises_have_factual_roots():
    core = EvidenceCore()
    prov = MemoryProvenanceIndex(core)
    _edge(core, "A", "linked_to", "B", "u1")
    _edge(core, "B", "linked_to", "C", "u2")
    prov.register("u1", source_type="user_assertion", namespace="s")
    prov.register("u2", source_type="user_assertion", namespace="s")

    result = FactualInferenceService(core).infer_path("A", "C", namespace="s")
    assert result.inferred is True
    assert result.paths[0].evidence_ids == ("u1", "u2")


def test_generated_premise_cannot_complete_factual_chain():
    core = EvidenceCore()
    prov = MemoryProvenanceIndex(core)
    _edge(core, "A", "linked_to", "B", "u1")
    _edge(core, "B", "linked_to", "C", "a1", origin="assistant")
    prov.register("u1", source_type="user_assertion", namespace="s")
    prov.register("a1", source_type="assistant_generated", namespace="s")

    assert core.infer_path("A", "C", namespace="s").inferred is True
    result = FactualInferenceService(core).infer_path("A", "C", namespace="s")
    assert result.inferred is False
    assert result.paths == ()


def test_generated_relation_with_explicit_user_root_remains_factual_lineage():
    core = EvidenceCore()
    prov = MemoryProvenanceIndex(core)
    prov.register("root-user", source_type="user_assertion", namespace="s")
    _edge(core, "A", "linked_to", "B", "a1", origin="assistant")
    prov.register(
        "a1",
        source_type="assistant_generated",
        parent_memory_ids=("root-user",),
        namespace="s",
    )

    result = FactualInferenceService(core).infer_path("A", "B", namespace="s")
    assert result.inferred is True
    assert result.paths[0].evidence_ids == ("a1",)


def test_unregistered_generic_evidence_remains_available_to_generic_core_only():
    core = EvidenceCore()
    _edge(core, "A", "linked_to", "B", "legacy")

    assert core.infer_path("A", "B", namespace="s").inferred is True
    assert FactualInferenceService(core).infer_path("A", "B", namespace="s").inferred is False


def test_derived_relation_is_invalidated_when_any_required_parent_is_superseded():
    core = EvidenceCore()
    prov = MemoryProvenanceIndex(core)

    prov.register("premise-a", source_type="user_assertion", namespace="s")
    prov.register("premise-b", source_type="user_assertion", namespace="s")
    _edge(core, "A", "derived_link", "C", "derived")
    prov.register(
        "derived",
        source_type="derived_relation",
        parent_memory_ids=("premise-a", "premise-b"),
        namespace="s",
    )

    before = FactualInferenceService(core).infer_path("A", "C", namespace="s")
    assert before.inferred is True
    assert prov.factual_ultimate_source("derived", namespace="s") is not None

    prov.register("premise-b-corrected", source_type="user_correction", namespace="s")
    prov.supersede("premise-b", by_memory_id="premise-b-corrected", namespace="s")

    # The relation stays in history/audit storage, but its old conjunction is no
    # longer a current factual premise until the derivation is recomputed.
    assert core.infer_path("A", "C", namespace="s").inferred is True
    assert prov.factual_ultimate_source("derived", namespace="s") is None
    after = FactualInferenceService(core).infer_path("A", "C", namespace="s")
    assert after.inferred is False
    assert after.paths == ()
