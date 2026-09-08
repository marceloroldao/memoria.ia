import pytest

from memoria_resolutiva.evidence_core import EvidenceCore
from memoria_resolutiva.memory_promotion import MemoryPromotionService
from memoria_resolutiva.memory_provenance import MemoryProvenanceIndex, ProvenanceCandidate


def _index():
    core = EvidenceCore()
    return core, MemoryProvenanceIndex(core)


def test_rc7_generated_root_never_wins_factual_selection_even_with_higher_confidence():
    _core, index = _index()
    index.register("assistant", source_type="assistant_generated", created_order=9, namespace="user-a")
    index.register("user", source_type="user_assertion", created_order=1, namespace="user-a")

    selected = index.select(
        [
            ProvenanceCandidate("assistant", confidence=1.0, created_order=9),
            ProvenanceCandidate("user", confidence=0.51, created_order=1),
        ],
        namespace="user-a",
    )

    assert selected is not None
    assert selected.memory_id == "user"


def test_rc7_promotion_rejects_validator_from_other_namespace():
    _core, index = _index()
    index.register("candidate", source_type="assistant_generated", created_order=1, namespace="user-a")
    index.register("validator", source_type="user_assertion", created_order=2, namespace="user-b")
    service = MemoryPromotionService(index)

    with pytest.raises(ValueError, match="independent active factual validation"):
        service.promote(
            "candidate",
            validating_memory_id="validator",
            promoted_memory_id="promoted",
            created_order=3,
            namespace="user-a",
        )


def test_rc7_generated_echo_with_factual_parent_does_not_replace_root_representative():
    _core, index = _index()
    index.register("root", source_type="user_assertion", created_order=1, namespace="user-a")
    index.register(
        "echo",
        source_type="assistant_generated",
        parent_memory_ids=("root",),
        created_order=2,
        namespace="user-a",
    )

    selected = index.select(
        [
            ProvenanceCandidate("echo", confidence=1.0, created_order=2),
            ProvenanceCandidate("root", confidence=0.6, created_order=1),
        ],
        namespace="user-a",
    )

    assert selected is not None
    assert selected.memory_id == "root"
    assert index.factual_ultimate_source("echo", namespace="user-a").memory_id == "root"


def test_rc7_superseded_root_invalidates_generated_echo_lineage():
    _core, index = _index()
    index.register("old", source_type="user_assertion", created_order=1, namespace="user-a")
    index.register(
        "echo",
        source_type="assistant_generated",
        parent_memory_ids=("old",),
        created_order=2,
        namespace="user-a",
    )
    index.register("new", source_type="user_correction", created_order=3, namespace="user-a")
    index.supersede("old", by_memory_id="new", namespace="user-a")

    assert not index.has_active_factual_lineage("echo", namespace="user-a")
    assert index.factual_ultimate_source("echo", namespace="user-a") is None
    selected = index.select(
        [
            ProvenanceCandidate("echo", confidence=1.0, created_order=2),
            ProvenanceCandidate("new", confidence=0.8, created_order=3),
        ],
        namespace="user-a",
    )
    assert selected is not None
    assert selected.memory_id == "new"


def test_rc7_external_import_keeps_declared_authority_class():
    _core, index = _index()
    imported = index.register("public", source_type="external_import", created_order=1, namespace="user-a")

    assert imported.source_type == "external_import"
    assert imported.authority == index.authority_for("external_import")
    assert index.factual_ultimate_source("public", namespace="user-a").memory_id == "public"
