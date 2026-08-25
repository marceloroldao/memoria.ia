from memoria_resolutiva.events_v104 import EventSemanticMemoryV104


def test_v104_initial_state_does_not_emit_change_event():
    mem = EventSemanticMemoryV104()
    mem.observe('A fonte Delta fornece 24 V ao controlador.')
    assert mem.events() == ()


def test_v104_explicit_temporal_change_emits_event():
    mem = EventSemanticMemoryV104()
    mem.observe('A fonte Delta fornece 24 V ao controlador.')
    changed = mem.observe('Agora a fonte Delta fornece 48 V ao controlador.')
    events = mem.events_for_entity('Delta')
    assert len(events) == 1
    event = events[0]
    assert event.kind == 'state_change'
    assert event.predicate == 'has_voltage'
    assert event.before == ('24 V',)
    assert event.after == ('48 V',)
    assert event.memory_id == changed.memory_id
    assert event.source_text == 'Agora a fonte Delta fornece 48 V ao controlador.'


def test_v104_unmarked_conflict_does_not_emit_event():
    mem = EventSemanticMemoryV104()
    mem.observe('A fonte Delta fornece 24 V ao controlador.')
    mem.observe('A fonte Delta fornece 48 V ao controlador.')
    assert mem.events() == ()
    state = mem.temporal.predicate_state('Delta', 'has_voltage')
    assert state is not None and state.status == 'conflict'


def test_v104_multiple_temporal_changes_keep_order():
    mem = EventSemanticMemoryV104()
    mem.observe('A fonte Delta fornece 24 V ao controlador.')
    mem.observe('Agora a fonte Delta fornece 48 V ao controlador.')
    mem.observe('Agora a fonte Delta fornece 36 V ao controlador.')
    events = mem.events_for_entity('Delta')
    assert [e.event_id for e in events] == ['event:00000001', 'event:00000002']
    assert events[0].before == ('24 V',) and events[0].after == ('48 V',)
    assert events[1].before == ('48 V',) and events[1].after == ('36 V',)


def test_v104_event_log_persists_and_reloads(tmp_path):
    state_path = tmp_path / 'semantic.json'
    event_path = tmp_path / 'events.json'
    mem = EventSemanticMemoryV104(path=state_path, events_path=event_path)
    mem.observe('A fonte Delta fornece 24 V ao controlador.')
    mem.observe('Agora a fonte Delta fornece 48 V ao controlador.')

    restored = EventSemanticMemoryV104(path=state_path, events_path=event_path)
    event = restored.latest_event('Delta')
    assert event is not None
    assert event.before == ('24 V',)
    assert event.after == ('48 V',)
    assert restored.temporal.predicate_state('Delta', 'has_voltage') is not None


def test_v104_preserves_autonomous_retrieval():
    mem = EventSemanticMemoryV104()
    mem.observe('Meu carro de teste se chama Orion e a cor dele é verde.')
    result = mem.query('Qual é o nome e a cor do meu carro de teste?')
    assert result.hits
