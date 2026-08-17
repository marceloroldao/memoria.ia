from memoria_resolutiva.temporal_memory import TemporalContextMemory


def test_temporal_memory_preserves_history_and_favors_recent_relation():
    memory = TemporalContextMemory(radius=2, decay=1.0)
    old = [
        "rota conecta margens do rio",
        "ponte conecta margens do rio",
        "cidade usa rota durante travessia",
        "cidade usa ponte durante travessia",
    ] * 20
    new = [
        "rota conecta margens do rio",
        "tunel conecta margens do rio",
        "cidade usa rota durante travessia",
        "cidade usa tunel durante travessia",
    ] * 40

    e0 = memory.add_epoch(old, label="old")
    assert memory.similarity_at(e0, "rota", "ponte") > 0.9

    memory.add_epoch(new, label="new")

    assert memory.current_similarity("rota", "tunel") > memory.current_similarity("rota", "ponte")
    assert memory.similarity_at(e0, "rota", "ponte") > 0.9
    assert memory.change_score("rota", "ponte", "tunel") > 0.0


def test_empty_temporal_memory_is_safe():
    memory = TemporalContextMemory()
    assert memory.current_similarity("a", "b") == 0.0
    assert memory.nearest_current("a") == []
