from memoria_resolutiva.structural_inference_v111 import StructuralInferenceMemoryV111


def test_v111_single_edge_is_returned_as_source_backed_path():
    mem = StructuralInferenceMemoryV111()
    mem.observe("A fonte Delta alimenta o controlador.")
    result = mem.infer_path("Delta", "controlador")
    assert result.inferred
    assert len(result.paths) == 1
    path = result.paths[0]
    assert path.nodes == ("Delta", "controlador")
    assert path.predicates == ("powers",)
    assert path.hops == 1
    assert path.memory_ids
    assert path.source_texts
    assert path.kind == "evidence_path"
    assert path.synthesized_claims == 0


def test_v111_two_hop_path_does_not_synthesize_new_predicate():
    mem = StructuralInferenceMemoryV111()
    mem.observe("A fonte Delta alimenta o controlador.")
    mem.observe("O controlador controlador pertence ao Orion.")
    result = mem.infer_path("Delta", "Orion", max_hops=2)
    assert result.inferred
    path = result.paths[0]
    assert path.predicates == ("powers", "belongs_to")
    assert path.nodes == ("Delta", "controlador", "Orion")
    assert path.synthesized_claims == 0
    assert result.unsupported_claims == 0


def test_v111_hop_limit_blocks_longer_path():
    mem = StructuralInferenceMemoryV111()
    mem.observe("A fonte Delta alimenta o controlador.")
    mem.observe("O controlador controlador pertence ao Orion.")
    assert not mem.infer_path("Delta", "Orion", max_hops=1).inferred


def test_v111_missing_edge_abstains():
    mem = StructuralInferenceMemoryV111()
    mem.observe("A fonte Delta alimenta o controlador.")
    result = mem.infer_path("Delta", "Vega")
    assert not result.inferred
    assert result.paths == ()
    assert result.unsupported_claims == 0


def test_v111_every_path_edge_has_original_memory_evidence():
    mem = StructuralInferenceMemoryV111()
    first = mem.observe("A fonte Delta alimenta o controlador.")
    second = mem.observe("O controlador controlador pertence ao Orion.")
    result = mem.infer_path("Delta", "Orion")
    path = result.paths[0]
    assert set(path.memory_ids) == {first.memory_id, second.memory_id}
    assert all(path.source_texts)


def test_v111_cycle_does_not_loop_forever():
    mem = StructuralInferenceMemoryV111()
    mem.observe("A fonte Delta alimenta o controlador.")
    mem.observe("O controlador controlador pertence ao Delta.")
    result = mem.infer_path("Delta", "controlador", max_hops=5)
    assert result.inferred
    assert all(path.hops <= 5 for path in result.paths)


def test_v111_preserves_original_autonomous_query_path():
    mem = StructuralInferenceMemoryV111()
    mem.observe("Meu carro de teste se chama Orion e a cor dele é verde.")
    result = mem.query("Qual é o nome e a cor do meu carro de teste?")
    assert result.hits
