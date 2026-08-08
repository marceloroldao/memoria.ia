from __future__ import annotations

from dataclasses import dataclass
from typing import Hashable, Iterable


@dataclass(frozen=True, slots=True)
class Argument:
    conclusion: Hashable
    polarity: bool
    confidence: float
    provenance: frozenset[Hashable]


@dataclass(frozen=True, slots=True)
class ConflictDecision:
    status: str  # support | reject | abstain | no_evidence
    support_confidence: float
    reject_confidence: float
    margin: float
    support_sources: frozenset[Hashable]
    reject_sources: frozenset[Hashable]


def _dependent(a: Argument, b: Argument) -> bool:
    return bool(a.provenance & b.provenance)


def _independent_representatives(arguments: list[Argument]) -> list[Argument]:
    """Collapse transitively dependent arguments to one strongest representative."""
    n = len(arguments)
    parent = list(range(n))

    def find(x: int) -> int:
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    def union(a: int, b: int) -> None:
        ra, rb = find(a), find(b)
        if ra != rb:
            parent[rb] = ra

    for i in range(n):
        for j in range(i + 1, n):
            if _dependent(arguments[i], arguments[j]):
                union(i, j)

    groups: dict[int, list[Argument]] = {}
    for i, arg in enumerate(arguments):
        groups.setdefault(find(i), []).append(arg)
    return [max(group, key=lambda x: x.confidence) for group in groups.values()]


def _fuse(arguments: list[Argument]) -> tuple[float, frozenset[Hashable]]:
    reps = _independent_representatives(arguments)
    if not reps:
        return 0.0, frozenset()
    residual = 1.0
    sources: set[Hashable] = set()
    for arg in reps:
        residual *= 1.0 - max(0.0, min(1.0, arg.confidence))
        sources.update(arg.provenance)
    return 1.0 - residual, frozenset(sources)


def decide_conflict(arguments: Iterable[Argument], conclusion: Hashable, decision_margin: float = 0.15, min_strength: float = 0.50) -> ConflictDecision:
    relevant = [a for a in arguments if a.conclusion == conclusion]
    positive = [a for a in relevant if a.polarity]
    negative = [a for a in relevant if not a.polarity]
    support, support_sources = _fuse(positive)
    reject, reject_sources = _fuse(negative)
    if not relevant:
        return ConflictDecision("no_evidence", 0.0, 0.0, 0.0, frozenset(), frozenset())
    margin = abs(support - reject)
    if max(support, reject) < min_strength or margin < decision_margin:
        status = "abstain"
    elif support > reject:
        status = "support"
    else:
        status = "reject"
    return ConflictDecision(status, support, reject, margin, support_sources, reject_sources)
