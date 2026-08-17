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


def _normalized(doc: SourceDocument) -> SourceDocument:
    """Accept the historical v0.26 positional order as well as the v0.25 order.

    Current order is ``(source, text, timestamp, cites)``. Some retained
    experiments used ``(source, timestamp, text, cites)``. Keeping this adapter
    preserves reproducibility of both experiment generations without changing
    the public current constructor contract.
    """
    if isinstance(doc.text, (int, float)) and isinstance(doc.timestamp, str):
        return SourceDocument(doc.source, doc.timestamp, float(doc.text), doc.cites)
    return doc


def _tokens(text: str) -> set[str]:
    return set(findall(r"\w+", str(text).lower()))


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
    normalized = [_normalized(d) for d in docs]
    ordered = sorted(normalized, key=lambda d: d.timestamp)
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


def infer_dependency_graph(
    docs: list[SourceDocument],
    *,
    threshold: float = 0.65,
    **kwargs,
) -> dict[str, str | None]:
    """Compatibility graph view retained for v0.26 experiments."""
    edges = infer_dependency(docs, threshold=threshold, **kwargs)
    parent = {edge.source: edge.probable_origin for edge in edges}
    return {doc.source: parent.get(doc.source) for doc in docs}


def roots_by_source(graph: dict[str, str | None]) -> dict[str, str]:
    """Resolve every source in a dependency graph to its earliest root."""
    def root(source: str) -> str:
        seen: set[str] = set()
        cur = source
        while graph.get(cur) is not None and cur not in seen:
            seen.add(cur)
            cur = graph[cur]  # type: ignore[index]
        return cur

    return {source: root(source) for source in graph}
