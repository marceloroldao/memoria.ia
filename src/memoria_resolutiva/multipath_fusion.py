from __future__ import annotations

from dataclasses import dataclass
from math import prod
from typing import Hashable, Iterable


@dataclass(frozen=True, slots=True)
class EvidencePath:
    conclusion: Hashable
    confidence: float
    provenance_roots: frozenset[Hashable]
    path_id: Hashable


@dataclass(frozen=True, slots=True)
class FusionResult:
    conclusion: Hashable
    fused_confidence: float
    independent_groups: int
    contributing_paths: tuple[Hashable, ...]


def _overlap(a: frozenset[Hashable], b: frozenset[Hashable]) -> bool:
    return bool(a & b)


def _group_by_dependency(paths: list[EvidencePath]) -> list[list[EvidencePath]]:
    """Group paths connected through shared provenance roots.

    Two paths belong to the same dependency family if they share at least one
    provenance root, directly or transitively. Each family contributes at most
    its strongest path to the final fusion.
    """
    groups: list[list[EvidencePath]] = []
    for path in paths:
        matched: list[int] = []
        for i, group in enumerate(groups):
            if any(_overlap(path.provenance_roots, member.provenance_roots) for member in group):
                matched.append(i)
        if not matched:
            groups.append([path])
            continue
        first = matched[0]
        groups[first].append(path)
        for i in reversed(matched[1:]):
            groups[first].extend(groups.pop(i))
    return groups


def fuse_paths(paths: Iterable[EvidencePath]) -> FusionResult | None:
    items = list(paths)
    if not items:
        return None
    conclusion = items[0].conclusion
    if any(p.conclusion != conclusion for p in items):
        raise ValueError("all paths must support the same conclusion")
    for p in items:
        if not 0.0 <= p.confidence <= 1.0:
            raise ValueError("confidence must be in [0,1]")

    groups = _group_by_dependency(items)
    representatives = [max(group, key=lambda p: p.confidence) for group in groups]

    # Independent support fusion via complement product:
    # P = 1 - Π(1-p_i). Dependency families contribute only once.
    fused = 1.0 - prod(1.0 - p.confidence for p in representatives)
    return FusionResult(
        conclusion=conclusion,
        fused_confidence=fused,
        independent_groups=len(groups),
        contributing_paths=tuple(p.path_id for p in representatives),
    )
