from memoria_resolutiva.semantic_convergence_v102 import ConvergentSemanticMemoryV102


def _rels(state, predicate):
    return {(r.subject, r.predicate, r.object) for r in state.relations if r.predicate == predicate}


def test_v102_converges_multiple_sentences_on_same_entity():
    mem = ConvergentSemanticMemoryV102()
    mem.observe('A fonte Delta fornece 24 V ao controlador.')
    mem.observe('A fonte Delta alimenta o controlador.')
    mem.observe('A fonte Delta pertence ao Orion.')
    state = mem.entity_state('Delta')
    assert state is not None
    assert 'fonte' in state.kinds
    assert len(state.evidence) == 3
    assert ('Delta', 'has_voltage', '24 V') in _rels(state, 'has_voltage')
    assert ('Delta', 'powers', 'controlador') in _rels(state, 'powers')
    assert ('Delta', 'belongs_to', 'Orion') in _rels(state, 'belongs_to')
    assert state.conflicts == ()


def test_v102_preserves_conflicting_single_value_assertions():
    mem = ConvergentSemanticMemoryV102()
    mem.observe('A fonte Delta fornece 24 V ao controlador.')
    mem.observe('A fonte Delta fornece 48 V ao controlador.')
    state = mem.entity_state('Delta')
    assert state is not None
    values = {r.object for r in state.relations if r.predicate == 'has_voltage'}
    assert values == {'24 V', '48 V'}
    assert state.conflicts == ('has_voltage',)
    assert len(state.evidence) == 2


def test_v102_deduplicates_identical_relations_but_keeps_evidence():
    mem = ConvergentSemanticMemoryV102()
    mem.observe('A fonte Delta alimenta o controlador.')
    mem.observe('A fonte Delta alimenta o controlador.', provenance='repeat')
    state = mem.entity_state('Delta')
    assert state is not None
    powers = [r for r in state.relations if r.predicate == 'powers']
    assert len(powers) == 1
    # The autonomous layer may reinforce an existing memory id. Evidence must
    # remain traceable to at least one original frame.
    assert len(state.evidence) >= 1


def test_v102_persists_and_reloads_relational_state(tmp_path):
    path = tmp_path / 'semantic-v102.json'
    mem = ConvergentSemanticMemoryV102(path=path)
    mem.observe('A fonte Delta fornece 24 V ao controlador.')
    mem.observe('A fonte Delta pertence ao Orion.')
    assert path.exists()

    loaded = ConvergentSemanticMemoryV102(path=path)
    state = loaded.entity_state('Delta')
    assert state is not None
    assert ('Delta', 'has_voltage', '24 V') in _rels(state, 'has_voltage')
    assert ('Delta', 'belongs_to', 'Orion') in _rels(state, 'belongs_to')
    assert len(state.evidence) == 2


def test_v102_keeps_v101_and_v100_retrieval_path():
    mem = ConvergentSemanticMemoryV102()
    mem.observe('Meu carro de teste se chama Orion e a cor dele é verde.')
    result = mem.query('Qual é o nome e a cor do meu carro de teste?')
    assert result.hits
    assert 'Orion' in result.hits[0].text
    assert 'verde' in result.hits[0].text


def test_v102_unknown_entity_abstains():
    mem = ConvergentSemanticMemoryV102()
    mem.observe('A fonte Delta fornece 24 V ao controlador.')
    assert mem.entity_state('EntidadeInexistente') is None
