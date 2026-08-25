from memoria_resolutiva.conflict_aware_inference_v112 import ConflictAwareStructuralMemoryV112


def test_v112_stable_two_hop_path_is_admissible():
    mem = ConflictAwareStructuralMemoryV112()
    mem.observe("A fonte Delta alimenta controlador.")
    mem.observe("O controlador pertence ao Orion.")

    result = mem.infer_path("Delta", "Orion", max_hops=2)
    assert result.inferred
    path = result.paths[0]
    assert path.predicates == ("powers", "belongs_to")
    assert path.edge_statuses == ("stable", "stable")
    assert path.path_confidence == 1.0
    assert path.synthesized_claims == 0


def test_v112_conflicted_predicate_blocks_path():
    mem = ConflictAwareStructuralMemoryV112()
    mem.observe("A fonte Delta alimenta controlador.")
    mem.observe("A fonte Delta alimenta sensor.")
    mem.observe("O controlador pertence ao Orion.")

    result = mem.infer_path("Delta", "Orion", max_hops=2)
    assert not result.inferred
    assert result.paths == ()
    assert result.rejected_conflict_edges >= 2
    assert result.unsupported_claims == 0


def test_v112_explicit_temporal_change_rejects_old_edge_and_accepts_current_edge():
    mem = ConflictAwareStructuralMemoryV112()
    mem.observe("A fonte Delta alimenta controlador.")
    mem.observe("Agora a fonte Delta alimenta sensor.")
    mem.observe("O controlador pertence ao Orion.")
    mem.observe("O sensor pertence ao Vega.")

    old = mem.infer_path("Delta", "Orion", max_hops=2)
    current = mem.infer_path("Delta", "Vega", max_hops=2)

    assert not old.inferred
    assert old.rejected_stale_edges >= 1
    assert current.inferred
    path = current.paths[0]
    assert path.edge_statuses[0] == "current_changed"
    assert path.path_confidence == 0.9


def test_v112_min_path_confidence_can_reject_temporal_change_path():
    mem = ConflictAwareStructuralMemoryV112()
    mem.observe("A fonte Delta alimenta controlador.")
    mem.observe("Agora a fonte Delta alimenta sensor.")
    mem.observe("O sensor pertence ao Vega.")

    result = mem.infer_path("Delta", "Vega", max_hops=2, min_path_confidence=0.95)
    assert not result.inferred


def test_v112_every_admitted_edge_remains_source_backed():
    mem = ConflictAwareStructuralMemoryV112()
    a = mem.observe("A fonte Delta alimenta controlador.")
    b = mem.observe("O controlador pertence ao Orion.")

    result = mem.infer_path("Delta", "Orion", max_hops=2)
    assert result.inferred
    path = result.paths[0]
    assert path.memory_ids == (a.memory_id, b.memory_id)
    assert all(path.source_texts)
    assert path.synthesized_claims == 0


def test_v112_missing_edge_still_abstains():
    mem = ConflictAwareStructuralMemoryV112()
    mem.observe("A fonte Delta alimenta controlador.")
    result = mem.infer_path("Delta", "Orion", max_hops=3)
    assert not result.inferred


def test_v112_preserves_orion_autonomous_retrieval():
    mem = ConflictAwareStructuralMemoryV112()
    mem.observe("Meu carro de teste se chama Orion e a cor dele é verde.")
    result = mem.query("Qual é o nome e a cor do meu carro de teste?")
    assert result.hits
