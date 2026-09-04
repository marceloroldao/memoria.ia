from __future__ import annotations

from dataclasses import dataclass

from .concept_aware_conversation import ConceptAwareConversationResolver
from .concept_relations import ConceptRelationPath, ConceptRelationView
from .product_conversation import ConversationResolveResult, ConversationSemanticService
from .semantic_concepts import normalize_concept_surface


@dataclass(frozen=True, slots=True)
class QueryAnchor:
    surface: str
    key: str
    status: str


@dataclass(frozen=True, slots=True)
class ConceptPathConversationTrace:
    original_status: str
    alias_status: str
    path_attempted: bool
    final_status: str
    reason: str
    anchors: tuple[QueryAnchor, ...] = ()
    evidence_ids: tuple[str, ...] = ()


class ConceptPathConversationResolver:
    """Third-chance conversational resolver over explicit concept-relation paths.

    Ingest delegates unchanged to the wrapped concept-aware service. Only resolve
    is intercepted, so the product retains one authoritative write path.
    """

    def __init__(self, concept_aware: ConceptAwareConversationResolver, conversation: ConversationSemanticService, relation_view: ConceptRelationView, *, max_alias_words: int = 6, max_hops: int = 3, max_paths: int = 3, min_confidence: float = 0.9) -> None:
        if max_alias_words < 1:
            raise ValueError("max_alias_words must be >= 1")
        if max_hops < 1 or max_paths < 1:
            raise ValueError("max_hops and max_paths must be >= 1")
        if not 0.0 <= min_confidence <= 1.0:
            raise ValueError("min_confidence must be in [0, 1]")
        self.concept_aware = concept_aware
        self.conversation = conversation
        self.relation_view = relation_view
        self.max_alias_words = max_alias_words
        self.max_hops = max_hops
        self.max_paths = max_paths
        self.min_confidence = min_confidence
        self.last_trace: ConceptPathConversationTrace | None = None

    def ingest(self, **kwargs):
        return self.concept_aware.ingest(**kwargs)

    def _anchors(self, query: str, *, namespace: str | None) -> tuple[QueryAnchor, ...]:
        normalized = normalize_concept_surface(query)
        words = normalized.split()
        relations = self.relation_view.active_relations(namespace=namespace)
        graph_keys = {row.subject.key for row in relations} | {row.object.key for row in relations}
        graph_surfaces: dict[str, str] = {}
        for row in relations:
            graph_surfaces.setdefault(row.subject.key, row.subject.surface)
            graph_surfaces.setdefault(row.object.key, row.object.surface)

        found: dict[str, QueryAnchor] = {}
        haystack = f" {normalized} "
        for key, surface in graph_surfaces.items():
            if not key.startswith("surface:"):
                continue
            needle = normalize_concept_surface(surface)
            if needle and f" {needle} " in haystack:
                found[key] = QueryAnchor(surface, key, "LEXICAL")

        for width in range(min(self.max_alias_words, len(words)), 0, -1):
            for start in range(0, len(words) - width + 1):
                surface = " ".join(words[start : start + width])
                resolution = self.relation_view.concepts.resolve_with_context(
                    self.relation_view.scope,
                    surface,
                    query,
                    namespace=self.relation_view.concept_namespace,
                )
                if resolution.status != "HIT" or resolution.concept_id is None:
                    continue
                key = f"concept:{resolution.concept_id}"
                if key not in graph_keys:
                    continue
                found.setdefault(key, QueryAnchor(surface, key, "CONCEPT"))
        return tuple(sorted(found.values(), key=lambda item: (item.key, item.surface)))

    def _path_rows_result(self, path: ConceptRelationPath, *, namespace: str | None) -> ConversationResolveResult:
        ids = tuple(dict.fromkeys(path.evidence_ids))
        by_id = {
            edge.evidence_id: edge
            for edge in self.conversation.evidence.core.active_edges(namespace=namespace)
            if edge.evidence_id in ids
        }
        rows = [by_id[memory_id] for memory_id in ids if memory_id in by_id]
        if len(rows) != len(ids):
            return ConversationResolveResult("UNRESOLVED", 0.0, (), "", (), ())
        return self.conversation._result("HIT", rows, confidence=path.confidence, namespace=namespace)

    def resolve_with_trace(self, *, query: str, session_id: str | None = None):
        second, alias_trace = self.concept_aware.resolve_with_trace(query=query, session_id=session_id)
        alias_status = str(getattr(second, "status", ""))
        if alias_status == "HIT":
            trace = ConceptPathConversationTrace(alias_trace.original_status, alias_status, False, "HIT", alias_trace.reason or "alias_hit")
            self.last_trace = trace
            return second, trace

        anchors = self._anchors(query, namespace=session_id)
        if len(anchors) != 2:
            trace = ConceptPathConversationTrace(alias_trace.original_status, alias_status, False, alias_status or "UNRESOLVED", "anchor_count", anchors)
            self.last_trace = trace
            return second, trace

        a, b = anchors
        forward = self.relation_view.infer_path(a.surface, b.surface, namespace=session_id, context=query, max_hops=self.max_hops, max_paths=self.max_paths, min_confidence=self.min_confidence)
        reverse = self.relation_view.infer_path(b.surface, a.surface, namespace=session_id, context=query, max_hops=self.max_hops, max_paths=self.max_paths, min_confidence=self.min_confidence)
        directions = [item for item in (forward, reverse) if item.status == "HIT" and item.paths]
        if len(directions) != 1:
            trace = ConceptPathConversationTrace(alias_trace.original_status, alias_status, True, "UNRESOLVED", "no_unique_direction" if directions else "no_path", anchors)
            self.last_trace = trace
            return second, trace

        chosen = directions[0]
        best_conf = max(path.confidence for path in chosen.paths)
        best = [path for path in chosen.paths if abs(path.confidence - best_conf) < 1e-12]
        if len(best) != 1:
            trace = ConceptPathConversationTrace(alias_trace.original_status, alias_status, True, "UNRESOLVED", "ambiguous_paths", anchors)
            self.last_trace = trace
            return second, trace

        result = self._path_rows_result(best[0], namespace=session_id)
        trace = ConceptPathConversationTrace(alias_trace.original_status, alias_status, True, result.status, "concept_path" if result.status == "HIT" else "missing_evidence", anchors, best[0].evidence_ids if result.status == "HIT" else ())
        self.last_trace = trace
        return result, trace

    def resolve(self, *, query: str, session_id: str | None = None):
        result, _trace = self.resolve_with_trace(query=query, session_id=session_id)
        return result
