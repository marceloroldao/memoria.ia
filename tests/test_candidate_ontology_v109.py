import json

from memoria_resolutiva.candidate_ontology_v109 import CandidateOntologyMemoryV109


def _seed_three_abstractions(mem):
    for name, v0, v1 in (("Delta", 10, 20), ("Sigma", 12, 24), ("Kappa", 6, 9)):
        mem.observe(f"A fonte {name} fornece {v0} V ao controlador.")
        mem.observe(f"Agora a fonte {name} fornece {v1} V ao controlador.")
        mem.observe(f"A fonte {name} alimenta cargaA.")
        mem.observe(f"Agora a fonte {name} alimenta cargaB.")
        mem.observe(f"A fonte {name} pertence ao Orion.")
        mem.observe(f"Agora a fonte {name} pertence ao Vega.")
    mem.consolidate_abstractions()
    mem.consolidate_abstractions()
    assert len(mem.abstractions()) >= 3
    mem.consolidate_relations()
    mem.consolidate_relations()
    assert len(mem.relations()) >= 3


def test_v109_relations_do_not_create_ontology_automatically():
    mem = CandidateOntologyMemoryV109()
    _seed_three_abstractions(mem)
    assert mem.ontologies() == ()


def test_v109_first_ontology_cycle_is_not_enough():
    mem = CandidateOntologyMemoryV109()
    _seed_three_abstractions(mem)
    assert mem.consolidate_ontology() == ()


def test_v109_second_cycle_creates_candidate_only():
    mem = CandidateOntologyMemoryV109()
    _seed_three_abstractions(mem)
    mem.consolidate_ontology()
    ontologies = mem.consolidate_ontology()
    assert len(ontologies) == 1
    item = ontologies[0]
    assert item.status == "candidate"
    assert item.kind == "candidate_ontology"
    assert len(item.abstraction_ids) >= 3
    assert len(item.relation_ids) >= 3
    assert set(item.shared_entities) >= {"Delta", "Sigma", "Kappa"}
    assert item.graph_density >= 0.50
    assert item.maturity_cycles == 2
    assert item.evidence_memory_ids


def test_v109_never_claims_causality_taxonomy_or_truth():
    mem = CandidateOntologyMemoryV109()
    _seed_three_abstractions(mem)
    mem.consolidate_ontology()
    item = mem.consolidate_ontology()[0]
    serialized = json.dumps(item.__dict__ if hasattr(item, "__dict__") else {
        "status": item.status,
        "kind": item.kind,
        "predicates": item.predicates,
    }).casefold()
    assert "causes" not in serialized
    assert "implies" not in serialized
    assert "is_a" not in serialized
    assert "universal" not in serialized


def test_v109_requires_three_abstractions():
    mem = CandidateOntologyMemoryV109(ontology_min_abstractions=4)
    _seed_three_abstractions(mem)
    mem.consolidate_ontology()
    assert mem.consolidate_ontology() == ()


def test_v109_requires_shared_entity_diversity():
    mem = CandidateOntologyMemoryV109(ontology_min_shared_entities=4)
    _seed_three_abstractions(mem)
    mem.consolidate_ontology()
    assert mem.consolidate_ontology() == ()


def test_v109_persists_slow_clock_and_traceability(tmp_path):
    kwargs = dict(
        path=tmp_path / "semantic.json",
        events_path=tmp_path / "events.json",
        episodes_path=tmp_path / "episodes.json",
        patterns_path=tmp_path / "patterns.json",
        abstractions_path=tmp_path / "abstractions.json",
        relations_path=tmp_path / "relations.json",
        ontology_path=tmp_path / "ontology.json",
    )
    mem = CandidateOntologyMemoryV109(**kwargs)
    _seed_three_abstractions(mem)
    assert mem.consolidate_ontology() == ()

    reloaded = CandidateOntologyMemoryV109(**kwargs)
    ontologies = reloaded.consolidate_ontology()
    assert len(ontologies) == 1
    item = ontologies[0]
    assert item.maturity_cycles == 2
    assert item.evidence_memory_ids

    raw = json.loads((tmp_path / "ontology.json").read_text(encoding="utf-8"))
    assert raw["schema"] == "candidate-ontology-v109"
    assert raw["ontologies"][0]["status"] == "candidate"


def test_v109_preserves_autonomous_retrieval_path():
    mem = CandidateOntologyMemoryV109()
    mem.observe("Meu carro de teste se chama Orion e a cor dele é verde.")
    result = mem.query("Qual é o nome e a cor do meu carro de teste?")
    assert result.hits
