from pathlib import Path

from memoria_resolutiva.autonomous_memory_v097 import AutonomousTextMemoryV097
from memoria_resolutiva.autonomous_upgrade_v098 import load_or_migrate_autonomous_v098


def test_v097_snapshot_migrates_without_deleting_source(tmp_path: Path):
    old_path = tmp_path / 'autonomous-memory-v097.json'
    old = AutonomousTextMemoryV097()
    old.observe('Meu carro de teste se chama Orion e a cor dele é verde.')
    old.observe('O equipamento Atlas usa marcador Quasar.')
    old.save(old_path)

    upgraded, new_path, migrated = load_or_migrate_autonomous_v098(tmp_path)

    assert migrated is True
    assert old_path.exists()
    assert new_path.exists()
    assert len(upgraded) == 2
    result = upgraded.query('Qual é a cor do meu carro de teste?')
    assert result.hits and 'verde' in result.hits[0].text


def test_existing_v098_snapshot_wins_after_migration(tmp_path: Path):
    old_path = tmp_path / 'autonomous-memory-v097.json'
    old = AutonomousTextMemoryV097()
    old.observe('A versão antiga contém somente este fato.')
    old.save(old_path)

    first, new_path, migrated = load_or_migrate_autonomous_v098(tmp_path)
    assert migrated is True
    first.observe('A versão nova contém um segundo fato.')
    first.save(new_path)

    second, _, migrated_again = load_or_migrate_autonomous_v098(tmp_path)
    assert migrated_again is False
    assert len(second) == 2
