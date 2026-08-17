from __future__ import annotations
from dataclasses import dataclass
from statistics import mean

from .trajectory import Occurrence


@dataclass(frozen=True, slots=True)
class OrderedSimilarity:
    order_score: float
    temporal_score: float
    combined_score: float


def _lcs_length(a: list[str], b: list[str]) -> int:
    if not a or not b:
        return 0
    prev = [0] * (len(b) + 1)
    for x in a:
        cur = [0] * (len(b) + 1)
        for j, y in enumerate(b, start=1):
            cur[j] = prev[j - 1] + 1 if x == y else max(prev[j], cur[j - 1])
        prev = cur
    return prev[-1]


def _temporal_delta_score(a: list[Occurrence], b: list[Occurrence]) -> float:
    if len(a) < 2 or len(b) < 2:
        return 1.0 if a and b else 0.0
    da = [a[i + 1].local_time - a[i].local_time for i in range(len(a) - 1)]
    db = [b[i + 1].local_time - b[i].local_time for i in range(len(b) - 1)]
    n = min(len(da), len(db))
    if n == 0:
        return 0.0
    errors = []
    for x, y in zip(da[:n], db[:n]):
        scale = max(1, abs(x), abs(y))
        errors.append(abs(x - y) / scale)
    return max(0.0, 1.0 - mean(errors))


def compare_ordered(a: list[Occurrence], b: list[Occurrence], temporal_weight: float = 0.25) -> OrderedSimilarity:
    if not 0.0 <= temporal_weight <= 1.0:
        raise ValueError("temporal_weight must be between 0 and 1")
    seq_a = [o.node_id for o in sorted(a, key=lambda o: (o.layer, o.local_time))]
    seq_b = [o.node_id for o in sorted(b, key=lambda o: (o.layer, o.local_time))]
    if not seq_a or not seq_b:
        return OrderedSimilarity(0.0, 0.0, 0.0)
    lcs = _lcs_length(seq_a, seq_b)
    order_score = lcs / max(len(seq_a), len(seq_b))
    temporal_score = _temporal_delta_score(
        sorted(a, key=lambda o: (o.layer, o.local_time)),
        sorted(b, key=lambda o: (o.layer, o.local_time)),
    )
    combined = (1.0 - temporal_weight) * order_score + temporal_weight * temporal_score
    return OrderedSimilarity(order_score, temporal_score, combined)
