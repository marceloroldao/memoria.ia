from __future__ import annotations

from dataclasses import dataclass
from itertools import combinations
from math import log1p

from .polysemy import PolysemyMemory, Sense, jaccard


@dataclass(frozen=True, slots=True)
class TemporalSenseGroup:
    group_id: int
    sense_ids: tuple[int, ...]
    signature: frozenset[str]
    occurrences: int
    support_weight: float


def _signature(sense: Sense, top_k: int = 20) -> set[str]:
    return {token for token, _ in sense.contexts.most_common(top_k)}


def _support_weight(sense: Sense, saturation: float = 1.25) -> float:
    # Bounded recurrence support. A single accidental micro-sense contributes
    # less than one repeatedly observed, while saturation prevents dominance.
    if saturation <= 0:
        raise ValueError("saturation must be positive")
    raw = log1p(max(0, sense.occurrences))
    return min(saturation, raw) / saturation


def temporal_link_score(a: Sense, b: Sense, saturation: float = 1.25) -> float:
    sa, sb = _signature(a), _signature(b)
    lexical = jaccard(sa, sb)
    shared = len(sa & sb)
    context_support = min(1.0, shared / 2.0)
    recurrence = min(_support_weight(a, saturation), _support_weight(b, saturation))
    # Similarity remains primary; recurrence only validates that the relation
    # has been observed often enough to deserve consolidation.
    return recurrence * (0.65 * lexical + 0.35 * context_support)


def consolidate_temporal_senses(
    memory: PolysemyMemory,
    token: str,
    threshold: float = 0.24,
    saturation: float = 1.25,
) -> list[TemporalSenseGroup]:
    senses = memory.senses(token)
    if not senses:
        return []

    parent = {s.sense_id: s.sense_id for s in senses}

    def find(x: int) -> int:
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    def union(a: int, b: int) -> None:
        ra, rb = find(a), find(b)
        if ra != rb:
            parent[rb] = ra

    for a, b in combinations(senses, 2):
        if temporal_link_score(a, b, saturation) >= threshold:
            union(a.sense_id, b.sense_id)

    buckets: dict[int, list[Sense]] = {}
    for sense in senses:
        buckets.setdefault(find(sense.sense_id), []).append(sense)

    groups: list[TemporalSenseGroup] = []
    for gid, members in enumerate(buckets.values()):
        signature: set[str] = set()
        occurrences = 0
        ids = []
        support = 0.0
        for sense in members:
            signature |= _signature(sense)
            occurrences += sense.occurrences
            ids.append(sense.sense_id)
            support += _support_weight(sense, saturation)
        groups.append(TemporalSenseGroup(
            group_id=gid,
            sense_ids=tuple(sorted(ids)),
            signature=frozenset(signature),
            occurrences=occurrences,
            support_weight=support,
        ))
    return groups
