import json

from memoria_resolutiva.abstraction_relations_v108 import RelationalAbstractionMemoryV108


def _seed_two_abstractions(mem):
    for name, v0, v1 in (("Delta", 10, 20), ("Sigma", 12, 24), ("Kappa", 6, 9)):
        mem.observe(f"A fonte {name} fornece {v0} V ao controlador.")
        mem.observe(f"Agora a fonte {name} fornece {v1} V ao controlador.")
        mem.observe(f"Agora a fonte {name} alimenta cargaA.")
        mem.observe(f"Agora a fonte {name} alimenta cargaB.")
    mem.consolidate_abstractions()
    mem.consolidate_abstractions()
    assert len(mem.abstractions()) >= 2


def test_v108_abstractions_do_not_link_automatically():
    mem = RelationalAbstractionMemoryV108()
    _seed_two_abstractions(mem)
    assert mem.relations() == ()


def test_v108_first_relation_cycle_is_not_enough():
    mem = RelationalAbstractionMemoryV108()
    _seed_two_abstractions(mem)
    assert mem.consolidate_relations() == ()


def test_v108_second_relation_cycle_consolidates_co_support():
    mem = RelationalAbstractionMemoryV108()
    _seed_two_abstractions(mem)
    mem.consolidate_relations()
    relations = mem.consolidate_relations()
    assert relations
    relation = relations[0]
    assert relation.relation == "co_supported"
    assert set(relation.shared_entities) >= {"Delta", "Sigma", "Kappa"}
    assert relation.entity_jaccard >= 0.60
    assert relation.maturity_cycles == 2
    assert relation.evidence_memory_ids


def test_v108_does_not_claim_causality_or_implication():
    mem = RelationalAbstractionMemoryV108()
    _seed_two_abstractions(mem)
    mem.consolidate_relations()
    relations = mem.consolidate_relations()
    assert {r.relation for r in relations} == {"co_supported"}
    assert all(r.kind == "abstraction_relation" for r in relations)


def test_v108_requires_shared_entity_diversity():
    mem = RelationalAbstractionMemoryV108(relation_min_shared_entities=4)
    _seed_two_abstractions(mem)
    mem.consolidate_relations()
    assert mem.consolidate_relations() == ()


def test_v108_persists_relation_clock_and_evidence(tmp_path):
    kwargs = dict(
        path=tmp_path / "semantic.json",
        events_path=tmp_path / "events.json",
        episodes_path=tmp_path / "episodes.json",
        patterns_path=tmp_path / "patterns.json",
        abstractions_path=tmp_path / "abstractions.json",
        relations_path=tmp_path / "relations.json",
    )
    mem = RelationalAbstractionMemoryV108(**kwargs)
    _seed_two_abstractions(mem)
    mem.consolidate_relations()
    assert mem.relations() == ()
    raw = json.loads((tmp_path / "relations.json").read_text(encoding="utf-8"))
    assert raw["schema"] == "abstraction-relations-v108"
    assert raw["maturity"]

    reloaded = RelationalAbstractionMemoryV108(**kwargs)
    relations = reloaded.consolidate_relations()
    assert relations
    assert relations[0].maturity_cycles == 2
    assert relations[0].evidence_memory_ids


def test_v108_preserves_autonomous_retrieval_path():
    mem = RelationalAbstractionMemoryV108()
    mem.observe("Meu carro de teste se chama Orion e a cor dele é verde.")
    result = mem.query("Qual é o nome e a cor do meu carro de teste?")
    assert result.hits
