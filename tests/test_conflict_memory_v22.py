from memoria_resolutiva.conflict_memory import ProvenanceConflictMemory


def test_equal_conflicting_sources_force_abstention():
    m = ProvenanceConflictMemory(decision_margin=0.20)
    m.observe(5, "empresa_a", "diretor", "carlos", source="fonte_a", weight=1.0)
    m.observe(5, "empresa_a", "diretor", "ana", source="fonte_b", weight=1.0)
    state = m.current("empresa_a", "diretor")
    assert state.conflict is True
    assert state.winner is None
    assert state.confidence == 0.5
    assert {value for value, _, _ in state.sources} == {"carlos", "ana"}


def test_strong_evidence_resolves_without_deleting_rival():
    m = ProvenanceConflictMemory(decision_margin=0.20)
    m.observe(5, "empresa_a", "diretor", "carlos", source="fonte_a", weight=1.0)
    m.observe(5, "empresa_a", "diretor", "ana", source="fonte_b", weight=3.0)
    state = m.current("empresa_a", "diretor")
    assert state.conflict is False
    assert state.winner == "ana"
    assert state.confidence == 0.75
    assert len(state.sources) == 2


def test_later_epoch_changes_current_state_but_old_conflict_remains_queryable():
    m = ProvenanceConflictMemory(decision_margin=0.20)
    m.observe(5, "empresa_a", "diretor", "carlos", source="fonte_a")
    m.observe(5, "empresa_a", "diretor", "ana", source="fonte_b")
    old_state = m.resolve_at("empresa_a", "diretor", 5)
    assert old_state.conflict is True

    m.observe(9, "empresa_a", "diretor", "beatriz", source="registro_oficial", weight=5.0)
    current = m.current("empresa_a", "diretor")
    assert current.winner == "beatriz"
    assert current.conflict is False

    old_again = m.resolve_at("empresa_a", "diretor", 5)
    assert old_again.conflict is True
    assert old_again.winner is None
