import json

from memoria_resolutiva.episodes_v105 import EpisodicSemanticMemoryV105


def test_v105_single_change_creates_single_episode():
    mem = EpisodicSemanticMemoryV105()
    mem.observe('A fonte Delta fornece 24 V ao controlador.')
    mem.observe('Agora a fonte Delta fornece 48 V ao controlador.')
    episodes = mem.episodes_for_entity('Delta')
    assert len(episodes) == 1
    ep = episodes[0]
    assert ep.start_state == ('24 V',)
    assert ep.end_state == ('48 V',)
    assert len(ep.event_ids) == 1


def test_v105_continuous_changes_merge_into_one_episode():
    mem = EpisodicSemanticMemoryV105()
    mem.observe('A fonte Delta fornece 24 V ao controlador.')
    mem.observe('Agora a fonte Delta fornece 48 V ao controlador.')
    mem.observe('Agora a fonte Delta fornece 36 V ao controlador.')
    episodes = mem.episodes_for_entity('Delta')
    assert len(episodes) == 1
    ep = episodes[0]
    assert ep.start_state == ('24 V',)
    assert ep.end_state == ('36 V',)
    assert len(ep.event_ids) == 2
    assert len(ep.memory_ids) == 2


def test_v105_conflict_without_temporal_marker_creates_no_episode():
    mem = EpisodicSemanticMemoryV105()
    mem.observe('A fonte Delta fornece 24 V ao controlador.')
    mem.observe('A fonte Delta fornece 48 V ao controlador.')
    assert mem.events() == ()
    assert mem.episodes() == ()


def test_v105_different_entities_do_not_merge():
    mem = EpisodicSemanticMemoryV105()
    mem.observe('A fonte Delta fornece 24 V ao controlador.')
    mem.observe('A fonte Sigma fornece 12 V ao controlador.')
    mem.observe('Agora a fonte Delta fornece 48 V ao controlador.')
    mem.observe('Agora a fonte Sigma fornece 18 V ao controlador.')
    assert len(mem.episodes_for_entity('Delta')) == 1
    assert len(mem.episodes_for_entity('Sigma')) == 1
    assert len(mem.episodes()) == 2


def test_v105_persists_episode_projection(tmp_path):
    convergence = tmp_path / 'semantic.json'
    events = tmp_path / 'events.json'
    episodes = tmp_path / 'episodes.json'
    mem = EpisodicSemanticMemoryV105(path=convergence, events_path=events, episodes_path=episodes)
    mem.observe('A fonte Delta fornece 24 V ao controlador.')
    mem.observe('Agora a fonte Delta fornece 48 V ao controlador.')
    raw = json.loads(episodes.read_text(encoding='utf-8'))
    assert raw['schema'] == 'episodes-v105'
    assert raw['episodes'][0]['entity'] == 'Delta'
    assert raw['episodes'][0]['event_ids'] == ['event:00000001']


def test_v105_reload_from_persisted_events_rebuilds_same_episode(tmp_path):
    convergence = tmp_path / 'semantic.json'
    events = tmp_path / 'events.json'
    episodes = tmp_path / 'episodes.json'
    mem = EpisodicSemanticMemoryV105(path=convergence, events_path=events, episodes_path=episodes)
    mem.observe('A fonte Delta fornece 24 V ao controlador.')
    mem.observe('Agora a fonte Delta fornece 48 V ao controlador.')
    mem.observe('Agora a fonte Delta fornece 36 V ao controlador.')
    expected = mem.episodes()

    reloaded = EpisodicSemanticMemoryV105(path=convergence, events_path=events, episodes_path=episodes)
    assert reloaded.episodes() == expected


def test_v105_preserves_autonomous_retrieval_path():
    mem = EpisodicSemanticMemoryV105()
    mem.observe('Meu carro de teste se chama Orion e a cor dele é verde.')
    result = mem.query('Qual é o nome e a cor do meu carro de teste?')
    assert result.hits
