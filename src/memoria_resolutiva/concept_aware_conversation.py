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
    """Rewrite explicit aliases, using only explicit context cues for polysemy."""
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
            contextual = None
            if resolution.reason == "ambiguous":
                contextual = store.resolve_with_context(scope, surface, original, namespace=namespace)
                if contextual.status == "HIT" and contextual.concept_id is not None:
                    resolution = contextual
                else:
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
                        "ambiguous_context" if contextual is not None and contextual.reason == "ambiguous_context" else "ambiguous_concept",
                        tuple(ambiguous_matches),
                    )
            if resolution.status != "HIT" or resolution.concept_id is None:
                continue
            concept = store.get(scope, resolution.concept_id, namespace=namespace)
            if concept is None:
                return ConceptRewrite("UNRESOLVED", original, original, resolution.candidate_ids, "missing_concept", tuple(matches))
            canonical = concept.normalized_canonical
            rewritten.extend(canonical.split())
            concept_ids.append(concept.concept_id)
            matches.append(
                ConceptMatch(
                    surface=surface,
                    canonical=canonical,
                    concept_id=concept.concept_id,
                    sense_key=concept.sense_key,
                    status="CONTEXT_HIT" if resolution.reason == "context_cue" else "HIT",
                    candidate_ids=resolution.candidate_ids or (concept.concept_id,),
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
    """Second-chance resolver using explicit semantic concepts only after a miss.

    Ingest is deliberately transparent so this wrapper can sit on the production
    conversation boundary without becoming a second write path.
    """

    def __init__(self, base: ConversationResolver, concepts: PersistentSemanticConceptStore, *, scope: MemoryScope, concept_namespace: str | None = None, max_alias_words: int = 6) -> None:
        self.base = base
        self.concepts = concepts
        self.scope = scope
        self.concept_namespace = concept_namespace
        self.max_alias_words = max_alias_words
        self.last_trace: ConceptResolutionTrace | None = None

    def ingest(self, **kwargs):
        ingest = getattr(self.base, "ingest", None)
        if ingest is None:
            raise AttributeError("wrapped conversation service does not support ingest")
        return ingest(**kwargs)

    def resolve_with_trace(self, *, query: str, session_id: str | None = None):
        first = self.base.resolve(query=query, session_id=session_id)
        first_status = str(getattr(first, "status", ""))
        normalized_original = " ".join(str(query).split()).strip()
        if first_status == "HIT":
            trace = ConceptResolutionTrace(normalized_original, first_status, "SKIPPED", normalized_original, False, first_status, "original_hit", ())
            self.last_trace = trace
            return first, trace

        rewrite = rewrite_query_with_explicit_concepts(self.concepts, self.scope, query, namespace=self.concept_namespace, max_alias_words=self.max_alias_words)
        if rewrite.status != "REWRITTEN" or rewrite.rewritten_query == rewrite.original_query:
            trace = ConceptResolutionTrace(rewrite.original_query, first_status, rewrite.status, rewrite.rewritten_query, False, first_status, rewrite.reason, rewrite.matches)
            self.last_trace = trace
            return first, trace

        second = self.base.resolve(query=rewrite.rewritten_query, session_id=session_id)
        final_status = str(getattr(second, "status", ""))
        trace = ConceptResolutionTrace(rewrite.original_query, first_status, rewrite.status, rewrite.rewritten_query, True, final_status, "concept_retry", rewrite.matches)
        self.last_trace = trace
        return second, trace

    def resolve(self, *, query: str, session_id: str | None = None):
        result, _trace = self.resolve_with_trace(query=query, session_id=session_id)
        return result
