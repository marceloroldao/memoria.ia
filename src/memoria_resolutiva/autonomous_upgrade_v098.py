from __future__ import annotations

from pathlib import Path

from .autonomous_memory_v097 import AutonomousTextMemoryV097
from .autonomous_memory_v098 import AutonomousTextMemoryV098


def load_or_migrate_autonomous_v098(data_dir: str | Path) -> tuple[AutonomousTextMemoryV098, Path, bool]:
    """Load v0.98 state or migrate a v0.97 snapshot without deleting the source.

    Returns `(memory, v098_snapshot_path, migrated)`.
    """
    root = Path(data_dir)
    snapshot_v098 = root / 'autonomous-memory-v098.json'
    if snapshot_v098.exists():
        return AutonomousTextMemoryV098.load(snapshot_v098), snapshot_v098, False

    snapshot_v097 = root / 'autonomous-memory-v097.json'
    if snapshot_v097.exists():
        old = AutonomousTextMemoryV097.load(snapshot_v097)
        migrated = AutonomousTextMemoryV098(
            threshold=old.threshold,
            ambiguity_margin=old.ambiguity_margin,
        )
        for record in old.records():
            migrated.observe(record.text, provenance=record.provenance)
        migrated.save(snapshot_v098)
        return migrated, snapshot_v098, True

    return AutonomousTextMemoryV098(), snapshot_v098, False
