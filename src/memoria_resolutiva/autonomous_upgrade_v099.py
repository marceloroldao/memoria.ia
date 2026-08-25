from __future__ import annotations

from pathlib import Path

from .autonomous_memory_v099 import AutonomousTextMemoryV099
from .autonomous_upgrade_v098 import load_or_migrate_autonomous_v098


def load_autonomous_v099(data_dir: str | Path) -> tuple[AutonomousTextMemoryV099, Path, bool]:
    """Load v0.99 using the intentionally unchanged v0.98 snapshot format.

    If only a v0.97 snapshot exists, the validated v0.98 migration is performed
    first. The v0.97 source remains untouched. v0.99 then loads the resulting
    v0.98-format snapshot directly, preserving rollback compatibility.

    Returns `(memory, snapshot_path, migrated_from_v097)`.
    """
    _v098, snapshot, migrated = load_or_migrate_autonomous_v098(data_dir)
    memory = AutonomousTextMemoryV099.load(snapshot) if snapshot.exists() else AutonomousTextMemoryV099()
    return memory, snapshot, migrated
