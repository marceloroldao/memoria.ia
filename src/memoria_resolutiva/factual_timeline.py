from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class FactEvent:
    epoch: int
    subject: str
    relation: str
    value: str
    source: str | None = None


class FactualTimelineMemory:
    """Append-only temporal fact memory.

    Facts are never overwritten. A later value supersedes an earlier value only
    for current-state queries; historical queries remain reproducible.
    """

    def __init__(self):
        self._events: list[FactEvent] = []

    def observe(self, epoch: int, subject: str, relation: str, value: str, source: str | None = None) -> FactEvent:
        event = FactEvent(epoch, subject, relation, value, source)
        self._events.append(event)
        self._events.sort(key=lambda item: item.epoch)
        return event

    def history(self, subject: str, relation: str) -> list[FactEvent]:
        return [e for e in self._events if e.subject == subject and e.relation == relation]

    def at(self, subject: str, relation: str, epoch: int) -> FactEvent | None:
        candidates = [e for e in self.history(subject, relation) if e.epoch <= epoch]
        return candidates[-1] if candidates else None

    def current(self, subject: str, relation: str) -> FactEvent | None:
        events = self.history(subject, relation)
        return events[-1] if events else None

    def transitions(self, subject: str, relation: str) -> list[tuple[FactEvent, FactEvent]]:
        events = self.history(subject, relation)
        return [(a, b) for a, b in zip(events, events[1:]) if a.value != b.value]

    def superseded_at(self, subject: str, relation: str, value: str) -> int | None:
        events = self.history(subject, relation)
        for i, event in enumerate(events[:-1]):
            if event.value != value:
                continue
            for later in events[i + 1:]:
                if later.value != value:
                    return later.epoch
        return None
