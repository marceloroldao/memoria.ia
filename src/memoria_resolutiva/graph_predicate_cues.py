from __future__ import annotations

from dataclasses import dataclass
import re
import unicodedata

from .relational_activation import activate as activate_relations

_WORD_RE = re.compile(r"[\wÀ-ÿ.-]+", re.UNICODE)
_CUE_PREDICATES = frozenset({"unidade_de", "unit_of"})
_DEFAULT_MAX_QUERY_TERMS = 4
_DEFAULT_BUDGET = 320


@dataclass(frozen=True, slots=True)
class GraphPredicateCueResult:
    terms: tuple[str, ...]
    memory_ids: tuple[str, ...]


def _key(value: str) -> str:
    value = unicodedata.normalize("NFKD", value)
    value = "".join(ch for ch in value if not unicodedata.combining(ch))
    return " ".join(value.casefold().strip().split())


def _term_variants(value: str) -> tuple[str, ...]:
    """Return conservative lexical variants without knowing any unit vocabulary."""
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


def resolve_graph_predicate_cues(
    resolver: object,
    *,
    message: str,
    session_id: str | None,
    target: str = "",
    ignored_terms: frozenset[str] = frozenset(),
    max_query_terms: int = _DEFAULT_MAX_QUERY_TERMS,
) -> GraphPredicateCueResult:
    """Resolve implicit query predicates from explicit graph relations.

    Example persisted knowledge::

        volt | unidade_de | tensão

    allows a query containing ``volts`` to contribute ``tensão`` as a ranking
    cue. The function has no built-in knowledge of volts, amperes, Celsius, or
    any other unit. It only trusts persisted ``unidade_de``/``unit_of`` edges.

    Traversal goes through ``activate_relations`` so the same contract works for
    the Python EvidenceCore fallback and the optional native runtime.
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

    discovered: list[str] = []
    evidence_ids: list[str] = []
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
                if _key(predicate) not in _CUE_PREDICATES:
                    continue
                subject_key = _key(subject)
                object_key = _key(object_)
                if subject_key == variant_key:
                    cue = object_
                elif object_key == variant_key:
                    cue = subject
                else:
                    continue
                if cue and _key(cue) != target_key and cue not in discovered:
                    discovered.append(cue)
                matched = True
            if matched:
                for evidence_id in activated.memory_ids:
                    if evidence_id and evidence_id not in evidence_ids:
                        evidence_ids.append(evidence_id)
                break

    return GraphPredicateCueResult(tuple(discovered), tuple(evidence_ids))
