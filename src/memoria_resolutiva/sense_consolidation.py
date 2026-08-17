from __future__ import annotations

from dataclasses import dataclass
from itertools import combinations

from .polysemy import PolysemyMemory, Sense, jaccard


@dataclass(frozen=True, slots=True)
class SenseGroup:
    group_id: int
    sense_ids: tuple[int, ...]
    signature: frozenset[str]
    occurrences: int


def _expanded_signature(sense: Sense, top_k: int = 20) -> set[str]:
    return {token for token, _ in sense.contexts.most_common(top_k)}


def _link_score(a: Sense, b: Sense) -> float:
    """Conservative evidence that two micro-senses belong to one macro-sense."""
    sa = _expanded_signature(a)
    sb = _expanded_signature(b)
    lexical = jaccard(sa, sb)
    # Shared context is intentionally rewarded, but no merge is destructive.
    shared = len(sa & sb)
    support = min(1.0, shared / 2.0)
    return 0.65 * lexical + 0.35 * support


def consolidate_senses(memory: PolysemyMemory, token: str, threshold: float = 0.24) -> list[SenseGroup]:
    """Build macro-sense groups while preserving all original micro-senses.

    Consolidation is a derived hierarchy, not an in-place merge. This keeps the
    episodic trajectories auditable and makes consolidation reversible.
    """
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
        if _link_score(a, b) >= threshold:
            union(a.sense_id, b.sense_id)

    buckets: dict[int, list[Sense]] = {}
    for sense in senses:
        buckets.setdefault(find(sense.sense_id), []).append(sense)

    groups: list[SenseGroup] = []
    for gid, members in enumerate(buckets.values()):
        signature: set[str] = set()
        occurrences = 0
        ids = []
        for sense in members:
            signature |= _expanded_signature(sense)
            occurrences += sense.occurrences
            ids.append(sense.sense_id)
        groups.append(SenseGroup(gid, tuple(sorted(ids)), frozenset(signature), occurrences))
    return groups


def resolve_group(groups: list[SenseGroup], context_words: set[str]) -> tuple[int | None, float]:
    if not groups:
        return None, 0.0
    scored = [(jaccard(set(g.signature), context_words), g.group_id) for g in groups]
    score, gid = max(scored)
    return gid, score
