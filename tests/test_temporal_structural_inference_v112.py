from memoria_resolutiva.temporal_structural_inference_v112 import (
    TemporalStructuralInferenceMemoryV112,
)


def test_v112_later_epoch_supersedes_single_value_relation_without_erasing_history():
    mem = TemporalStructuralInferenceMemoryV112()
    mem.observe("O controlador Delta pertence ao Orion.", epoch=0)
    mem.observe("O controlador Delta pertence ao Vega.", epoch=1)

    assert mem.infer_path("Delta", "Orion", epoch=0).inferred
    assert not mem.infer_path("Delta", "Orion").inferred
    assert mem.infer_path("Delta", "Vega").inferred
    assert not mem.conflicts()


def test_v112_same_epoch_single_value_disagreement_abstains():
    mem = TemporalStructuralInferenceMemoryV112()
    mem.observe("O controlador Delta pertence ao Orion.", epoch=3)
    mem.observe("O controlador Delta pertence ao Vega.", epoch=3)

    conflicts = mem.conflicts()
    assert len(conflicts) == 1
    assert conflicts[0].subject == "Delta"
    assert conflicts[0].predicate == "belongs_to"
    assert set(conflicts[0].values) == {"Orion", "Vega"}
    assert not mem.infer_path("Delta", "Orion").inferred
    assert not mem.infer_path("Delta", "Vega").inferred


def test_v112_newer_epoch_resolves_previous_same_epoch_conflict():
    mem = TemporalStructuralInferenceMemoryV112()
    mem.observe("O controlador Delta pertence ao Orion.", epoch=3)
    mem.observe("O controlador Delta pertence ao Vega.", epoch=3)
    mem.observe("O controlador Delta pertence ao Lyra.", epoch=4)

    assert mem.conflicts(epoch=3)
    assert not mem.conflicts()
    assert mem.infer_path("Delta", "Lyra").inferred
    assert not mem.infer_path("Delta", "Orion").inferred
    assert not mem.infer_path("Delta", "Vega").inferred


def test_v112_multivalued_powers_relation_is_not_false_conflict():
    mem = TemporalStructuralInferenceMemoryV112()
    mem.observe("A fonte Delta alimenta o controlador.", epoch=2)
    mem.observe("A fonte Delta alimenta o sensor.", epoch=2)

    assert not mem.conflicts()
    assert mem.infer_path("Delta", "controlador").inferred
    assert mem.infer_path("Delta", "sensor").inferred


def test_v112_temporal_state_is_namespace_scoped():
    mem = TemporalStructuralInferenceMemoryV112()
    mem.observe("O controlador Delta pertence ao Orion.", namespace="alpha", epoch=0)
    mem.observe("O controlador Delta pertence ao Vega.", namespace="beta", epoch=0)

    assert mem.infer_path("Delta", "Orion", namespace="alpha").inferred
    assert not mem.infer_path("Delta", "Vega", namespace="alpha").inferred
    assert mem.infer_path("Delta", "Vega", namespace="beta").inferred
    assert not mem.conflicts(namespace="alpha")
    assert not mem.conflicts(namespace="beta")


def test_v112_default_epoch_advances_as_state_change():
    mem = TemporalStructuralInferenceMemoryV112()
    mem.observe("O controlador Delta pertence ao Orion.")
    mem.observe("O controlador Delta pertence ao Vega.")

    assert mem.infer_path("Delta", "Vega").inferred
    assert not mem.infer_path("Delta", "Orion").inferred
    assert mem.infer_path("Delta", "Orion", epoch=0).inferred


def test_v112_preserves_v111_multihop_structural_path():
    mem = TemporalStructuralInferenceMemoryV112()
    mem.observe("A fonte Delta alimenta o controlador.", epoch=0)
    mem.observe("O controlador controlador pertence ao Orion.", epoch=1)

    result = mem.infer_path("Delta", "Orion")
    assert result.inferred
    assert result.paths[0].predicates == ("powers", "belongs_to")
    assert result.paths[0].synthesized_claims == 0
