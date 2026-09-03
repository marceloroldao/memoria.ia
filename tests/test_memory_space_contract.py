import pytest

from memoria_resolutiva.memory_space import MemorySpace, may_be_factual_root, memory_space_for_source_type


@pytest.mark.parametrize(
    ("source_type", "expected"),
    [
        ("user_assertion", MemorySpace.FACTUAL),
        ("user_correction", MemorySpace.FACTUAL),
        ("direct_observation", MemorySpace.FACTUAL),
        ("external_import", MemorySpace.FACTUAL),
        ("derived_relation", MemorySpace.FACTUAL),
        ("assistant_generated", MemorySpace.GENERATIVE),
        ("retrieved_replay", MemorySpace.GENERATIVE),
    ],
)
def test_memory_space_is_deterministic_from_existing_source_type(source_type, expected):
    assert memory_space_for_source_type(source_type) is expected


def test_generated_material_cannot_anchor_factual_state():
    assert not may_be_factual_root("assistant_generated")
    assert not may_be_factual_root("retrieved_replay")


def test_user_and_world_evidence_may_anchor_factual_state():
    assert may_be_factual_root("user_assertion")
    assert may_be_factual_root("user_correction")
    assert may_be_factual_root("direct_observation")
    assert may_be_factual_root("external_import")


def test_empty_source_type_is_rejected():
    with pytest.raises(ValueError):
        memory_space_for_source_type("")
