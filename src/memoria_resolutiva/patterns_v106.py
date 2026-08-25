from __future__ import annotations

from dataclasses import asdict, dataclass
import json
import re
from pathlib import Path

from .episodes_v105 import EpisodicSemanticMemoryV105, StateEpisodeV105
from .semantic_structure_v101 import StructuredObservationV101

_SCALAR_RE = re.compile(r"^\s*(-?\d+(?:[.,]\d+)?)\s*([^\d\s].*)?\s*$")


@dataclass(frozen=True, slots=True)
class RecurringPatternV106:
    pattern_id: str
    predicate: str
    signature: tuple[str, ...]
    support: int
    entities: tuple[str, ...]
    episode_ids: tuple[str, ...]
    memory_ids: tuple[str, ...]
    status: str = "candidate"
    kind: str = "recurring_episode_pattern"


class PatternSemanticMemoryV106:
    """Detect conservative recurring structural patterns across v1.05 episodes.

    A v1.06 pattern is only a *candidate abstraction*. It does not assert cause,
    prediction, or ontology. By default a pattern requires at least two supporting
    episodes from at least two distinct entities. Numeric single-value transitions
    are generalized only to direction (up/down/same), predicate, unit, and event
    count. Unsupported/non-numeric transitions fall back to exact normalized states.
    """

    def __init__(
        self,
        *,
        threshold: float = 0.42,
        ambiguity_margin: float = 0.04,
        path: str | Path | None = None,
        events_path: str | Path | None = None,
        episodes_path: str | Path | None = None,
        patterns_path: str | Path | None = None,
        min_support: int = 2,
        min_distinct_entities: int = 2,
    ) -> None:
        if min_support < 2:
            raise ValueError("min_support must be >= 2")
        if min_distinct_entities < 1:
            raise ValueError("min_distinct_entities must be >= 1")
        self.episodic = EpisodicSemanticMemoryV105(
            threshold=threshold,
            ambiguity_margin=ambiguity_margin,
            path=path,
            events_path=events_path,
            episodes_path=episodes_path,
        )
        self.patterns_path = Path(patterns_path) if patterns_path is not None else None
        self.min_support = min_support
        self.min_distinct_entities = min_distinct_entities
        self._patterns: list[RecurringPatternV106] = []
        self._rebuild_patterns()

    @staticmethod
    def _key(value: str) -> str:
        return " ".join(value.strip().split()).casefold()

    @classmethod
    def _scalar(cls, state: tuple[str, ...]) -> tuple[float, str] | None:
        if len(state) != 1:
            return None
        match = _SCALAR_RE.match(state[0])
        if not match:
            return None
        value = float(match.group(1).replace(",", "."))
        unit = cls._key(match.group(2) or "")
        return value, unit

    @classmethod
    def _transition_token(cls, before: tuple[str, ...], after: tuple[str, ...]) -> str:
        left = cls._scalar(before)
        right = cls._scalar(after)
        if left is not None and right is not None and left[1] == right[1]:
            if right[0] > left[0]:
                direction = "up"
            elif right[0] < left[0]:
                direction = "down"
            else:
                direction = "same"
            return f"scalar:{left[1] or 'unitless'}:{direction}"
        norm_before = "|".join(cls._key(v) for v in before)
        norm_after = "|".join(cls._key(v) for v in after)
        return f"exact:{norm_before}->{norm_after}"

    def _event_lookup(self):
        return {event.event_id: event for event in self.episodic.events()}

    def episode_signature(self, episode: StateEpisodeV105) -> tuple[str, ...]:
        lookup = self._event_lookup()
        tokens: list[str] = [f"predicate:{episode.predicate}", f"events:{len(episode.event_ids)}"]
        for event_id in episode.event_ids:
            event = lookup.get(event_id)
            if event is None:
                return ()
            tokens.append(self._transition_token(tuple(event.before), tuple(event.after)))
        return tuple(tokens)

    def observe(
        self,
        text: str,
        *,
        provenance: str = "conversation",
        namespace: str | None = None,
    ) -> StructuredObservationV101:
        observed = self.episodic.observe(text, provenance=provenance, namespace=namespace)
        self._rebuild_patterns()
        self._persist_patterns()
        return observed

    def query(self, text: str, *, top_k: int = 3):
        return self.episodic.query(text, top_k=top_k)

    def episodes(self):
        return self.episodic.episodes()

    def patterns(self) -> tuple[RecurringPatternV106, ...]:
        return tuple(self._patterns)

    def patterns_for_predicate(self, predicate: str) -> tuple[RecurringPatternV106, ...]:
        return tuple(pattern for pattern in self._patterns if pattern.predicate == predicate)

    def _rebuild_patterns(self) -> None:
        buckets: dict[tuple[str, ...], list[StateEpisodeV105]] = {}
        for episode in self.episodic.episodes():
            signature = self.episode_signature(episode)
            if signature:
                buckets.setdefault(signature, []).append(episode)

        patterns: list[RecurringPatternV106] = []
        for signature in sorted(buckets):
            episodes = buckets[signature]
            entities = tuple(sorted({ep.entity for ep in episodes}, key=str.casefold))
            if len(episodes) < self.min_support or len(entities) < self.min_distinct_entities:
                continue
            episode_ids = tuple(ep.episode_id for ep in episodes)
            memory_ids = tuple(dict.fromkeys(mid for ep in episodes for mid in ep.memory_ids))
            patterns.append(
                RecurringPatternV106(
                    pattern_id=f"pattern:{len(patterns) + 1:08d}",
                    predicate=episodes[0].predicate,
                    signature=signature,
                    support=len(episodes),
                    entities=entities,
                    episode_ids=episode_ids,
                    memory_ids=memory_ids,
                )
            )
        self._patterns = patterns

    def _persist_patterns(self) -> None:
        if self.patterns_path is None:
            return
        self.patterns_path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "schema": "patterns-v106",
            "min_support": self.min_support,
            "min_distinct_entities": self.min_distinct_entities,
            "patterns": [asdict(pattern) for pattern in self._patterns],
        }
        tmp = self.patterns_path.with_suffix(self.patterns_path.suffix + ".tmp")
        tmp.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        tmp.replace(self.patterns_path)
