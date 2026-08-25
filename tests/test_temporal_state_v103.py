from memoria_resolutiva.temporal_state_v103 import TemporalSemanticMemoryV103


def test_v103_stable_single_value():
    mem = TemporalSemanticMemoryV103()
    mem.observe('A fonte Delta fornece 24 V ao controlador.')
    state = mem.predicate_state('Delta', 'has_voltage')
    assert state is not None
    assert state.status == 'stable'
    assert state.current == ('24 V',)


def test_v103_unmarked_incompatible_value_is_conflict():
    mem = TemporalSemanticMemoryV103()
    mem.observe('A fonte Delta fornece 24 V ao controlador.')
    mem.observe('A fonte Delta fornece 48 V ao controlador.')
    state = mem.predicate_state('Delta', 'has_voltage')
    assert state is not None
    assert state.status == 'conflict'
    assert set(state.current) == {'24 V', '48 V'}
    assert state.history == ('24 V', '48 V')


def test_v103_explicit_temporal_update_changes_current_and_keeps_history():
    mem = TemporalSemanticMemoryV103()
    mem.observe('A fonte Delta fornece 24 V ao controlador.')
    mem.observe('Agora a fonte Delta fornece 48 V ao controlador.')
    state = mem.predicate_state('Delta', 'has_voltage')
    assert state is not None
    assert state.status == 'changed'
    assert state.current == ('48 V',)
    assert state.history == ('24 V', '48 V')
    assert len(state.evidence_ids) == 2


def test_v103_entity_state_exposes_temporal_predicates():
    mem = TemporalSemanticMemoryV103()
    mem.observe('O sensor Alfa mede temperatura na sala norte.')
    state = mem.entity_state('Alfa')
    assert state is not None
    predicates = {p.predicate: p for p in state.predicates}
    assert predicates['measures'].status == 'stable'
    assert predicates['located_at'].status == 'stable'


def test_v103_preserves_retrieval_path():
    mem = TemporalSemanticMemoryV103()
    mem.observe('Meu carro de teste se chama Orion e a cor dele é verde.')
    result = mem.query('Qual é o nome e a cor do meu carro de teste?')
    assert result.hits
