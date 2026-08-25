from pathlib import Path

from memoria_resolutiva.autonomous_memory_v097 import AutonomousTextMemoryV097
from memoria_resolutiva.autonomous_memory_v098 import AutonomousTextMemoryV098
from memoria_resolutiva.autonomous_memory_v099 import AutonomousTextMemoryV099
from memoria_resolutiva.autonomous_upgrade_v099 import load_autonomous_v099


def test_v099_loads_existing_v098_snapshot_without_format_rewrite(tmp_path: Path):
    path = tmp_path / 'autonomous-memory-v098.json'
    old = AutonomousTextMemoryV098()
    old.observe('Meu carro de teste se chama Orion e a cor dele é verde.')
    old.save(path)

    memory, snapshot, migrated = load_autonomous_v099(tmp_path)
    assert isinstance(memory, AutonomousTextMemoryV099)
    assert snapshot == path
    assert migrated is False
    result = memory.query('Qual é a cor do meu carro de teste?')
    assert result.hits and 'verde' in result.hits[0].text


def test_v099_written_snapshot_can_be_loaded_by_v098_for_rollback(tmp_path: Path):
    memory, snapshot, _ = load_autonomous_v099(tmp_path)
    memory.observe('A estação Vega usa o protocolo Nebulon para telemetria.')
    memory.save(snapshot)

    rollback = AutonomousTextMemoryV098.load(snapshot)
    result = rollback.query('Qual protocolo a estação Vega usa?')
    assert result.hits and 'Nebulon' in result.hits[0].text


def test_v099_migrates_v097_non_destructively_then_loads_v099(tmp_path: Path):
    source = tmp_path / 'autonomous-memory-v097.json'
    old = AutonomousTextMemoryV097()
    old.observe('O equipamento Atlas usa marcador Quasar.')
    old.save(source)

    memory, snapshot, migrated = load_autonomous_v099(tmp_path)
    assert isinstance(memory, AutonomousTextMemoryV099)
    assert migrated is True
    assert source.exists()
    assert snapshot.name == 'autonomous-memory-v098.json'
    assert snapshot.exists()
    result = memory.query('Qual marcador o equipamento Atlas usa?')
    assert result.hits and 'Quasar' in result.hits[0].text
