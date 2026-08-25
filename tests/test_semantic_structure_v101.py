from memoria_resolutiva.semantic_structure_v101 import (
    DeterministicSemanticExtractorV101,
    StructuredAutonomousMemoryV101,
)


def _rels(frame):
    return {(r.subject, r.predicate, r.object) for r in frame.relations}


def test_v101_extracts_source_voltage_and_target():
    ex = DeterministicSemanticExtractorV101()
    frame = ex.extract('A fonte Delta fornece 24 V ao controlador.', memory_id='m1')
    assert frame.unresolved is False
    assert ('Delta', 'has_voltage', '24 V') in _rels(frame)
    assert ('Delta', 'powers', 'controlador') in _rels(frame)
    assert any(e.name == 'Delta' and e.kind == 'fonte' for e in frame.entities)
    assert 'tensão' in frame.concepts


def test_v101_extracts_sensor_measurement_and_place():
    ex = DeterministicSemanticExtractorV101()
    frame = ex.extract('O sensor Alfa mede temperatura na sala norte.', memory_id='m2')
    assert ('Alfa', 'measures', 'temperatura') in _rels(frame)
    assert ('Alfa', 'located_at', 'sala norte') in _rels(frame)


def test_v101_extracts_belongs_to_relation():
    ex = DeterministicSemanticExtractorV101()
    frame = ex.extract('O controlador Beta pertence ao Orion.', memory_id='m3')
    assert ('Beta', 'belongs_to', 'Orion') in _rels(frame)


def test_v101_abstains_on_unsupported_semantics():
    ex = DeterministicSemanticExtractorV101()
    frame = ex.extract('Talvez amanhã alguma coisa interessante aconteça.', memory_id='m4')
    assert frame.unresolved is True
    assert frame.relations == ()


def test_v101_preserves_original_text_as_evidence():
    text = 'A fonte Delta fornece 24 V ao controlador.'
    frame = DeterministicSemanticExtractorV101().extract(text, memory_id='m5')
    assert frame.source_text == text
    assert frame.memory_id == 'm5'


def test_v101_structured_memory_keeps_v100_retrieval():
    mem = StructuredAutonomousMemoryV101()
    observed = mem.observe('Meu carro de teste se chama Orion e a cor dele é verde.')
    result = mem.query('Qual é o nome e a cor do meu carro de teste?')
    assert result.hits
    assert 'Orion' in result.hits[0].text
    assert mem.frame(observed.memory_id) is not None


def test_v101_entity_index_returns_related_frames():
    mem = StructuredAutonomousMemoryV101()
    mem.observe('A fonte Delta fornece 24 V ao controlador.')
    mem.observe('A fonte Delta alimenta o inversor.')
    frames = mem.frames_for_entity('Delta')
    assert len(frames) == 2
    rels = mem.relations_for('Delta')
    assert any(r.predicate == 'has_voltage' for r in rels)
    assert sum(1 for r in rels if r.predicate == 'powers') >= 2


def test_v101_is_deterministic():
    ex = DeterministicSemanticExtractorV101()
    text = 'A fonte Delta fornece 24 V ao controlador.'
    a = ex.extract(text, memory_id='same')
    b = ex.extract(text, memory_id='same')
    assert a == b
