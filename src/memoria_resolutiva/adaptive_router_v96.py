from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

from .discriminative_router_v96 import DiscriminativeSemanticRouterV96
from .semantic_router_v96 import SemanticResolution


@dataclass(frozen=True, slots=True)
class AdaptiveCandidateStats:
    attempted_limits: tuple[int, ...]
    final_limit: int
    final_candidate_count: int
    expanded: bool


class AdaptiveDiscriminativeSemanticRouterV96(DiscriminativeSemanticRouterV96):
    """Conservative progressive candidate expansion for v0.96 experiments.

    Candidate selection remains discriminative, but exact scoring is attempted
    progressively over an increasing candidate ladder. A stage is accepted only
    when the inherited semantic score and margin criteria are satisfied. If a
    stage abstains, the router expands the candidate set and tries again.

    This does not guarantee that a valid concept omitted by a small candidate set
    cannot be missed; therefore the class remains experimental and is evaluated
    against full-scan parity before any default promotion.
    """

    def __init__(
        self,
        *,
        radius: int = 3,
        threshold: float = 0.60,
        min_margin: float = 0.08,
        candidate_ladder: Iterable[int] = (8, 16, 32, 64),
    ) -> None:
        ladder = tuple(sorted(set(int(x) for x in candidate_ladder)))
        if not ladder or ladder[0] < 2:
            raise ValueError("candidate_ladder must contain values >= 2")
        super().__init__(
            radius=radius,
            threshold=threshold,
            min_margin=min_margin,
            candidate_limit=ladder[-1],
        )
        self.candidate_ladder = ladder
        self._last_adaptive_stats = AdaptiveCandidateStats((), ladder[0], 0, False)

    def _resolve_with_ids(self, q: str, candidate_ids: list[str]) -> SemanticResolution:
        if not candidate_ids:
            return SemanticResolution(q, None, 0.0, 0.0, "unresolved")

        ranked: list[tuple[str, float]] = []
        for concept_id in candidate_ids:
            anchors = self._concepts[concept_id]
            best = max((self._score(q, anchor) for anchor in anchors), default=0.0)
            ranked.append((concept_id, best))
        ranked.sort(key=lambda item: (-item[1], item[0]))

        best_id, best_score = ranked[0]
        second_score = ranked[1][1] if len(ranked) > 1 else 0.0
        margin = best_score - second_score
        if best_score >= self.threshold and margin >= self.min_margin:
            return SemanticResolution(q, best_id, best_score, margin, "memory")
        return SemanticResolution(q, None, best_score, margin, "unresolved")

    def resolve_token(self, query: str) -> SemanticResolution:
        q = query.strip().lower()
        if not q:
            raise ValueError("query must not be empty")

        # Build the largest ranked list once; smaller stages are stable prefixes.
        original_limit = self.candidate_limit
        self.candidate_limit = self.candidate_ladder[-1]
        try:
            ranked_ids = self._discriminative_candidates(q)
        finally:
            self.candidate_limit = original_limit

        if not ranked_ids:
            self._last_adaptive_stats = AdaptiveCandidateStats(
                (self.candidate_ladder[0],), self.candidate_ladder[0], 0, False
            )
            return SemanticResolution(q, None, 0.0, 0.0, "unresolved")

        attempted: list[int] = []
        last = SemanticResolution(q, None, 0.0, 0.0, "unresolved")
        for limit in self.candidate_ladder:
            attempted.append(limit)
            ids = ranked_ids[:limit]
            last = self._resolve_with_ids(q, ids)
            if last.concept_id is not None:
                self._last_candidate_count = len(ids)
                self._last_adaptive_stats = AdaptiveCandidateStats(
                    tuple(attempted), limit, len(ids), len(attempted) > 1
                )
                return last

        self._last_candidate_count = len(ranked_ids)
        self._last_adaptive_stats = AdaptiveCandidateStats(
            tuple(attempted), self.candidate_ladder[-1], len(ranked_ids), len(attempted) > 1
        )
        return last

    def adaptive_stats(self) -> AdaptiveCandidateStats:
        return self._last_adaptive_stats
