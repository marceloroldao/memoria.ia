from __future__ import annotations

from dataclasses import asdict, dataclass
import json
from pathlib import Path

from .patterns_v106 import PatternSemanticMemoryV106, RecurringPatternV106
from .semantic_structure_v101 import StructuredObservationV101


@dataclass(frozen=True, slots=True)
class ConsolidatedAbstractionV107:
    abstraction_id: str
    predicate: str
    signature: tuple[str, ...]
    support: int
    entities: tuple[str, ...]
    pattern_id: str
    episode_ids: tuple[str, ...]
    memory_ids: tuple[str, ...]
    maturity_cycles: int
    status: str = "consolidated"
    kind: str = "consolidated_pattern_abstraction"


class AbstractionSemanticMemoryV107:
    """Consolidate recurring v1.06 patterns on a slower explicit clock.

    The abstraction layer never advances on each observation. New observations
    can create/update candidate patterns in v1.06, but promotion requires an
    explicit ``consolidate()`` tick. A pattern must also have stronger support
    and entity diversity than the underlying v1.06 candidate gate and remain
    eligible for multiple consolidation cycles before becoming consolidated.

    This models a slower update rate for denser/higher semantic layers while
    preserving a full evidence path back to episodes and source memories.
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
        abstractions_path: str | Path | None = None,
        candidate_min_support: int = 2,
        candidate_min_distinct_entities: int = 2,
        abstraction_min_support: int = 3,
        abstraction_min_distinct_entities: int = 3,
        min_stability_cycles: int = 2,
    ) -> None:
        if abstraction_min_support < candidate_min_support:
            raise ValueError("abstraction_min_support must be >= candidate_min_support")
        if abstraction_min_distinct_entities < candidate_min_distinct_entities:
            raise ValueError("abstraction_min_distinct_entities must be >= candidate_min_distinct_entities")
        if min_stability_cycles < 1:
            raise ValueError("min_stability_cycles must be >= 1")

        self.pattern_memory = PatternSemanticMemoryV106(
            threshold=threshold,
            ambiguity_margin=ambiguity_margin,
            path=path,
            events_path=events_path,
            episodes_path=episodes_path,
            patterns_path=patterns_path,
            min_support=candidate_min_support,
            min_distinct_entities=candidate_min_distinct_entities,
        )
        self.abstractions_path = Path(abstractions_path) if abstractions_path is not None else None
        self.abstraction_min_support = abstraction_min_support
        self.abstraction_min_distinct_entities = abstraction_min_distinct_entities
        self.min_stability_cycles = min_stability_cycles
        self._maturity: dict[tuple[str, ...], int] = {}
        self._abstractions: list[ConsolidatedAbstractionV107] = []
        if self.abstractions_path and self.abstractions_path.exists():
            self._load_state()
        self._rebuild_abstractions()

    def observe(
        self,
        text: str,
        *,
        provenance: str = "conversation",
        namespace: str | None = None,
    ) -> StructuredObservationV101:
        observed = self.pattern_memory.observe(text, provenance=provenance, namespace=namespace)
        # Intentionally do not advance maturity here. Higher-layer time only
        # advances through consolidate(), not at the event/episode rate.
        self._rebuild_abstractions()
        self._persist_state()
        return observed

    def query(self, text: str, *, top_k: int = 3):
        return self.pattern_memory.query(text, top_k=top_k)

    def patterns(self) -> tuple[RecurringPatternV106, ...]:
        return self.pattern_memory.patterns()

    def abstractions(self) -> tuple[ConsolidatedAbstractionV107, ...]:
        return tuple(self._abstractions)

    def abstractions_for_predicate(self, predicate: str) -> tuple[ConsolidatedAbstractionV107, ...]:
        return tuple(a for a in self._abstractions if a.predicate == predicate)

    def maturity_for_signature(self, signature: tuple[str, ...]) -> int:
        return self._maturity.get(tuple(signature), 0)

    def _eligible_patterns(self) -> tuple[RecurringPatternV106, ...]:
        return tuple(
            pattern
            for pattern in self.pattern_memory.patterns()
            if pattern.support >= self.abstraction_min_support
            and len(pattern.entities) >= self.abstraction_min_distinct_entities
        )

    def consolidate(self) -> tuple[ConsolidatedAbstractionV107, ...]:
        eligible = {tuple(pattern.signature): pattern for pattern in self._eligible_patterns()}

        # Evidence that disappears or falls below the stronger gate loses its
        # maturity rather than surviving as an unsupported abstraction seed.
        for signature in tuple(self._maturity):
            if signature not in eligible:
                del self._maturity[signature]

        for signature in eligible:
            self._maturity[signature] = self._maturity.get(signature, 0) + 1

        self._rebuild_abstractions()
        self._persist_state()
        return self.abstractions()

    def _rebuild_abstractions(self) -> None:
        abstractions: list[ConsolidatedAbstractionV107] = []
        for pattern in sorted(self._eligible_patterns(), key=lambda p: p.signature):
            maturity = self._maturity.get(tuple(pattern.signature), 0)
            if maturity < self.min_stability_cycles:
                continue
            abstractions.append(
                ConsolidatedAbstractionV107(
                    abstraction_id=f"abstraction:{len(abstractions) + 1:08d}",
                    predicate=pattern.predicate,
                    signature=tuple(pattern.signature),
                    support=pattern.support,
                    entities=tuple(pattern.entities),
                    pattern_id=pattern.pattern_id,
                    episode_ids=tuple(pattern.episode_ids),
                    memory_ids=tuple(pattern.memory_ids),
                    maturity_cycles=maturity,
                )
            )
        self._abstractions = abstractions

    def _persist_state(self) -> None:
        if self.abstractions_path is None:
            return
        self.abstractions_path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "schema": "abstractions-v107",
            "abstraction_min_support": self.abstraction_min_support,
            "abstraction_min_distinct_entities": self.abstraction_min_distinct_entities,
            "min_stability_cycles": self.min_stability_cycles,
            "maturity": [
                {"signature": list(signature), "cycles": cycles}
                for signature, cycles in sorted(self._maturity.items())
            ],
            "abstractions": [asdict(a) for a in self._abstractions],
        }
        tmp = self.abstractions_path.with_suffix(self.abstractions_path.suffix + ".tmp")
        tmp.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        tmp.replace(self.abstractions_path)

    def _load_state(self) -> None:
        raw = json.loads(self.abstractions_path.read_text(encoding="utf-8"))
        if raw.get("schema") != "abstractions-v107":
            raise ValueError("unsupported abstractions schema")
        self._maturity = {
            tuple(item.get("signature", [])): int(item.get("cycles", 0))
            for item in raw.get("maturity", [])
        }
