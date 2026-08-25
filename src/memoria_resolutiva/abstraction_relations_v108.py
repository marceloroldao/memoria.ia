from __future__ import annotations

from dataclasses import asdict, dataclass
import json
from pathlib import Path

from .abstractions_v107 import AbstractionSemanticMemoryV107, ConsolidatedAbstractionV107
from .semantic_structure_v101 import StructuredObservationV101


@dataclass(frozen=True, slots=True)
class AbstractionRelationV108:
    relation_id: str
    left_abstraction_id: str
    right_abstraction_id: str
    relation: str
    shared_entities: tuple[str, ...]
    union_entities: tuple[str, ...]
    entity_jaccard: float
    evidence_memory_ids: tuple[str, ...]
    maturity_cycles: int
    status: str = "consolidated"
    kind: str = "abstraction_relation"


class RelationalAbstractionMemoryV108:
    """Build conservative relations between already-consolidated abstractions.

    v1.08 does not infer causality, implication, or ontology. The only relation
    currently emitted is ``co_supported``: two abstractions are linked when a
    sufficiently large and stable set of entities supports both abstractions.
    The relation advances on its own explicit ``consolidate_relations()`` clock,
    slower than observations and separate from v1.07 abstraction consolidation.
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
        relations_path: str | Path | None = None,
        relation_min_shared_entities: int = 3,
        relation_min_entity_jaccard: float = 0.60,
        relation_min_stability_cycles: int = 2,
        **abstraction_kwargs,
    ) -> None:
        if relation_min_shared_entities < 2:
            raise ValueError("relation_min_shared_entities must be >= 2")
        if not 0.0 <= relation_min_entity_jaccard <= 1.0:
            raise ValueError("relation_min_entity_jaccard must be between 0 and 1")
        if relation_min_stability_cycles < 1:
            raise ValueError("relation_min_stability_cycles must be >= 1")
        self.abstraction_memory = AbstractionSemanticMemoryV107(
            threshold=threshold,
            ambiguity_margin=ambiguity_margin,
            path=path,
            events_path=events_path,
            episodes_path=episodes_path,
            patterns_path=patterns_path,
            abstractions_path=abstractions_path,
            **abstraction_kwargs,
        )
        self.relations_path = Path(relations_path) if relations_path is not None else None
        self.relation_min_shared_entities = relation_min_shared_entities
        self.relation_min_entity_jaccard = relation_min_entity_jaccard
        self.relation_min_stability_cycles = relation_min_stability_cycles
        self._maturity: dict[tuple[tuple[str, ...], tuple[str, ...]], int] = {}
        self._relations: list[AbstractionRelationV108] = []
        if self.relations_path and self.relations_path.exists():
            self._load_state()
        self._rebuild_relations()

    @staticmethod
    def _abstraction_key(abstraction: ConsolidatedAbstractionV107) -> tuple[str, ...]:
        return tuple(abstraction.signature)

    @classmethod
    def _pair_key(
        cls, left: ConsolidatedAbstractionV107, right: ConsolidatedAbstractionV107
    ) -> tuple[tuple[str, ...], tuple[str, ...]]:
        a, b = cls._abstraction_key(left), cls._abstraction_key(right)
        return (a, b) if a <= b else (b, a)

    def observe(
        self,
        text: str,
        *,
        provenance: str = "conversation",
        namespace: str | None = None,
    ) -> StructuredObservationV101:
        observed = self.abstraction_memory.observe(text, provenance=provenance, namespace=namespace)
        self._rebuild_relations()
        self._persist_state()
        return observed

    def query(self, text: str, *, top_k: int = 3):
        return self.abstraction_memory.query(text, top_k=top_k)

    def consolidate_abstractions(self):
        result = self.abstraction_memory.consolidate()
        self._rebuild_relations()
        self._persist_state()
        return result

    def abstractions(self) -> tuple[ConsolidatedAbstractionV107, ...]:
        return self.abstraction_memory.abstractions()

    def relations(self) -> tuple[AbstractionRelationV108, ...]:
        return tuple(self._relations)

    def _eligible_pairs(self):
        abstractions = self.abstraction_memory.abstractions()
        out = []
        for i, left in enumerate(abstractions):
            for right in abstractions[i + 1 :]:
                # Linking an abstraction to another copy of the same signature
                # would add no structural information.
                if tuple(left.signature) == tuple(right.signature):
                    continue
                left_entities = set(left.entities)
                right_entities = set(right.entities)
                shared = left_entities & right_entities
                union = left_entities | right_entities
                jaccard = len(shared) / len(union) if union else 0.0
                if (
                    len(shared) >= self.relation_min_shared_entities
                    and jaccard >= self.relation_min_entity_jaccard
                ):
                    out.append((left, right, tuple(sorted(shared, key=str.casefold)), tuple(sorted(union, key=str.casefold)), jaccard))
        return tuple(out)

    def consolidate_relations(self) -> tuple[AbstractionRelationV108, ...]:
        eligible = {self._pair_key(left, right): (left, right, shared, union, jaccard)
                    for left, right, shared, union, jaccard in self._eligible_pairs()}
        for key in tuple(self._maturity):
            if key not in eligible:
                del self._maturity[key]
        for key in eligible:
            self._maturity[key] = self._maturity.get(key, 0) + 1
        self._rebuild_relations()
        self._persist_state()
        return self.relations()

    def _rebuild_relations(self) -> None:
        relations: list[AbstractionRelationV108] = []
        for left, right, shared, union, jaccard in sorted(
            self._eligible_pairs(), key=lambda item: self._pair_key(item[0], item[1])
        ):
            key = self._pair_key(left, right)
            maturity = self._maturity.get(key, 0)
            if maturity < self.relation_min_stability_cycles:
                continue
            evidence = tuple(dict.fromkeys((*left.memory_ids, *right.memory_ids)))
            relations.append(
                AbstractionRelationV108(
                    relation_id=f"abstraction-relation:{len(relations) + 1:08d}",
                    left_abstraction_id=left.abstraction_id,
                    right_abstraction_id=right.abstraction_id,
                    relation="co_supported",
                    shared_entities=shared,
                    union_entities=union,
                    entity_jaccard=jaccard,
                    evidence_memory_ids=evidence,
                    maturity_cycles=maturity,
                )
            )
        self._relations = relations

    def _persist_state(self) -> None:
        if self.relations_path is None:
            return
        self.relations_path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "schema": "abstraction-relations-v108",
            "relation_min_shared_entities": self.relation_min_shared_entities,
            "relation_min_entity_jaccard": self.relation_min_entity_jaccard,
            "relation_min_stability_cycles": self.relation_min_stability_cycles,
            "maturity": [
                {"left": list(key[0]), "right": list(key[1]), "cycles": cycles}
                for key, cycles in sorted(self._maturity.items())
            ],
            "relations": [asdict(relation) for relation in self._relations],
        }
        tmp = self.relations_path.with_suffix(self.relations_path.suffix + ".tmp")
        tmp.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        tmp.replace(self.relations_path)

    def _load_state(self) -> None:
        raw = json.loads(self.relations_path.read_text(encoding="utf-8"))
        if raw.get("schema") != "abstraction-relations-v108":
            raise ValueError("unsupported abstraction-relations schema")
        self._maturity = {
            (tuple(item.get("left", [])), tuple(item.get("right", []))): int(item.get("cycles", 0))
            for item in raw.get("maturity", [])
        }
