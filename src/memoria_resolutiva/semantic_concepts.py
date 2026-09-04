from __future__ import annotations

from dataclasses import dataclass
import hashlib
import unicodedata


@dataclass(frozen=True, slots=True)
class SemanticConcept:
    concept_id: str
    canonical_name: str
    normalized_canonical: str
    namespace: str | None
    sense_key: str | None
    aliases: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class ConceptResolution:
    status: str
    concept_id: str | None
    candidate_ids: tuple[str, ...]
    normalized_query: str
    reason: str | None = None


def normalize_concept_surface(value: str) -> str:
    """Deterministic lexical normalization for explicit concept identity.

    This is deliberately not a fuzzy semantic model. It normalizes Unicode,
    accents, case, punctuation and repeated whitespace so explicitly registered
    aliases can share one stable lookup surface without introducing guessed
    synonyms into the memory core.
    """
    value = unicodedata.normalize("NFKD", str(value))
    value = "".join(ch for ch in value if not unicodedata.combining(ch))
    chars: list[str] = []
    for ch in value.casefold():
        if ch.isalnum() or ch == "_":
            chars.append(ch)
        else:
            chars.append(" ")
    return " ".join("".join(chars).split())


def _stable_concept_id(*, namespace: str | None, canonical: str, sense_key: str | None) -> str:
    raw = "\0".join((namespace or "", canonical, sense_key or "")).encode("utf-8")
    return "concept:" + hashlib.sha256(raw).hexdigest()[:24]


class SemanticConceptIndex:
    """Deterministic explicit concept/alias registry with fail-closed ambiguity.

    A surface form may intentionally point to multiple concepts. Such collisions
    are preserved as separate senses and resolution returns UNRESOLVED rather
    than silently merging them. The index contains no built-in synonym table.
    """

    def __init__(self) -> None:
        self._concepts: dict[tuple[str | None, str], SemanticConcept] = {}
        self._surface_to_ids: dict[tuple[str | None, str], set[str]] = {}

    def register_concept(
        self,
        canonical_name: str,
        *,
        aliases: tuple[str, ...] | list[str] = (),
        namespace: str | None = None,
        sense_key: str | None = None,
        concept_id: str | None = None,
    ) -> SemanticConcept:
        canonical_name = " ".join(str(canonical_name).split()).strip()
        normalized_canonical = normalize_concept_surface(canonical_name)
        if not normalized_canonical:
            raise ValueError("canonical_name must contain at least one semantic token")

        normalized_sense = normalize_concept_surface(sense_key or "") or None
        concept_id = (concept_id or "").strip() or _stable_concept_id(
            namespace=namespace,
            canonical=normalized_canonical,
            sense_key=normalized_sense,
        )
        key = (namespace, concept_id)

        explicit_aliases: list[str] = []
        for value in (canonical_name, *aliases):
            surface = " ".join(str(value).split()).strip()
            normalized = normalize_concept_surface(surface)
            if not normalized:
                continue
            if normalized not in explicit_aliases:
                explicit_aliases.append(normalized)

        existing = self._concepts.get(key)
        if existing is not None:
            if (
                existing.normalized_canonical != normalized_canonical
                or existing.sense_key != normalized_sense
            ):
                raise ValueError("concept_id already belongs to a different concept identity")
            merged_aliases = tuple(dict.fromkeys((*existing.aliases, *explicit_aliases)))
            concept = SemanticConcept(
                concept_id=existing.concept_id,
                canonical_name=existing.canonical_name,
                normalized_canonical=existing.normalized_canonical,
                namespace=existing.namespace,
                sense_key=existing.sense_key,
                aliases=merged_aliases,
            )
        else:
            concept = SemanticConcept(
                concept_id=concept_id,
                canonical_name=canonical_name,
                normalized_canonical=normalized_canonical,
                namespace=namespace,
                sense_key=normalized_sense,
                aliases=tuple(explicit_aliases),
            )

        self._concepts[key] = concept
        for alias in concept.aliases:
            self._surface_to_ids.setdefault((namespace, alias), set()).add(concept.concept_id)
        return concept

    def resolve(self, surface: str, *, namespace: str | None = None) -> ConceptResolution:
        normalized = normalize_concept_surface(surface)
        if not normalized:
            return ConceptResolution("UNRESOLVED", None, (), normalized, "empty")
        candidates = tuple(sorted(self._surface_to_ids.get((namespace, normalized), ())))
        if not candidates:
            return ConceptResolution("UNRESOLVED", None, (), normalized, "unknown")
        if len(candidates) > 1:
            return ConceptResolution("UNRESOLVED", None, candidates, normalized, "ambiguous")
        return ConceptResolution("HIT", candidates[0], candidates, normalized, None)

    def get(self, concept_id: str, *, namespace: str | None = None) -> SemanticConcept | None:
        return self._concepts.get((namespace, concept_id))

    def aliases_for(self, concept_id: str, *, namespace: str | None = None) -> tuple[str, ...]:
        concept = self.get(concept_id, namespace=namespace)
        return concept.aliases if concept is not None else ()
