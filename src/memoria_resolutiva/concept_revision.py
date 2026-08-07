from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

from .sense_consolidation import SenseGroup, consolidate_senses
from .polysemy import PolysemyMemory


@dataclass(frozen=True, slots=True)
class ConceptSnapshot:
    epoch: int
    token: str
    groups: tuple[tuple[int, ...], ...]


class ConceptRevisionHistory:
    """Append-only history of ontology snapshots.

    Current concept organization may change over time, while prior snapshots
    remain queryable. This records model-belief structure, not factual truth.
    """

    def __init__(self):
        self._snapshots: list[ConceptSnapshot] = []

    @staticmethod
    def _canonical(groups: Iterable[SenseGroup]) -> tuple[tuple[int, ...], ...]:
        return tuple(sorted((tuple(sorted(g.sense_ids)) for g in groups), key=lambda x: (len(x), x)))

    def record(self, epoch: int, token: str, groups: list[SenseGroup]) -> ConceptSnapshot:
        snapshot = ConceptSnapshot(epoch=epoch, token=token.lower(), groups=self._canonical(groups))
        self._snapshots.append(snapshot)
        self._snapshots.sort(key=lambda s: s.epoch)
        return snapshot

    def current(self, token: str) -> ConceptSnapshot | None:
        rows = [s for s in self._snapshots if s.token == token.lower()]
        return rows[-1] if rows else None

    def at(self, token: str, epoch: int) -> ConceptSnapshot | None:
        rows = [s for s in self._snapshots if s.token == token.lower() and s.epoch <= epoch]
        return rows[-1] if rows else None

    def revisions(self, token: str) -> list[tuple[ConceptSnapshot, ConceptSnapshot]]:
        rows = [s for s in self._snapshots if s.token == token.lower()]
        return [(a, b) for a, b in zip(rows, rows[1:]) if a.groups != b.groups]


def snapshot_from_memory(
    history: ConceptRevisionHistory,
    memory: PolysemyMemory,
    token: str,
    epoch: int,
    threshold: float,
) -> ConceptSnapshot:
    groups = consolidate_senses(memory, token, threshold=threshold)
    return history.record(epoch, token, groups)
