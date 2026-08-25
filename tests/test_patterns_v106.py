import json

from memoria_resolutiva.patterns_v106 import PatternSemanticMemoryV106


def test_v106_single_episode_does_not_create_pattern():
    mem = PatternSemanticMemoryV106()
    mem.observe('A fonte Delta fornece 24 V ao controlador.')
    mem.observe('Agora a fonte Delta fornece 48 V ao controlador.')
    assert len(mem.episodes()) == 1
    assert mem.patterns() == ()


def test_v106_same_structural_change_across_entities_creates_candidate_pattern():
    mem = PatternSemanticMemoryV106()
    mem.observe('A fonte Delta fornece 24 V ao controlador.')
    mem.observe('A fonte Sigma fornece 12 V ao controlador.')
    mem.observe('Agora a fonte Delta fornece 48 V ao controlador.')
    mem.observe('Agora a fonte Sigma fornece 18 V ao controlador.')
    patterns = mem.patterns_for_predicate('has_voltage')
    assert len(patterns) == 1
    pattern = patterns[0]
    assert pattern.status == 'candidate'
    assert pattern.support == 2
    assert set(pattern.entities) == {'Delta', 'Sigma'}
    assert 'scalar:v:up' in pattern.signature


def test_v106_opposite_directions_do_not_form_same_pattern():
    mem = PatternSemanticMemoryV106()
    mem.observe('A fonte Delta fornece 24 V ao controlador.')
    mem.observe('A fonte Sigma fornece 24 V ao controlador.')
    mem.observe('Agora a fonte Delta fornece 48 V ao controlador.')
    mem.observe('Agora a fonte Sigma fornece 12 V ao controlador.')
    assert mem.patterns() == ()


def test_v106_repeated_two_step_shape_is_detected_without_claiming_causality():
    mem = PatternSemanticMemoryV106()
    mem.observe('A fonte Delta fornece 24 V ao controlador.')
    mem.observe('A fonte Sigma fornece 12 V ao controlador.')
    mem.observe('Agora a fonte Delta fornece 48 V ao controlador.')
    mem.observe('Agora a fonte Delta fornece 36 V ao controlador.')
    mem.observe('Agora a fonte Sigma fornece 24 V ao controlador.')
    mem.observe('Agora a fonte Sigma fornece 18 V ao controlador.')
    patterns = mem.patterns_for_predicate('has_voltage')
    assert len(patterns) == 1
    pattern = patterns[0]
    assert pattern.signature[-2:] == ('scalar:v:up', 'scalar:v:down')
    assert pattern.kind == 'recurring_episode_pattern'
    assert pattern.status == 'candidate'


def test_v106_requires_distinct_entities_by_default():
    mem = PatternSemanticMemoryV106(min_support=2, min_distinct_entities=2)
    # Directly validate the conservative contract through a corpus with only one
    # certified episode: support cannot be fabricated from repeated assertions.
    mem.observe('A fonte Delta fornece 24 V ao controlador.')
    mem.observe('Agora a fonte Delta fornece 48 V ao controlador.')
    mem.observe('Agora a fonte Delta fornece 36 V ao controlador.')
    assert mem.patterns() == ()


def test_v106_persists_candidate_projection(tmp_path):
    semantic = tmp_path / 'semantic.json'
    events = tmp_path / 'events.json'
    episodes = tmp_path / 'episodes.json'
    patterns = tmp_path / 'patterns.json'
    mem = PatternSemanticMemoryV106(
        path=semantic,
        events_path=events,
        episodes_path=episodes,
        patterns_path=patterns,
    )
    mem.observe('A fonte Delta fornece 24 V ao controlador.')
    mem.observe('A fonte Sigma fornece 12 V ao controlador.')
    mem.observe('Agora a fonte Delta fornece 48 V ao controlador.')
    mem.observe('Agora a fonte Sigma fornece 18 V ao controlador.')
    raw = json.loads(patterns.read_text(encoding='utf-8'))
    assert raw['schema'] == 'patterns-v106'
    assert raw['patterns'][0]['support'] == 2
    assert set(raw['patterns'][0]['entities']) == {'Delta', 'Sigma'}


def test_v106_pattern_preserves_episode_and_memory_evidence():
    mem = PatternSemanticMemoryV106()
    mem.observe('A fonte Delta fornece 24 V ao controlador.')
    mem.observe('A fonte Sigma fornece 12 V ao controlador.')
    mem.observe('Agora a fonte Delta fornece 48 V ao controlador.')
    mem.observe('Agora a fonte Sigma fornece 18 V ao controlador.')
    pattern = mem.patterns()[0]
    assert len(pattern.episode_ids) == 2
    assert len(pattern.memory_ids) == 2


def test_v106_preserves_autonomous_retrieval_path():
    mem = PatternSemanticMemoryV106()
    mem.observe('Meu carro de teste se chama Orion e a cor dele é verde.')
    result = mem.query('Qual é o nome e a cor do meu carro de teste?')
    assert result.hits
