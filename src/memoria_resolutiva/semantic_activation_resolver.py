from __future__ import annotations

from .graph_predicate_cues import resolve_graph_semantic_cues
from .relational_activation import activate as activate_relations
from .semantic_activation_plan import plan_activation_concepts


class SemanticActivationConversationResolver:
    """Conversation resolver proxy that adds bounded graph-semantic activation.

    Ordinary ``resolve`` calls are delegated unchanged. Structural activation first
    discovers graph-declared concept bridges for the requested concept, applies the
    shared activation planner, and aggregates at most two structural activations.
    """

    def __init__(self, resolver: object, *, max_concepts: int = 2):
        if max_concepts < 1:
            raise ValueError("max_concepts must be >= 1")
        self._resolver = resolver
        self.max_concepts = max_concepts

    @property
    def evidence(self):
        return getattr(self._resolver, "evidence", None)

    def resolve(self, *, query: str, session_id: str | None = None):
        return self._resolver.resolve(query=query, session_id=session_id)

    def __getattr__(self, name: str):
        return getattr(self._resolver, name)

    def activate_relations(
        self,
        *,
        concept: str,
        session_id: str | None = None,
        depth: int = 2,
        budget: int = 1200,
        hop_decay: float = 0.72,
        min_confidence: float = 0.45,
    ) -> dict:
        semantic = resolve_graph_semantic_cues(
            self._resolver,
            message=concept,
            session_id=session_id,
            target="",
            max_query_terms=1,
        )
        plan = plan_activation_concepts(
            (concept,),
            semantic.concept_terms,
            max_concepts=self.max_concepts,
        )

        contexts: list[str] = []
        evidence_ids: list[str] = []
        concepts: list[str] = []
        confidences: list[float] = []
        status_seen = "UNRESOLVED"
        used = 0

        for planned in plan:
            result = activate_relations(
                self._resolver,
                concept=planned,
                session_id=session_id,
                depth=depth,
                budget=budget,
                hop_decay=hop_decay,
                min_confidence=min_confidence,
            )
            if result.status == "UNSUPPORTED":
                if status_seen == "UNRESOLVED":
                    status_seen = "UNSUPPORTED"
                continue
            if result.status != "HIT" or not result.selected_context:
                continue
            status_seen = "HIT"
            for line in result.selected_context.splitlines():
                normalized = " ".join(line.split()).strip()
                if not normalized or normalized in contexts:
                    continue
                cost = len(normalized) + (1 if contexts else 0)
                if used + cost > budget:
                    continue
                contexts.append(normalized)
                used += cost
            for item in result.memory_ids:
                if item and item not in evidence_ids:
                    evidence_ids.append(item)
            for item in result.concepts:
                if item and item not in concepts:
                    concepts.append(item)
            confidences.append(result.confidence)

        if status_seen != "HIT" or not contexts:
            return {
                "status": status_seen,
                "confidence": 0.0,
                "selected_context": "",
                "relations": [],
            }

        rows = [
            {
                "subject_key": concepts[0] if concepts else concept,
                "object_key": item,
                "evidence_id": evidence_id,
            }
            for item, evidence_id in zip(concepts[1:] or concepts, evidence_ids)
        ]
        if not rows:
            rows = [{"subject_key": concept, "object_key": concept, "evidence_id": evidence_id} for evidence_id in evidence_ids]

        return {
            "status": "HIT",
            "confidence": min(confidences) if confidences else 0.0,
            "selected_context": "\n".join(contexts),
            "relations": rows,
        }
