import pytest

from memoria_resolutiva.evidence_core import EvidenceCore
from memoria_resolutiva.memory_promotion import MemoryPromotionService
from memoria_resolutiva.memory_provenance import MemoryProvenanceIndex
from memoria_resolutiva.memory_space import MemorySpace, memory_space_for_source_type


def _index():
    core = EvidenceCore()
    return core, MemoryProvenanceIndex(core)


def test_generated_candidate_cannot_self_promote():
    _core, index = _index()
    index.register("g1", source_type="assistant_generated", created_order=1, namespace="s")
    service = MemoryPromotionService(index)

    with pytest.raises(ValueError, match="independent active factual validation"):
        service.promote(
            "g1",
            validating_memory_id="g1",
            promoted_memory_id="p1",
            created_order=2,
            namespace="s",
        )


def test_generated_candidate_can_be_promoted_by_independent_user_evidence():
    _core, index = _index()
    index.register("g1", source_type="assistant_generated", created_order=1, namespace="s")
    index.register("u1", source_type="user_assertion", created_order=2, namespace="s")
    service = MemoryPromotionService(index)

    result = service.promote(
        "g1",
        validating_memory_id="u1",
        promoted_memory_id="p1",
        created_order=3,
        namespace="s",
    )

    assert result.memory_space is MemorySpace.FACTUAL
    assert result.source_type == "user_assertion"
    assert service.inspect_candidate("g1", namespace="s").source_type == "assistant_generated"
    assert memory_space_for_source_type(service.inspect_candidate("g1", namespace="s").source_type) is MemorySpace.GENERATIVE
    assert service.candidate_for_promotion("p1", namespace="s") == "g1"
    promoted = index.inspect("p1", namespace="s")
    assert promoted.parent_memory_ids == ("u1",)
    assert index.factual_ultimate_source("p1", namespace="s").memory_id == "u1"


def test_factual_record_is_not_accepted_as_generative_candidate():
    _core, index = _index()
    index.register("u1", source_type="user_assertion", created_order=1, namespace="s")
    index.register("u2", source_type="user_correction", created_order=2, namespace="s")
    service = MemoryPromotionService(index)

    with pytest.raises(ValueError, match="candidate must belong to generative memory space"):
        service.promote(
            "u1",
            validating_memory_id="u2",
            promoted_memory_id="p1",
            created_order=3,
            namespace="s",
        )
