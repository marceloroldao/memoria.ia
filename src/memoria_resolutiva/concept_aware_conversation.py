from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from .product_identity import MemoryScope
from .semantic_concept_store import PersistentSemanticConceptStore
from .semantic_concepts import normalize_concept_surface


class ConversationResolver(Protocol):
    def resolve(self, *, query: str, session_id: str | None = None): ...


@dataclass(frozen=True, slots=True)
class ConceptMatch:
    surface: str
    canonical: str | None
    concept_id: str | None
    sense_key: str | None
    status: str
    candidate_ids: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class ConceptRewrite:
    status: str
    original_query: str
    rewritten_query: str
    concept_ids: tuple[str, ...] = ()
    reason: str | None = None
    matches: tuple[ConceptMatch, ...] = ()


@dataclass(frozen=True, slots=True)
class ConceptResolutionTrace:
    original_query: str
    original_status: str
    rewrite_status: str
    rewritten_query: str
    retry_attempted: bool
    final_status: str
    reason: str | None
    matches: tuple[ConceptMatch, ...] = ()


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

    Every concept match is recorded so callers can audit which explicit alias and
    semantic sense participated in a retry without changing the ordinary resolver
    response contract.
    """
    if max_alias_words < 1:
        raise ValueError("max_alias_words must be >= 1")
    original = " ".join(str(query).split()).strip()
    normalized = normalize_concept_surface(original)
    if not normalized:
        return ConceptRewrite("UNCHANGED", original, original, (), "empty", ())

    words = normalized.split()
    rewritten: list[str] = []
    concept_ids: list[str] = []
    matches: list[ConceptMatch] = []
    changed = False
    i = 0
    while i < len(words):
        matched = False
        longest = min(max_alias_words, len(words) - i)
        for width in range(longest, 0, -1):
            surface = " ".join(words[i : i + width])
            resolution = store.resolve(scope, surface, namespace=namespace)
            if resolution.reason == "ambiguous":
                ambiguous_matches: list[ConceptMatch] = []
                for candidate_id in resolution.candidate_ids:
                    concept = store.get(scope, candidate_id, namespace=namespace)
                    ambiguous_matches.append(
                        ConceptMatch(
                            surface=surface,
                            canonical=None if concept is None else concept.normalized_canonical,
                            concept_id=candidate_id,
                            sense_key=None if concept is None else concept.sense_key,
                            status="AMBIGUOUS",
                            candidate_ids=resolution.candidate_ids,
                        )
                    )
                return ConceptRewrite(
                    "UNRESOLVED",
                    original,
                    original,
                    resolution.candidate_ids,
                    "ambiguous_concept",
                    tuple(ambiguous_matches),
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
                    tuple(matches),
                )
            canonical = concept.normalized_canonical
            rewritten.extend(canonical.split())
            concept_ids.append(concept.concept_id)
            matches.append(
                ConceptMatch(
                    surface=surface,
                    canonical=canonical,
                    concept_id=concept.concept_id,
                    sense_key=concept.sense_key,
                    status="HIT",
                    candidate_ids=(concept.concept_id,),
                )
            )
            changed = changed or canonical != surface
            i += width
            matched = True
            break
        if not matched:
            rewritten.append(words[i])
            i += 1

    rewritten_query = " ".join(rewritten)
    unique_ids = tuple(dict.fromkeys(concept_ids))
    if not changed:
        return ConceptRewrite("UNCHANGED", original, original, unique_ids, None, tuple(matches))
    return ConceptRewrite("REWRITTEN", original, rewritten_query, unique_ids, None, tuple(matches))


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
        self.last_trace: ConceptResolutionTrace | None = None

    def resolve_with_trace(self, *, query: str, session_id: str | None = None):
        first = self.base.resolve(query=query, session_id=session_id)
        first_status = str(getattr(first, "status", ""))
        normalized_original = " ".join(str(query).split()).strip()
        if first_status == "HIT":
            trace = ConceptResolutionTrace(
                original_query=normalized_original,
                original_status=first_status,
                rewrite_status="SKIPPED",
                rewritten_query=normalized_original,
                retry_attempted=False,
                final_status=first_status,
                reason="original_hit",
                matches=(),
            )
            self.last_trace = trace
            return first, trace

        rewrite = rewrite_query_with_explicit_concepts(
            self.concepts,
            self.scope,
            query,
            namespace=self.concept_namespace,
            max_alias_words=self.max_alias_words,
        )
        if rewrite.status != "REWRITTEN" or rewrite.rewritten_query == rewrite.original_query:
            trace = ConceptResolutionTrace(
                original_query=rewrite.original_query,
                original_status=first_status,
                rewrite_status=rewrite.status,
                rewritten_query=rewrite.rewritten_query,
                retry_attempted=False,
                final_status=first_status,
                reason=rewrite.reason,
                matches=rewrite.matches,
            )
            self.last_trace = trace
            return first, trace

        second = self.base.resolve(query=rewrite.rewritten_query, session_id=session_id)
        final_status = str(getattr(second, "status", ""))
        trace = ConceptResolutionTrace(
            original_query=rewrite.original_query,
            original_status=first_status,
            rewrite_status=rewrite.status,
            rewritten_query=rewrite.rewritten_query,
            retry_attempted=True,
            final_status=final_status,
            reason="concept_retry",
            matches=rewrite.matches,
        )
        self.last_trace = trace
        return second, trace

    def resolve(self, *, query: str, session_id: str | None = None):
        result, _trace = self.resolve_with_trace(query=query, session_id=session_id)
        return result
