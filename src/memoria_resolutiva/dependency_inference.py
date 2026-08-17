from __future__ import annotations

from dataclasses import dataclass
from math import exp
from re import findall


@dataclass(frozen=True, slots=True)
class SourceDocument:
    source: str
    text: str
    timestamp: float
    cites: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class DependencyEdge:
    source: str
    probable_origin: str
    score: float
    lexical_similarity: float
    temporal_proximity: float
    citation_signal: float


def _tokens(text: str) -> set[str]:
    return set(findall(r"\w+", text.lower()))


def lexical_jaccard(a: str, b: str) -> float:
    ta, tb = _tokens(a), _tokens(b)
    if not ta and not tb:
        return 1.0
    if not ta or not tb:
        return 0.0
    return len(ta & tb) / len(ta | tb)


def infer_dependency(
    docs: list[SourceDocument],
    *,
    lexical_weight: float = 0.55,
    temporal_weight: float = 0.25,
    citation_weight: float = 0.20,
    time_scale: float = 6.0,
    threshold: float = 0.65,
) -> tuple[DependencyEdge, ...]:
    """Infer likely copy/dependency links from earlier to later sources.

    The score combines lexical overlap, temporal proximity, and explicit citation.
    Only earlier documents can be probable origins of later documents.
    """
    ordered = sorted(docs, key=lambda d: d.timestamp)
    edges: list[DependencyEdge] = []

    for i, current in enumerate(ordered):
        best: DependencyEdge | None = None
        for prior in ordered[:i]:
            lexical = lexical_jaccard(current.text, prior.text)
            delta_t = max(0.0, current.timestamp - prior.timestamp)
            temporal = exp(-delta_t / max(time_scale, 1e-9))
            citation = 1.0 if prior.source in current.cites else 0.0
            score = lexical_weight * lexical + temporal_weight * temporal + citation_weight * citation
            candidate = DependencyEdge(
                source=current.source,
                probable_origin=prior.source,
                score=score,
                lexical_similarity=lexical,
                temporal_proximity=temporal,
                citation_signal=citation,
            )
            if best is None or candidate.score > best.score:
                best = candidate
        if best is not None and best.score >= threshold:
            edges.append(best)

    return tuple(edges)


def origin_groups(docs: list[SourceDocument], edges: tuple[DependencyEdge, ...]) -> dict[str, str]:
    """Collapse inferred dependency chains to their earliest reachable origin."""
    parent = {edge.source: edge.probable_origin for edge in edges}

    def root(source: str) -> str:
        seen: set[str] = set()
        cur = source
        while cur in parent and cur not in seen:
            seen.add(cur)
            cur = parent[cur]
        return cur

    return {doc.source: root(doc.source) for doc in docs}
