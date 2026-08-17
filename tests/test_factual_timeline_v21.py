from memoria_resolutiva.factual_timeline import FactualTimelineMemory


def build_memory():
    m = FactualTimelineMemory()
    m.observe(1, "empresa_a", "diretor", "joao")
    m.observe(5, "empresa_a", "diretor", "carlos")
    m.observe(9, "empresa_a", "diretor", "ana")
    return m


def test_current_and_historical_queries_are_distinct():
    m = build_memory()
    assert m.current("empresa_a", "diretor").value == "ana"
    assert m.at("empresa_a", "diretor", 1).value == "joao"
    assert m.at("empresa_a", "diretor", 7).value == "carlos"


def test_old_facts_are_preserved_after_updates():
    m = build_memory()
    assert [(e.epoch, e.value) for e in m.history("empresa_a", "diretor")] == [
        (1, "joao"), (5, "carlos"), (9, "ana")
    ]


def test_supersession_time_and_transitions():
    m = build_memory()
    assert m.superseded_at("empresa_a", "diretor", "joao") == 5
    assert m.superseded_at("empresa_a", "diretor", "carlos") == 9
    transitions = m.transitions("empresa_a", "diretor")
    assert [(a.value, b.value, b.epoch) for a, b in transitions] == [
        ("joao", "carlos", 5), ("carlos", "ana", 9)
    ]
