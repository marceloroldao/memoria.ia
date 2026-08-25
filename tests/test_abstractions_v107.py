from memoria_resolutiva.abstractions_v107 import AbstractionSemanticMemoryV107


def _add_up_episode(mem, entity: str, before: int, after: int) -> None:
    mem.observe(f'A fonte {entity} fornece {before} V ao controlador.')
    mem.observe(f'Agora a fonte {entity} fornece {after} V ao controlador.')


def test_v107_two_entity_candidate_never_reaches_stronger_abstraction_gate():
    mem = AbstractionSemanticMemoryV107()
    _add_up_episode(mem, 'Delta', 24, 48)
    _add_up_episode(mem, 'Sigma', 12, 18)
    assert len(mem.patterns()) == 1
    mem.consolidate()
    mem.consolidate()
    mem.consolidate()
    assert mem.abstractions() == ()


def test_v107_eligible_pattern_is_not_promoted_on_observation_clock():
    mem = AbstractionSemanticMemoryV107()
    _add_up_episode(mem, 'Delta', 24, 48)
    _add_up_episode(mem, 'Sigma', 12, 18)
    _add_up_episode(mem, 'Kappa', 6, 9)
    assert len(mem.patterns()) == 1
    assert mem.patterns()[0].support == 3
    assert mem.abstractions() == ()


def test_v107_requires_two_explicit_slow_consolidation_cycles():
    mem = AbstractionSemanticMemoryV107()
    _add_up_episode(mem, 'Delta', 24, 48)
    _add_up_episode(mem, 'Sigma', 12, 18)
    _add_up_episode(mem, 'Kappa', 6, 9)
    signature = mem.patterns()[0].signature

    mem.consolidate()
    assert mem.maturity_for_signature(signature) == 1
    assert mem.abstractions() == ()

    mem.consolidate()
    abstractions = mem.abstractions()
    assert len(abstractions) == 1
    abstraction = abstractions[0]
    assert abstraction.status == 'consolidated'
    assert abstraction.support == 3
    assert set(abstraction.entities) == {'Delta', 'Sigma', 'Kappa'}
    assert abstraction.maturity_cycles == 2


def test_v107_consolidated_abstraction_preserves_evidence_chain():
    mem = AbstractionSemanticMemoryV107()
    _add_up_episode(mem, 'Delta', 24, 48)
    _add_up_episode(mem, 'Sigma', 12, 18)
    _add_up_episode(mem, 'Kappa', 6, 9)
    mem.consolidate()
    mem.consolidate()
    abstraction = mem.abstractions()[0]
    assert len(abstraction.episode_ids) == 3
    assert len(abstraction.memory_ids) == 3
    assert abstraction.pattern_id.startswith('pattern:')


def test_v107_opposite_direction_does_not_support_same_abstraction():
    mem = AbstractionSemanticMemoryV107()
    _add_up_episode(mem, 'Delta', 24, 48)
    _add_up_episode(mem, 'Sigma', 12, 18)
    mem.observe('A fonte Kappa fornece 9 V ao controlador.')
    mem.observe('Agora a fonte Kappa fornece 6 V ao controlador.')
    mem.consolidate()
    mem.consolidate()
    assert mem.abstractions() == ()


def test_v107_new_support_updates_consolidated_evidence_without_fast_repromotion():
    mem = AbstractionSemanticMemoryV107()
    _add_up_episode(mem, 'Delta', 24, 48)
    _add_up_episode(mem, 'Sigma', 12, 18)
    _add_up_episode(mem, 'Kappa', 6, 9)
    mem.consolidate()
    mem.consolidate()
    assert mem.abstractions()[0].support == 3

    _add_up_episode(mem, 'Tau', 10, 20)
    abstraction = mem.abstractions()[0]
    assert abstraction.support == 4
    assert set(abstraction.entities) == {'Delta', 'Sigma', 'Kappa', 'Tau'}
    assert abstraction.maturity_cycles == 2


def test_v107_persists_slow_clock_maturity_across_restart(tmp_path):
    semantic = tmp_path / 'semantic.json'
    events = tmp_path / 'events.json'
    episodes = tmp_path / 'episodes.json'
    patterns = tmp_path / 'patterns.json'
    abstractions = tmp_path / 'abstractions.json'
    kwargs = dict(
        path=semantic,
        events_path=events,
        episodes_path=episodes,
        patterns_path=patterns,
        abstractions_path=abstractions,
    )
    mem = AbstractionSemanticMemoryV107(**kwargs)
    _add_up_episode(mem, 'Delta', 24, 48)
    _add_up_episode(mem, 'Sigma', 12, 18)
    _add_up_episode(mem, 'Kappa', 6, 9)
    signature = mem.patterns()[0].signature
    mem.consolidate()
    assert mem.maturity_for_signature(signature) == 1

    reloaded = AbstractionSemanticMemoryV107(**kwargs)
    assert reloaded.maturity_for_signature(signature) == 1
    assert reloaded.abstractions() == ()
    reloaded.consolidate()
    assert len(reloaded.abstractions()) == 1
    assert reloaded.abstractions()[0].maturity_cycles == 2


def test_v107_preserves_autonomous_retrieval_path():
    mem = AbstractionSemanticMemoryV107()
    mem.observe('Meu carro de teste se chama Orion e a cor dele é verde.')
    result = mem.query('Qual é o nome e a cor do meu carro de teste?')
    assert result.hits
