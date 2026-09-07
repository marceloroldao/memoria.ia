from __future__ import annotations

from dataclasses import dataclass
import re
import unicodedata

from .relational_activation import activate as activate_relations

_WORD_RE = re.compile(r"[\wÀ-ÿ.-]+", re.UNICODE)
_LEGACY_PREDICATE_CUE_PREDICATES = frozenset({"unidade_de", "unit_of"})
_SEMANTIC_ROLE_PREDICATES = frozenset({"semantic_role", "papel_semantico", "papel_semântico"})
_PREDICATE_ROLES = frozenset({"predicate", "predicado"})
_CONCEPT_ROLES = frozenset({"concept", "conceito"})
_DEFAULT_MAX_QUERY_TERMS = 4
_DEFAULT_BUDGET = 320


@dataclass(frozen=True, slots=True)
class GraphSemanticCueResult:
    predicate_terms: tuple[str, ...]
    concept_terms: tuple[str, ...]
    memory_ids: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class GraphPredicateCueResult:
    terms: tuple[str, ...]
    memory_ids: tuple[str, ...]


def _key(value: str) -> str:
    value = unicodedata.normalize("NFKD", value)
    value = "".join(ch for ch in value if not unicodedata.combining(ch))
    return " ".join(value.casefold().strip().split())


def _term_variants(value: str) -> tuple[str, ...]:
    """Return conservative lexical variants without domain vocabulary."""
    raw = value.strip(".,;:!?")
    if not raw:
        return ()
    out = [raw]
    key = _key(raw)
    if len(key) > 4 and key.endswith("s"):
        singular = raw[:-1]
        if singular and _key(singular) != key:
            out.append(singular)
    return tuple(dict.fromkeys(out))


def _parse_relation(line: str) -> tuple[str, str, str] | None:
    parts = [part.strip() for part in line.split("|", 2)]
    if len(parts) != 3 or not all(parts):
        return None
    return parts[0], parts[1], parts[2]


def _semantic_role_for_predicate(
    resolver: object,
    *,
    predicate: str,
    session_id: str | None,
    cache: dict[str, tuple[str, tuple[str, ...]]],
) -> tuple[str, tuple[str, ...]]:
    predicate_key = _key(predicate)
    if predicate_key in cache:
        return cache[predicate_key]

    if predicate_key in {_key(item) for item in _LEGACY_PREDICATE_CUE_PREDICATES}:
        result = ("predicate", ())
        cache[predicate_key] = result
        return result

    activated = activate_relations(
        resolver,
        concept=predicate,
        session_id=session_id,
        depth=1,
        budget=_DEFAULT_BUDGET,
    )
    if activated.status != "HIT":
        result = ("", ())
        cache[predicate_key] = result
        return result

    role = ""
    evidence_ids: list[str] = []
    for line in activated.selected_context.splitlines():
        parsed = _parse_relation(line)
        if parsed is None:
            continue
        subject, relation_predicate, object_ = parsed
        if _key(relation_predicate) not in {_key(item) for item in _SEMANTIC_ROLE_PREDICATES}:
            continue
        if _key(subject) == predicate_key:
            candidate_role = _key(object_)
        elif _key(object_) == predicate_key:
            candidate_role = _key(subject)
        else:
            continue
        if candidate_role in {_key(item) for item in _PREDICATE_ROLES}:
            role = "predicate"
        elif candidate_role in {_key(item) for item in _CONCEPT_ROLES}:
            role = "concept"
        if role:
            for evidence_id in activated.memory_ids:
                if evidence_id and evidence_id not in evidence_ids:
                    evidence_ids.append(evidence_id)
            break

    result = (role, tuple(evidence_ids))
    cache[predicate_key] = result
    return result


def resolve_graph_semantic_cues(
    resolver: object,
    *,
    message: str,
    session_id: str | None,
    target: str = "",
    ignored_terms: frozenset[str] = frozenset(),
    max_query_terms: int = _DEFAULT_MAX_QUERY_TERMS,
) -> GraphSemanticCueResult:
    """Resolve query interpretation cues from graph-declared semantic bridges.

    A relation predicate can declare its semantic role inside the graph::

        unidade_de | semantic_role | predicate
        tipo_de | semantic_role | concept
        tecnologia_de | semantic_role | concept

    Then ordinary knowledge can extend interpretation without code changes::

        volt | unidade_de | tensão
        ONU | tipo_de | equipamento
        EPON | tecnologia_de | rede

    Predicate-role bridges add terms used to rank graph predicates. Concept-role
    bridges add concepts that may be activated structurally. The resolver has no
    built-in list of units, device types, technologies, models or life stages.

    ``unidade_de``/``unit_of`` remain a compatibility shortcut for existing
    persisted memories and behave as predicate-role bridges even without an
    explicit ``semantic_role`` declaration.
    """
    if max_query_terms < 1:
        raise ValueError("max_query_terms must be >= 1")

    target_key = _key(target)
    ignored = {_key(term) for term in ignored_terms}
    candidates: list[str] = []
    seen: set[str] = set()
    for token in _WORD_RE.findall(message):
        key = _key(token)
        if len(key) < 2 or key == target_key or key in ignored or key in seen:
            continue
        seen.add(key)
        candidates.append(token)
        if len(candidates) >= max_query_terms:
            break

    predicate_terms: list[str] = []
    concept_terms: list[str] = []
    evidence_ids: list[str] = []
    role_cache: dict[str, tuple[str, tuple[str, ...]]] = {}

    for candidate in candidates:
        for variant in _term_variants(candidate):
            activated = activate_relations(
                resolver,
                concept=variant,
                session_id=session_id,
                depth=1,
                budget=_DEFAULT_BUDGET,
            )
            if activated.status != "HIT":
                continue
            variant_key = _key(variant)
            matched = False
            for line in activated.selected_context.splitlines():
                parsed = _parse_relation(line)
                if parsed is None:
                    continue
                subject, predicate, object_ = parsed
                subject_key = _key(subject)
                object_key = _key(object_)
                if subject_key == variant_key:
                    cue = object_
                elif object_key == variant_key:
                    cue = subject
                else:
                    continue

                role, role_evidence = _semantic_role_for_predicate(
                    resolver,
                    predicate=predicate,
                    session_id=session_id,
                    cache=role_cache,
                )
                if not role or not cue or _key(cue) == target_key:
                    continue

                destination = predicate_terms if role == "predicate" else concept_terms
                if cue not in destination:
                    destination.append(cue)
                for evidence_id in tuple(activated.memory_ids) + tuple(role_evidence):
                    if evidence_id and evidence_id not in evidence_ids:
                        evidence_ids.append(evidence_id)
                matched = True
            if matched:
                break

    return GraphSemanticCueResult(
        tuple(predicate_terms),
        tuple(concept_terms),
        tuple(evidence_ids),
    )


def resolve_graph_predicate_cues(
    resolver: object,
    *,
    message: str,
    session_id: str | None,
    target: str = "",
    ignored_terms: frozenset[str] = frozenset(),
    max_query_terms: int = _DEFAULT_MAX_QUERY_TERMS,
) -> GraphPredicateCueResult:
    """Backward-compatible predicate-only view of graph semantic cues."""
    result = resolve_graph_semantic_cues(
        resolver,
        message=message,
        session_id=session_id,
        target=target,
        ignored_terms=ignored_terms,
        max_query_terms=max_query_terms,
    )
    return GraphPredicateCueResult(result.predicate_terms, result.memory_ids)
