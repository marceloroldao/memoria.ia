from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class SimilarityRow:
    word1: str
    word2: str
    human_score: float


def _rank(values: list[float]) -> list[float]:
    order = sorted(range(len(values)), key=values.__getitem__)
    ranks = [0.0] * len(values)
    i = 0
    while i < len(order):
        j = i + 1
        while j < len(order) and values[order[j]] == values[order[i]]:
            j += 1
        avg = (i + j - 1) / 2.0 + 1.0
        for k in range(i, j):
            ranks[order[k]] = avg
        i = j
    return ranks


def spearman(x: list[float], y: list[float]) -> float:
    if len(x) != len(y) or len(x) < 2:
        return 0.0
    rx, ry = _rank(x), _rank(y)
    mx = sum(rx) / len(rx)
    my = sum(ry) / len(ry)
    num = sum((a - mx) * (b - my) for a, b in zip(rx, ry))
    dx = sum((a - mx) ** 2 for a in rx) ** 0.5
    dy = sum((b - my) ** 2 for b in ry) ** 0.5
    return num / (dx * dy) if dx and dy else 0.0


def evaluate_similarity_rows(rows: list[SimilarityRow], similarity) -> dict[str, float]:
    human, model = [], []
    covered = 0
    for row in rows:
        score = similarity(row.word1, row.word2)
        human.append(row.human_score)
        model.append(score)
        if score != 0.0:
            covered += 1
    return {
        "pairs": float(len(rows)),
        "coverage": covered / len(rows) if rows else 0.0,
        "spearman": spearman(human, model),
    }
