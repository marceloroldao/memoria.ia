from __future__ import annotations

from dataclasses import dataclass

from .candidate_ontology_v109 import CandidateOntologyMemoryV109


_PREDICATE_HINTS = {
    "has_voltage": ("tensão", "tensao", "voltagem", "voltage", "volt", "v"),
    "powers": ("alimenta", "alimentação", "alimentacao", "energiza", "energia", "powers"),
    "belongs_to": ("pertence", "projeto", "belongs"),
    "measures": ("mede", "medição", "medicao", "measures"),
    "located_at": ("local", "localização", "localizacao", "located"),
}


@dataclass(frozen=True, slots=True)
class GuidedEvidenceV110:
    memory_id: str
    text: str
    predicate: str
    ontology_id: str
    kind: str = "source_evidence"


@dataclass(frozen=True, slots=True)
class OntologyGuidedResultV110:
    query: str
    direct_result: object
    guided_evidence: tuple[GuidedEvidenceV110, ...]
    matched_predicates: tuple[str, ...]
    ontology_ids: tuple[str, ...]
    ontology_used: bool
    synthesized_claims: int = 0


class OntologyGuidedMemoryV110:
    """Use candidate ontologies only as routing hints to original evidence.

    v1.10 never turns a candidate ontology into a factual answer. The upper layer
    may select which consolidated abstraction/evidence paths are worth inspecting,
    but returned items are always original memory records. If no supported lexical
    predicate hint or no candidate ontology exists, the guided path abstains.
    """

    def __init__(self, **kwargs) -> None:
        self.ontology = CandidateOntologyMemoryV109(**kwargs)

    def observe(self, text: str, *, provenance: str = "conversation", namespace: str | None = None):
        return self.ontology.observe(text, provenance=provenance, namespace=namespace)

    def query(self, text: str, *, top_k: int = 3):
        return self.ontology.query(text, top_k=top_k)

    def consolidate_abstractions(self):
        return self.ontology.consolidate_abstractions()

    def consolidate_relations(self):
        return self.ontology.consolidate_relations()

    def consolidate_ontology(self):
        return self.ontology.consolidate_ontology()

    @staticmethod
    def _matched_predicates(text: str) -> tuple[str, ...]:
        folded = text.casefold()
        out = []
        for predicate, hints in _PREDICATE_HINTS.items():
            if any(hint in folded.split() or hint in folded for hint in hints):
                out.append(predicate)
        return tuple(sorted(set(out)))

    def _base_memory(self):
        return (
            self.ontology.relational.abstraction_memory.pattern_memory
            .episodic.events_memory.temporal.convergent.structured.memory
        )

    def guided_query(self, text: str, *, top_k: int = 3) -> OntologyGuidedResultV110:
        direct = self.query(text, top_k=top_k)
        predicates = self._matched_predicates(text)
        if not predicates or not self.ontology.ontologies():
            return OntologyGuidedResultV110(text, direct, (), predicates, (), False)

        abstractions = {a.abstraction_id: a for a in self.ontology.abstractions()}
        base = self._base_memory()
        evidence: list[GuidedEvidenceV110] = []
        ontology_ids: list[str] = []
        seen: set[str] = set()

        for ontology in self.ontology.ontologies():
            selected = [
                abstractions[aid]
                for aid in ontology.abstraction_ids
                if aid in abstractions and abstractions[aid].predicate in predicates
            ]
            if not selected:
                continue
            ontology_ids.append(ontology.ontology_id)
            for abstraction in selected:
                for memory_id in abstraction.memory_ids:
                    if memory_id in seen:
                        continue
                    record, _metrics = base.exact_lookup(memory_id)
                    if record is None:
                        continue
                    seen.add(memory_id)
                    evidence.append(
                        GuidedEvidenceV110(
                            memory_id=record.memory_id,
                            text=record.text,
                            predicate=abstraction.predicate,
                            ontology_id=ontology.ontology_id,
                        )
                    )
                    if len(evidence) >= top_k:
                        break
                if len(evidence) >= top_k:
                    break
            if len(evidence) >= top_k:
                break

        return OntologyGuidedResultV110(
            query=text,
            direct_result=direct,
            guided_evidence=tuple(evidence),
            matched_predicates=predicates,
            ontology_ids=tuple(ontology_ids),
            ontology_used=bool(evidence),
            synthesized_claims=0,
        )
