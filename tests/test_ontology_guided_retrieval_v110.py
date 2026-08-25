from memoria_resolutiva.ontology_guided_retrieval_v110 import OntologyGuidedMemoryV110


def _seed(mem):
    for name, v0, v1 in (("Delta", 10, 20), ("Sigma", 12, 24), ("Kappa", 6, 9)):
        mem.observe(f"A fonte {name} fornece {v0} V ao controlador.")
        mem.observe(f"Agora a fonte {name} fornece {v1} V ao controlador.")
        mem.observe(f"A fonte {name} alimenta cargaA.")
        mem.observe(f"Agora a fonte {name} alimenta cargaB.")
        mem.observe(f"A fonte {name} pertence ao Orion.")
        mem.observe(f"Agora a fonte {name} pertence ao Vega.")
    mem.consolidate_abstractions()
    mem.consolidate_abstractions()
    mem.consolidate_relations()
    mem.consolidate_relations()
    mem.consolidate_ontology()
    mem.consolidate_ontology()
    assert mem.ontology.ontologies()


def test_v110_without_ontology_guided_path_abstains():
    mem = OntologyGuidedMemoryV110()
    mem.observe("A fonte Delta fornece 10 V ao controlador.")
    result = mem.guided_query("Qual é a tensão?")
    assert not result.ontology_used
    assert result.guided_evidence == ()
    assert result.synthesized_claims == 0


def test_v110_candidate_ontology_routes_voltage_to_original_evidence():
    mem = OntologyGuidedMemoryV110()
    _seed(mem)
    result = mem.guided_query("Mostre o histórico de tensão.", top_k=3)
    assert result.ontology_used
    assert "has_voltage" in result.matched_predicates
    assert result.guided_evidence
    assert all(item.kind == "source_evidence" for item in result.guided_evidence)
    assert all(item.predicate == "has_voltage" for item in result.guided_evidence)
    assert all("fornece" in item.text.casefold() for item in result.guided_evidence)
    assert result.synthesized_claims == 0


def test_v110_guided_evidence_ids_exist_in_original_memory():
    mem = OntologyGuidedMemoryV110()
    _seed(mem)
    result = mem.guided_query("Quero evidências sobre tensão.", top_k=10)
    base = mem._base_memory()
    known = {record.memory_id for record in base.records()}
    assert {item.memory_id for item in result.guided_evidence}.issubset(known)


def test_v110_unknown_semantic_request_does_not_use_ontology():
    mem = OntologyGuidedMemoryV110()
    _seed(mem)
    result = mem.guided_query("Explique a beleza do sistema.")
    assert not result.ontology_used
    assert result.guided_evidence == ()
    assert result.synthesized_claims == 0


def test_v110_does_not_emit_causal_or_taxonomic_claims():
    mem = OntologyGuidedMemoryV110()
    _seed(mem)
    result = mem.guided_query("A tensão causa alimentação?")
    blob = repr(result).casefold()
    assert "source_evidence" in blob
    assert result.synthesized_claims == 0
    assert not hasattr(result, "causes")
    assert not hasattr(result, "is_a")


def test_v110_direct_retrieval_is_preserved():
    mem = OntologyGuidedMemoryV110()
    mem.observe("Meu carro de teste se chama Orion e a cor dele é verde.")
    result = mem.guided_query("Qual é o nome e a cor do meu carro de teste?")
    assert result.direct_result.hits


def test_v110_top_k_caps_evidence_not_truth():
    mem = OntologyGuidedMemoryV110()
    _seed(mem)
    result = mem.guided_query("tensão", top_k=1)
    assert len(result.guided_evidence) <= 1
    assert result.synthesized_claims == 0
