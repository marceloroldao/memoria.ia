from __future__ import annotations

from dataclasses import dataclass

from .textual import TextContextMemory


@dataclass(frozen=True, slots=True)
class ConceptCluster:
    members: tuple[str, ...]
    purity: float


class EmergentOntology:
    """Build small latent concept groups from contextual similarity only.

    No synonym dictionary is required here. Terms are grouped when their
    contextual similarity exceeds the configured threshold. This is a simple
    mechanism test, not a full ontology learner.
    """

    def __init__(self, radius: int = 3, threshold: float = 0.55):
        self.memory = TextContextMemory(radius=radius)
        self.threshold = threshold

    def observe_many(self, sentences: list[str]) -> None:
        self.memory.observe_many(sentences)

    def _similarity(self, a: str, b: str) -> float:
        # Preserve the ordered/trajectory score but allow lexical ontology
        # grouping to recover equivalence under small grammatical shifts.
        return max(
            self.memory.similarity(a, b),
            self.memory.unordered_similarity(a, b),
        )

    def cluster(self, terms: list[str]) -> tuple[tuple[str, ...], ...]:
        unseen = set(t.lower() for t in terms)
        groups: list[tuple[str, ...]] = []
        while unseen:
            seed = min(unseen)
            unseen.remove(seed)
            group = {seed}
            changed = True
            while changed:
                changed = False
                for candidate in list(unseen):
                    if any(self._similarity(candidate, member) >= self.threshold for member in group):
                        group.add(candidate)
                        unseen.remove(candidate)
                        changed = True
            groups.append(tuple(sorted(group)))
        groups.sort(key=lambda g: (g[0], len(g)))
        return tuple(groups)


def cluster_purity(clusters: tuple[tuple[str, ...], ...], labels: dict[str, str]) -> float:
    total = sum(len(c) for c in clusters)
    if total == 0:
        return 1.0
    correct = 0
    for cluster in clusters:
        counts: dict[str, int] = {}
        for term in cluster:
            label = labels[term]
            counts[label] = counts.get(label, 0) + 1
        correct += max(counts.values())
    return correct / total
