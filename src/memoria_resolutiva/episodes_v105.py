from __future__ import annotations

from dataclasses import asdict, dataclass
import json
from pathlib import Path

from .events_v104 import EventSemanticMemoryV104, StateChangeEventV104
from .semantic_structure_v101 import StructuredObservationV101


@dataclass(frozen=True, slots=True)
class StateEpisodeV105:
    episode_id: str
    entity: str
    predicate: str
    start_state: tuple[str, ...]
    end_state: tuple[str, ...]
    event_ids: tuple[str, ...]
    memory_ids: tuple[str, ...]
    source_texts: tuple[str, ...]
    kind: str = "state_transition_episode"


class EpisodicSemanticMemoryV105:
    """Conservatively group certified v1.04 events into state-transition episodes.

    Episode continuity is intentionally strict: two events are grouped only when
    they affect the same entity and predicate and the previous ``after`` state
    exactly matches the next ``before`` state. This avoids inventing causal or
    episodic relationships that are not supported by the temporal record.
    """

    def __init__(
        self,
        *,
        threshold: float = 0.42,
        ambiguity_margin: float = 0.04,
        path: str | Path | None = None,
        events_path: str | Path | None = None,
        episodes_path: str | Path | None = None,
    ) -> None:
        self.events_memory = EventSemanticMemoryV104(
            threshold=threshold,
            ambiguity_margin=ambiguity_margin,
            path=path,
            events_path=events_path,
        )
        self.episodes_path = Path(episodes_path) if episodes_path is not None else None
        self._episodes: list[StateEpisodeV105] = []
        self._rebuild_episodes()

    @staticmethod
    def _key(value: str) -> str:
        return " ".join(value.strip().split()).casefold()

    def observe(
        self,
        text: str,
        *,
        provenance: str = "conversation",
        namespace: str | None = None,
    ) -> StructuredObservationV101:
        observed = self.events_memory.observe(
            text,
            provenance=provenance,
            namespace=namespace,
        )
        self._rebuild_episodes()
        self._persist_episodes()
        return observed

    def query(self, text: str, *, top_k: int = 3):
        return self.events_memory.query(text, top_k=top_k)

    def events(self) -> tuple[StateChangeEventV104, ...]:
        return self.events_memory.events()

    def episodes(self) -> tuple[StateEpisodeV105, ...]:
        return tuple(self._episodes)

    def episodes_for_entity(self, name: str) -> tuple[StateEpisodeV105, ...]:
        needle = self._key(name)
        return tuple(ep for ep in self._episodes if self._key(ep.entity) == needle)

    def latest_episode(self, name: str, predicate: str | None = None) -> StateEpisodeV105 | None:
        episodes = self.episodes_for_entity(name)
        if predicate is not None:
            episodes = tuple(ep for ep in episodes if ep.predicate == predicate)
        return episodes[-1] if episodes else None

    def _rebuild_episodes(self) -> None:
        episodes: list[StateEpisodeV105] = []
        current: list[StateChangeEventV104] = []

        def flush() -> None:
            if not current:
                return
            first, last = current[0], current[-1]
            episodes.append(
                StateEpisodeV105(
                    episode_id=f"episode:{len(episodes) + 1:08d}",
                    entity=first.entity,
                    predicate=first.predicate,
                    start_state=tuple(first.before),
                    end_state=tuple(last.after),
                    event_ids=tuple(event.event_id for event in current),
                    memory_ids=tuple(event.memory_id for event in current),
                    source_texts=tuple(event.source_text for event in current),
                )
            )
            current.clear()

        for event in self.events_memory.events():
            if not current:
                current.append(event)
                continue
            previous = current[-1]
            continuous = (
                self._key(previous.entity) == self._key(event.entity)
                and previous.predicate == event.predicate
                and tuple(previous.after) == tuple(event.before)
            )
            if continuous:
                current.append(event)
            else:
                flush()
                current.append(event)
        flush()
        self._episodes = episodes

    def _persist_episodes(self) -> None:
        if self.episodes_path is None:
            return
        self.episodes_path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "schema": "episodes-v105",
            "episodes": [asdict(ep) for ep in self._episodes],
        }
        tmp = self.episodes_path.with_suffix(self.episodes_path.suffix + ".tmp")
        tmp.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        tmp.replace(self.episodes_path)
