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


def evaluate_similarity_rows(rows: list[SimilarityRow], similarity, contains=None) -> dict[str, float]:
    """Evaluate human-rated word pairs.

    If `contains` is supplied it must return whether a word is in the model's
    learned vocabulary. This keeps zero semantic similarity distinct from
    out-of-vocabulary coverage failure. Spearman is computed only on covered
    pairs when explicit coverage is available.
    """
    human: list[float] = []
    model: list[float] = []
    covered = 0

    for row in rows:
        is_covered = True
        if contains is not None:
            is_covered = bool(contains(row.word1) and contains(row.word2))
        if not is_covered:
            continue
        score = similarity(row.word1, row.word2)
        human.append(row.human_score)
        model.append(score)
        covered += 1

    if contains is None:
        # Backward-compatible fallback when the model exposes no vocabulary API.
        human = []
        model = []
        covered = 0
        for row in rows:
            score = similarity(row.word1, row.word2)
            human.append(row.human_score)
            model.append(score)
            if score != 0.0:
                covered += 1

    return {
        "pairs": float(len(rows)),
        "covered_pairs": float(covered),
        "coverage": covered / len(rows) if rows else 0.0,
        "spearman": spearman(human, model),
    }
