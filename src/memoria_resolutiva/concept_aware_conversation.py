from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from .product_identity import MemoryScope
from .semantic_concept_store import PersistentSemanticConceptStore
from .semantic_concepts import normalize_concept_surface


class ConversationResolver(Protocol):
    def resolve(self, *, query: str, session_id: str | None = None): ...


@dataclass(frozen=True, slots=True)
class ConceptRewrite:
    status: str
    original_query: str
    rewritten_query: str
    concept_ids: tuple[str, ...] = ()
    reason: str | None = None


def rewrite_query_with_explicit_concepts(
    store: PersistentSemanticConceptStore,
    scope: MemoryScope,
    query: str,
    *,
    namespace: str | None,
    max_alias_words: int = 6,
) -> ConceptRewrite:
    """Rewrite only explicitly registered, unambiguous aliases.

    The input is normalized to the same deterministic lexical surface used by the
    concept registry. Longest registered aliases win. Unknown spans are left as
    ordinary query terms. If any matched alias is ambiguous, rewriting fails
    closed and callers should keep the original unresolved result.
    """
    if max_alias_words < 1:
        raise ValueError("max_alias_words must be >= 1")
    original = " ".join(str(query).split()).strip()
    normalized = normalize_concept_surface(original)
    if not normalized:
        return ConceptRewrite("UNCHANGED", original, original, (), "empty")

    words = normalized.split()
    rewritten: list[str] = []
    concept_ids: list[str] = []
    changed = False
    i = 0
    while i < len(words):
        matched = False
        longest = min(max_alias_words, len(words) - i)
        for width in range(longest, 0, -1):
            surface = " ".join(words[i : i + width])
            resolution = store.resolve(scope, surface, namespace=namespace)
            if resolution.reason == "ambiguous":
                return ConceptRewrite(
                    "UNRESOLVED",
                    original,
                    original,
                    resolution.candidate_ids,
                    "ambiguous_concept",
                )
            if resolution.status != "HIT" or resolution.concept_id is None:
                continue
            concept = store.get(scope, resolution.concept_id, namespace=namespace)
            if concept is None:
                return ConceptRewrite(
                    "UNRESOLVED",
                    original,
                    original,
                    resolution.candidate_ids,
                    "missing_concept",
                )
            canonical = concept.normalized_canonical
            rewritten.extend(canonical.split())
            concept_ids.append(concept.concept_id)
            changed = changed or canonical != surface
            i += width
            matched = True
            break
        if not matched:
            rewritten.append(words[i])
            i += 1

    rewritten_query = " ".join(rewritten)
    if not changed:
        return ConceptRewrite("UNCHANGED", original, original, tuple(dict.fromkeys(concept_ids)), None)
    return ConceptRewrite("REWRITTEN", original, rewritten_query, tuple(dict.fromkeys(concept_ids)), None)


class ConceptAwareConversationResolver:
    """Second-chance resolver using explicit concept aliases only after a miss.

    Existing conversation behavior always gets the first attempt. A concept-aware
    retry occurs only when the first result is not HIT and query rewriting is both
    unambiguous and actually changes the query. This keeps the semantic concept
    layer additive and fail-closed while Phase B matures.
    """

    def __init__(
        self,
        base: ConversationResolver,
        concepts: PersistentSemanticConceptStore,
        *,
        scope: MemoryScope,
        concept_namespace: str | None = None,
        max_alias_words: int = 6,
    ) -> None:
        self.base = base
        self.concepts = concepts
        self.scope = scope
        self.concept_namespace = concept_namespace
        self.max_alias_words = max_alias_words

    def resolve(self, *, query: str, session_id: str | None = None):
        first = self.base.resolve(query=query, session_id=session_id)
        if str(getattr(first, "status", "")) == "HIT":
            return first

        rewrite = rewrite_query_with_explicit_concepts(
            self.concepts,
            self.scope,
            query,
            namespace=self.concept_namespace,
            max_alias_words=self.max_alias_words,
        )
        if rewrite.status != "REWRITTEN" or rewrite.rewritten_query == rewrite.original_query:
            return first
        return self.base.resolve(query=rewrite.rewritten_query, session_id=session_id)
