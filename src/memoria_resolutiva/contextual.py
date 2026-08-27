from __future__ import annotations

from collections import Counter, defaultdict
from math import log, sqrt


class ContextAssociator:
    """Sparse contextual association over ordered node trajectories.

    Nodes are never declared equivalent. Similarity emerges from repeated exposure
    to similar signed neighborhoods around each node. No embeddings or neural
    network are used; profiles are sparse counters indexed by (relative_offset,
    neighboring_node).

    v0.13 maintains feature document frequencies incrementally during observation.
    Earlier versions rebuilt them during every similarity call, which becomes an
    avoidable bottleneck as vocabulary and feature counts grow.
    """

    def __init__(self, radius: int = 2):
        if radius < 1:
            raise ValueError("radius must be >= 1")
        self.radius = radius
        self.profiles: dict[str, Counter[tuple[int, str]]] = defaultdict(Counter)
        self.observations: Counter[str] = Counter()
        self.feature_df: Counter[tuple[int, str]] = Counter()

    def observe(self, trajectory: list[str] | tuple[str, ...]) -> None:
        for i, node_id in enumerate(trajectory):
            self.observations[node_id] += 1
            profile = self.profiles[node_id]
            lo = max(0, i - self.radius)
            hi = min(len(trajectory), i + self.radius + 1)
            for j in range(lo, hi):
                if j == i:
                    continue
                feature = (j - i, trajectory[j])
                if profile[feature] == 0:
                    self.feature_df[feature] += 1
                profile[feature] += 1

    def _feature_weight(self, feature: tuple[int, str]) -> float:
        total_nodes = max(1, len(self.profiles))
        return log((total_nodes + 1) / (self.feature_df[feature] + 1)) + 1.0

    def similarity(self, a: str, b: str) -> float:
        pa = self.profiles.get(a)
        pb = self.profiles.get(b)
        if not pa or not pb:
            return 0.0

        shared = set(pa) & set(pb)
        dot = sum(pa[f] * pb[f] * self._feature_weight(f) ** 2 for f in shared)
        norm_a = sqrt(sum((v * self._feature_weight(f)) ** 2 for f, v in pa.items()))
        norm_b = sqrt(sum((v * self._feature_weight(f)) ** 2 for f, v in pb.items()))
        if norm_a == 0.0 or norm_b == 0.0:
            return 0.0
        return dot / (norm_a * norm_b)

    def nearest(self, node_id: str, top_k: int = 5) -> list[tuple[str, float]]:
        if node_id not in self.profiles:
            return []
        scores = [
            (other, self.similarity(node_id, other))
            for other in self.profiles
            if other != node_id
        ]
        scores.sort(key=lambda item: (-item[1], item[0]))
        return scores[:top_k]

    def footprint(self) -> dict[str, int]:
        """Return sparse structural counts for streaming-growth measurements."""
        return {
            "nodes": len(self.profiles),
            "features": sum(len(profile) for profile in self.profiles.values()),
            "feature_df_entries": len(self.feature_df),
            "observations": sum(self.observations.values()),
        }
