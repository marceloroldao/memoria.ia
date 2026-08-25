from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

from .autonomous_memory_v099 import AutonomousTextMemoryV099


@dataclass(frozen=True, slots=True)
class PostingPrefilterStatsV100:
    query_terms: int
    required_any_terms: tuple[str, ...]
    posting_pool_count: int
    complement_upper_bound: float
    certified: bool
    used: bool


class AutonomousTextMemoryV100(AutonomousTextMemoryV099):
    """Experimental certified postings prefilter before v0.99 scoring.

    v0.99 proves when exact scoring can stop, but it still builds a bound for each
    candidate in the union of all query postings. v1.00 first proves that every
    record capable of reaching the v0.98 acceptance threshold must contain at
    least one term from a selected discriminative set R. It can then safely form
    the candidate pool from union(posting(term) for term in R), without visiting
    postings for the remaining generic terms.

    Certificate: assume a record contains every query term outside R and none in
    R. This is the best possible record excluded by union(postings(R)). Applying
    the same safe v0.98 score upper bound used by v0.99, if that complement bound
    is below threshold, no excluded record can be eligible. The v0.99 certificate
    then handles ranking/top-k inside the retained pool.

    Semantic discovery is still not O(1); this is a postings-level reduction.
    """

    def __init__(
        self,
        *,
        threshold: float = 0.42,
        ambiguity_margin: float = 0.04,
        candidate_ladder: Iterable[int] = (8, 16, 32, 64, 128),
    ) -> None:
        super().__init__(
            threshold=threshold,
            ambiguity_margin=ambiguity_margin,
            candidate_ladder=candidate_ladder,
        )
        self._query_prefilter_active = False
        self._prefilter_stats = PostingPrefilterStatsV100(0, (), 0, 0.0, True, False)

    def prefilter_stats(self) -> PostingPrefilterStatsV100:
        return self._prefilter_stats

    def _complement_bound(self, terms: tuple[str, ...], excluded: set[str]) -> float:
        q = set(terms)
        if not q:
            return 0.0
        remaining = q - excluded
        if not remaining:
            return 0.0
        total_weight = sum(self._idf(term) for term in q)
        remaining_weight = sum(self._idf(term) for term in remaining)
        qcoverage = len(remaining) / len(q)
        weighted = remaining_weight / total_weight if total_weight else 0.0
        return min(1.0, 0.49 * qcoverage + 0.21 + 0.30 * weighted)

    def _certified_posting_pool(self, terms: tuple[str, ...]) -> set[str]:
        unique = set(terms)
        if not unique:
            self._prefilter_stats = PostingPrefilterStatsV100(0, (), 0, 0.0, True, False)
            return set()

        # Prefer terms that remove much possible score mass while touching few
        # records. Deterministic tie-breaking keeps repeated runs identical.
        weighted_terms = []
        total_weight = sum(self._idf(term) for term in unique)
        for term in unique:
            df = len(self._inverted.get(term, ()))
            impact = (0.49 / len(unique)) + (0.30 * self._idf(term) / total_weight if total_weight else 0.0)
            efficiency = impact / max(1, df)
            weighted_terms.append((term, efficiency, impact, df))
        weighted_terms.sort(key=lambda item: (-item[1], -item[2], item[3], item[0]))

        required_any: set[str] = set()
        bound = self._complement_bound(terms, required_any)
        for term, _efficiency, _impact, _df in weighted_terms:
            if bound < self.threshold:
                break
            required_any.add(term)
            bound = self._complement_bound(terms, required_any)

        if bound >= self.threshold:
            # Defensive fallback. With all terms excluded the true maximum is 0,
            # so this branch should not normally be reachable.
            pool: set[str] = set()
            for term in unique:
                pool.update(self._inverted.get(term, ()))
            self._prefilter_stats = PostingPrefilterStatsV100(
                len(unique), tuple(sorted(unique)), len(pool), bound, False, False
            )
            return pool

        pool: set[str] = set()
        for term in required_any:
            pool.update(self._inverted.get(term, ()))
        used = required_any != unique
        self._prefilter_stats = PostingPrefilterStatsV100(
            query_terms=len(unique),
            required_any_terms=tuple(sorted(required_any)),
            posting_pool_count=len(pool),
            complement_upper_bound=bound,
            certified=True,
            used=used,
        )
        return pool

    def _candidate_ids(self, terms: tuple[str, ...]) -> set[str]:
        if self._query_prefilter_active:
            return self._certified_posting_pool(terms)
        return super()._candidate_ids(terms)

    def query(self, text: str, *, top_k: int = 3):
        self._query_prefilter_active = True
        try:
            return super().query(text, top_k=top_k)
        finally:
            self._query_prefilter_active = False
