from __future__ import annotations

from dataclasses import asdict, dataclass
import json
from pathlib import Path

from .abstraction_relations_v108 import RelationalAbstractionMemoryV108, AbstractionRelationV108
from .semantic_structure_v101 import StructuredObservationV101


@dataclass(frozen=True, slots=True)
class CandidateOntologyV109:
    ontology_id: str
    abstraction_ids: tuple[str, ...]
    relation_ids: tuple[str, ...]
    predicates: tuple[str, ...]
    shared_entities: tuple[str, ...]
    evidence_memory_ids: tuple[str, ...]
    graph_density: float
    maturity_cycles: int
    status: str = "candidate"
    kind: str = "candidate_ontology"


class CandidateOntologyMemoryV109:
    """Form conservative candidate ontologies from consolidated v1.08 relations.

    This layer does not assert taxonomy, causality, implication, or universal truth.
    A candidate ontology is only a stable connected structure of already-consolidated
    abstractions and ``co_supported`` relations. Promotion happens on an explicit
    slower clock via ``consolidate_ontology()`` and requires minimum graph size,
    relation density, shared entity diversity, and repeated stability cycles.
    """

    def __init__(
        self,
        *,
        ontology_path: str | Path | None = None,
        ontology_min_abstractions: int = 3,
        ontology_min_relations: int = 2,
        ontology_min_shared_entities: int = 3,
        ontology_min_graph_density: float = 0.50,
        ontology_min_stability_cycles: int = 2,
        **relation_kwargs,
    ) -> None:
        if ontology_min_abstractions < 3:
            raise ValueError("ontology_min_abstractions must be >= 3")
        if ontology_min_relations < 2:
            raise ValueError("ontology_min_relations must be >= 2")
        if ontology_min_shared_entities < 2:
            raise ValueError("ontology_min_shared_entities must be >= 2")
        if not 0.0 <= ontology_min_graph_density <= 1.0:
            raise ValueError("ontology_min_graph_density must be between 0 and 1")
        if ontology_min_stability_cycles < 1:
            raise ValueError("ontology_min_stability_cycles must be >= 1")

        self.relational = RelationalAbstractionMemoryV108(**relation_kwargs)
        self.ontology_path = Path(ontology_path) if ontology_path is not None else None
        self.ontology_min_abstractions = ontology_min_abstractions
        self.ontology_min_relations = ontology_min_relations
        self.ontology_min_shared_entities = ontology_min_shared_entities
        self.ontology_min_graph_density = ontology_min_graph_density
        self.ontology_min_stability_cycles = ontology_min_stability_cycles
        self._maturity: dict[tuple[str, ...], int] = {}
        self._ontologies: list[CandidateOntologyV109] = []
        if self.ontology_path and self.ontology_path.exists():
            self._load_state()
        self._rebuild_ontologies()

    def observe(
        self,
        text: str,
        *,
        provenance: str = "conversation",
        namespace: str | None = None,
    ) -> StructuredObservationV101:
        observed = self.relational.observe(text, provenance=provenance, namespace=namespace)
        self._rebuild_ontologies()
        self._persist_state()
        return observed

    def query(self, text: str, *, top_k: int = 3):
        return self.relational.query(text, top_k=top_k)

    def consolidate_abstractions(self):
        result = self.relational.consolidate_abstractions()
        self._rebuild_ontologies()
        self._persist_state()
        return result

    def consolidate_relations(self):
        result = self.relational.consolidate_relations()
        self._rebuild_ontologies()
        self._persist_state()
        return result

    def abstractions(self):
        return self.relational.abstractions()

    def relations(self):
        return self.relational.relations()

    def ontologies(self) -> tuple[CandidateOntologyV109, ...]:
        return tuple(self._ontologies)

    @staticmethod
    def _component_key(abstraction_ids: tuple[str, ...]) -> tuple[str, ...]:
        return tuple(sorted(abstraction_ids))

    def _eligible_components(self):
        abstractions = {a.abstraction_id: a for a in self.relational.abstractions()}
        relations = tuple(r for r in self.relational.relations() if r.relation == "co_supported")
        adjacency: dict[str, set[str]] = {aid: set() for aid in abstractions}
        by_pair: dict[frozenset[str], AbstractionRelationV108] = {}
        for relation in relations:
            left, right = relation.left_abstraction_id, relation.right_abstraction_id
            if left not in abstractions or right not in abstractions:
                continue
            adjacency[left].add(right)
            adjacency[right].add(left)
            by_pair[frozenset((left, right))] = relation

        visited: set[str] = set()
        out = []
        for root in sorted(adjacency):
            if root in visited or not adjacency[root]:
                continue
            stack = [root]
            component: set[str] = set()
            while stack:
                node = stack.pop()
                if node in visited:
                    continue
                visited.add(node)
                component.add(node)
                stack.extend(adjacency[node] - visited)

            ids = tuple(sorted(component))
            if len(ids) < self.ontology_min_abstractions:
                continue
            comp_relations = [
                relation for pair, relation in by_pair.items()
                if pair.issubset(component)
            ]
            if len(comp_relations) < self.ontology_min_relations:
                continue
            possible_edges = len(ids) * (len(ids) - 1) / 2
            density = len(comp_relations) / possible_edges if possible_edges else 0.0
            if density < self.ontology_min_graph_density:
                continue

            entity_sets = [set(abstractions[aid].entities) for aid in ids]
            shared_entities = set.intersection(*entity_sets) if entity_sets else set()
            if len(shared_entities) < self.ontology_min_shared_entities:
                continue

            out.append((ids, tuple(sorted(comp_relations, key=lambda r: r.relation_id)), density, tuple(sorted(shared_entities, key=str.casefold))))
        return tuple(out)

    def consolidate_ontology(self) -> tuple[CandidateOntologyV109, ...]:
        eligible = {self._component_key(ids): (ids, relations, density, shared)
                    for ids, relations, density, shared in self._eligible_components()}
        for key in tuple(self._maturity):
            if key not in eligible:
                del self._maturity[key]
        for key in eligible:
            self._maturity[key] = self._maturity.get(key, 0) + 1
        self._rebuild_ontologies()
        self._persist_state()
        return self.ontologies()

    def _rebuild_ontologies(self) -> None:
        abstraction_map = {a.abstraction_id: a for a in self.relational.abstractions()}
        ontologies: list[CandidateOntologyV109] = []
        for ids, relations, density, shared in sorted(self._eligible_components(), key=lambda item: item[0]):
            key = self._component_key(ids)
            maturity = self._maturity.get(key, 0)
            if maturity < self.ontology_min_stability_cycles:
                continue
            predicates = tuple(sorted({abstraction_map[aid].predicate for aid in ids}))
            evidence = tuple(dict.fromkeys(
                memory_id
                for aid in ids
                for memory_id in abstraction_map[aid].memory_ids
            ))
            ontologies.append(
                CandidateOntologyV109(
                    ontology_id=f"candidate-ontology:{len(ontologies) + 1:08d}",
                    abstraction_ids=ids,
                    relation_ids=tuple(r.relation_id for r in relations),
                    predicates=predicates,
                    shared_entities=shared,
                    evidence_memory_ids=evidence,
                    graph_density=density,
                    maturity_cycles=maturity,
                )
            )
        self._ontologies = ontologies

    def _persist_state(self) -> None:
        if self.ontology_path is None:
            return
        self.ontology_path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "schema": "candidate-ontology-v109",
            "ontology_min_abstractions": self.ontology_min_abstractions,
            "ontology_min_relations": self.ontology_min_relations,
            "ontology_min_shared_entities": self.ontology_min_shared_entities,
            "ontology_min_graph_density": self.ontology_min_graph_density,
            "ontology_min_stability_cycles": self.ontology_min_stability_cycles,
            "maturity": [
                {"abstraction_ids": list(key), "cycles": cycles}
                for key, cycles in sorted(self._maturity.items())
            ],
            "ontologies": [asdict(item) for item in self._ontologies],
        }
        tmp = self.ontology_path.with_suffix(self.ontology_path.suffix + ".tmp")
        tmp.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        tmp.replace(self.ontology_path)

    def _load_state(self) -> None:
        raw = json.loads(self.ontology_path.read_text(encoding="utf-8"))
        if raw.get("schema") != "candidate-ontology-v109":
            raise ValueError("unsupported candidate-ontology schema")
        self._maturity = {
            tuple(item.get("abstraction_ids", [])): int(item.get("cycles", 0))
            for item in raw.get("maturity", [])
        }
