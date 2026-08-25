from __future__ import annotations

from dataclasses import dataclass
import heapq
from time import perf_counter
from typing import Iterable

from .autonomous_memory_v098 import (
    AutonomousHitV098,
    AutonomousQueryResultV098,
    AutonomousTextMemoryV098,
    CoreMetricsV098,
    _conflicts,
    _terms,
)


@dataclass(frozen=True, slots=True)
class AdaptiveCandidateStatsV099:
    raw_candidates: int
    exact_scored: int
    attempted_limits: tuple[int, ...]
    final_limit: int
    expanded: bool
    retained_fraction: float
    max_unseen_upper_bound: float = 0.0
    certified: bool = False


class AutonomousTextMemoryV099(AutonomousTextMemoryV098):
    """Adaptive exact-scoring with a conservative v0.98 score certificate.

    Candidate discovery and the final score are still the deterministic v0.98
    mechanisms. v0.99 avoids exact-scoring every candidate only when a cheap
    mathematical upper bound proves that no unscored candidate can change the
    selected top-k set or the top-two decision used for ambiguity/conflict.

    The bound follows directly from the v0.98 score:
      score = .70 * (.50*qcoverage + .30*overlap + .20*jaccard)
              + .30*weighted_query_coverage
    with overlap <= 1 and jaccard <= qcoverage. Therefore:
      score <= .49*qcoverage + .21 + .30*weighted_query_coverage.

    This turns pruning from a heuristic early exit into a conservative certificate.
    It does not make semantic discovery O(1): candidate generation and upper-bound
    construction still depend on the query postings. Exact resolved-address lookup
    remains the separate O(1)-style path.
    """

    def __init__(
        self,
        *,
        threshold: float = 0.42,
        ambiguity_margin: float = 0.04,
        candidate_ladder: Iterable[int] = (8, 16, 32, 64, 128),
    ) -> None:
        super().__init__(threshold=threshold, ambiguity_margin=ambiguity_margin)
        ladder = tuple(sorted(set(int(x) for x in candidate_ladder)))
        if not ladder or ladder[0] < 2:
            raise ValueError('candidate_ladder must contain values >= 2')
        self.candidate_ladder = ladder
        self._last_adaptive_stats = AdaptiveCandidateStatsV099(0, 0, (), ladder[0], False, 0.0)

    def adaptive_stats(self) -> AdaptiveCandidateStatsV099:
        return self._last_adaptive_stats

    def _upper_bound(self, query: tuple[str, ...], record: tuple[str, ...]) -> float:
        q = set(query)
        if not q:
            return 0.0
        shared = q & set(record)
        if not shared:
            return 0.0
        qcoverage = len(shared) / len(q)
        query_weight = sum(self._idf(term) for term in q)
        shared_weight = sum(self._idf(term) for term in shared)
        weighted = shared_weight / query_weight if query_weight else 0.0
        return min(1.0, 0.49 * qcoverage + 0.21 + 0.30 * weighted)

    def _bound_heap(self, terms: tuple[str, ...], candidate_ids: set[str]) -> list[tuple[float, str]]:
        heap = [(-self._upper_bound(terms, self._records[mid].terms), mid) for mid in candidate_ids]
        heapq.heapify(heap)
        return heap

    def _score_ids(self, terms: tuple[str, ...], ids: list[str]) -> list[tuple[object, float]]:
        ranked = [(self._records[mid], self._score(terms, self._records[mid].terms)) for mid in ids]
        ranked.sort(key=lambda item: (-item[1], -item[0].sequence, item[0].memory_id))
        return ranked

    def _safe_to_stop(
        self,
        eligible: list[tuple[object, float]],
        *,
        top_k: int,
        unseen_bound: float,
    ) -> bool:
        if not eligible:
            return unseen_bound < self.threshold

        # The top-two identities must be fixed before classifying ambiguity or
        # conflict. If there is only one eligible result, every unseen candidate
        # must be proven unable to cross the acceptance threshold.
        if len(eligible) == 1:
            decision_safe = unseen_bound < self.threshold
        else:
            decision_safe = unseen_bound <= eligible[1][1]

        # The complete returned top-k set must also be fixed. When fewer than k
        # accepted records have been scored, an unseen record above threshold
        # would change the response context.
        if len(eligible) < top_k:
            selection_safe = unseen_bound < self.threshold
        else:
            selection_safe = unseen_bound <= eligible[top_k - 1][1]
        return decision_safe and selection_safe

    def query(self, text: str, *, top_k: int = 3) -> AutonomousQueryResultV098:
        started = perf_counter()
        clean = ' '.join(text.strip().split())
        terms = _terms(clean)
        if not clean or not terms:
            raise ValueError('query must contain meaningful text')
        if top_k < 1:
            raise ValueError('top_k must be >= 1')

        candidate_ids = self._candidate_ids(terms)
        raw_count = len(candidate_ids)
        heap = self._bound_heap(terms, candidate_ids)
        attempted: list[int] = []
        scored_ids: list[str] = []
        ranked_all: list[tuple[object, float]] = []
        exact_scored = 0
        certified = False

        if heap:
            for limit in self.candidate_ladder:
                target = min(limit, raw_count)
                attempted.append(target)
                while heap and len(scored_ids) < target:
                    _negative_bound, mid = heapq.heappop(heap)
                    scored_ids.append(mid)
                exact_scored = len(scored_ids)
                ranked_all = self._score_ids(terms, scored_ids)
                eligible = [(record, score) for record, score in ranked_all if score >= self.threshold]
                unseen_bound = -heap[0][0] if heap else 0.0
                if self._safe_to_stop(eligible, top_k=top_k, unseen_bound=unseen_bound):
                    certified = True
                    break
                if not heap:
                    certified = True
                    break

            # The normal ladder is a performance preference, not a correctness
            # limit. Continue in bounded chunks until the certificate holds.
            chunk = self.candidate_ladder[-1]
            while heap and not certified:
                target = min(raw_count, len(scored_ids) + chunk)
                attempted.append(target)
                while heap and len(scored_ids) < target:
                    _negative_bound, mid = heapq.heappop(heap)
                    scored_ids.append(mid)
                exact_scored = len(scored_ids)
                ranked_all = self._score_ids(terms, scored_ids)
                eligible = [(record, score) for record, score in ranked_all if score >= self.threshold]
                unseen_bound = -heap[0][0] if heap else 0.0
                certified = self._safe_to_stop(eligible, top_k=top_k, unseen_bound=unseen_bound) or not heap
        else:
            unseen_bound = 0.0
            certified = True

        ranked = [(record, score) for record, score in ranked_all if score >= self.threshold]
        best = ranked[0][1] if ranked else 0.0
        runner = ranked[1][1] if len(ranked) > 1 else 0.0
        margin = best - runner
        ambiguous = len(ranked) > 1 and margin < self.ambiguity_margin
        conflict_pair = len(ranked) > 1 and _conflicts(ranked[0][0].terms, ranked[1][0].terms)

        if not ranked or (ambiguous and not conflict_pair):
            decision = 'unresolved'
            selected = []
            abstained = True
        else:
            decision = 'conflict' if conflict_pair else ('same' if best >= 0.96 else 'related')
            selected = ranked[:top_k]
            abstained = False

        hits = tuple(
            AutonomousHitV098(
                record.memory_id,
                record.text,
                score,
                'conflict' if conflict_pair else ('same' if score >= 0.96 else 'related'),
                record.sequence,
            )
            for record, score in selected
        )
        latency = (perf_counter() - started) * 1000.0
        retained = (exact_scored / raw_count) if raw_count else 0.0
        final_limit = attempted[-1] if attempted else self.candidate_ladder[0]
        final_unseen_bound = -heap[0][0] if heap else 0.0
        self._last_adaptive_stats = AdaptiveCandidateStatsV099(
            raw_candidates=raw_count,
            exact_scored=exact_scored,
            attempted_limits=tuple(attempted),
            final_limit=final_limit,
            expanded=len(attempted) > 1,
            retained_fraction=retained,
            max_unseen_upper_bound=final_unseen_bound,
            certified=certified,
        )
        metrics = CoreMetricsV098(
            len(self), raw_count, exact_scored, len(hits), best, runner, margin,
            decision, False, latency, 0.0, 0, 0, 0, int(abstained),
        )
        return AutonomousQueryResultV098(clean, hits, abstained, exact_scored, metrics)
