from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

from .autonomous_memory_v098 import AutonomousTextMemoryV098, _terms
from .autonomous_memory_v099 import AdaptiveCandidateStatsV099, AutonomousTextMemoryV099


@dataclass(frozen=True, slots=True)
class PostingPrefilterStatsV100:
    query_terms: int
    required_any_terms: tuple[str, ...]
    posting_pool_count: int
    complement_upper_bound: float
    certified: bool
    used: bool
    scoring_mode: str = 'adaptive'


class AutonomousTextMemoryV100(AutonomousTextMemoryV099):
    """Certified postings prefilter plus adaptive/one-shot scoring selection.

    v0.99 proves when exact scoring can stop, but it still builds a bound for each
    candidate in the union of all query postings. v1.00 first proves that every
    record capable of reaching the v0.98 acceptance threshold must contain at
    least one term from a selected discriminative set R. It can then safely form
    the candidate pool from union(posting(term) for term in R), without visiting
    postings for the remaining generic terms.

    For selective pools, the certified v0.99 progressive scorer is retained. For
    large/generic pools, v1.00 intentionally falls back to one v0.98-style exact
    ranking pass over the already-certified posting pool. This avoids repeated
    expansion/sorting in the v0.99 worst case while preserving exactly the same
    score, threshold, ambiguity and conflict rules.

    Semantic discovery is still not O(1); this is a postings-level reduction.
    """

    def __init__(
        self,
        *,
        threshold: float = 0.42,
        ambiguity_margin: float = 0.04,
        candidate_ladder: Iterable[int] = (8, 16, 32, 64, 128),
        one_shot_threshold: int = 2048,
    ) -> None:
        super().__init__(
            threshold=threshold,
            ambiguity_margin=ambiguity_margin,
            candidate_ladder=candidate_ladder,
        )
        if one_shot_threshold < 2:
            raise ValueError('one_shot_threshold must be >= 2')
        self.one_shot_threshold = int(one_shot_threshold)
        self._query_prefilter_active = False
        self._query_prefilter_pool: set[str] | None = None
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
            pool: set[str] = set()
            for term in unique:
                pool.update(self._inverted.get(term, ()))
            self._prefilter_stats = PostingPrefilterStatsV100(
                len(unique), tuple(sorted(unique)), len(pool), bound, False, False, 'one_shot'
            )
            return pool

        pool: set[str] = set()
        for term in required_any:
            pool.update(self._inverted.get(term, ()))
        used = required_any != unique
        mode = 'one_shot' if len(pool) > self.one_shot_threshold else 'adaptive'
        self._prefilter_stats = PostingPrefilterStatsV100(
            query_terms=len(unique),
            required_any_terms=tuple(sorted(required_any)),
            posting_pool_count=len(pool),
            complement_upper_bound=bound,
            certified=True,
            used=used,
            scoring_mode=mode,
        )
        return pool

    def _candidate_ids(self, terms: tuple[str, ...]) -> set[str]:
        if self._query_prefilter_active:
            if self._query_prefilter_pool is not None:
                return set(self._query_prefilter_pool)
            return self._certified_posting_pool(terms)
        return super()._candidate_ids(terms)

    def query(self, text: str, *, top_k: int = 3):
        clean = ' '.join(text.strip().split())
        terms = _terms(clean)
        if not clean or not terms:
            raise ValueError('query must contain meaningful text')
        if top_k < 1:
            raise ValueError('top_k must be >= 1')

        pool = self._certified_posting_pool(terms)
        self._query_prefilter_pool = pool
        self._query_prefilter_active = True
        try:
            if len(pool) > self.one_shot_threshold:
                # One exact ranking pass is faster and simpler than repeated
                # progressive expansions for a broad/generic certified pool.
                result = AutonomousTextMemoryV098.query(self, clean, top_k=top_k)
                self._last_adaptive_stats = AdaptiveCandidateStatsV099(
                    raw_candidates=len(pool),
                    exact_scored=len(pool),
                    attempted_limits=(len(pool),) if pool else (),
                    final_limit=len(pool),
                    expanded=False,
                    retained_fraction=1.0 if pool else 0.0,
                    max_unseen_upper_bound=0.0,
                    certified=True,
                )
                self._prefilter_stats = PostingPrefilterStatsV100(
                    query_terms=self._prefilter_stats.query_terms,
                    required_any_terms=self._prefilter_stats.required_any_terms,
                    posting_pool_count=self._prefilter_stats.posting_pool_count,
                    complement_upper_bound=self._prefilter_stats.complement_upper_bound,
                    certified=self._prefilter_stats.certified,
                    used=self._prefilter_stats.used,
                    scoring_mode='one_shot',
                )
                return result
            result = AutonomousTextMemoryV099.query(self, clean, top_k=top_k)
            self._prefilter_stats = PostingPrefilterStatsV100(
                query_terms=self._prefilter_stats.query_terms,
                required_any_terms=self._prefilter_stats.required_any_terms,
                posting_pool_count=self._prefilter_stats.posting_pool_count,
                complement_upper_bound=self._prefilter_stats.complement_upper_bound,
                certified=self._prefilter_stats.certified,
                used=self._prefilter_stats.used,
                scoring_mode='adaptive',
            )
            return result
        finally:
            self._query_prefilter_active = False
            self._query_prefilter_pool = None
