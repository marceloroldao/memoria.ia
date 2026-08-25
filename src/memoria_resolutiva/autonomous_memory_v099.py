from __future__ import annotations

from dataclasses import dataclass
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


class AutonomousTextMemoryV099(AutonomousTextMemoryV098):
    """Experimental v0.99 adaptive candidate reduction.

    v0.98 remains the correctness baseline. v0.99 reuses its inverse-frequency
    candidate priority, but exact relation scoring is performed progressively over
    a candidate ladder. A stage is accepted only when the v0.98 threshold and
    ambiguity-margin rules are already satisfied. Otherwise the candidate set is
    expanded deterministically.

    This is intentionally experimental: candidate-pruning recall must be measured
    against v0.98 full-candidate scoring before promotion.
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

    def _priority_order(self, terms: tuple[str, ...], candidate_ids: set[str]) -> list[str]:
        return sorted(
            candidate_ids,
            key=lambda mid: (-self._candidate_priority(terms, self._records[mid].terms), mid),
        )

    def _score_ids(self, terms: tuple[str, ...], ids: list[str]) -> list[tuple[object, float]]:
        ranked = [(self._records[mid], self._score(terms, self._records[mid].terms)) for mid in ids]
        ranked.sort(key=lambda item: (-item[1], -item[0].sequence, item[0].memory_id))
        return ranked

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
        ordered = self._priority_order(terms, candidate_ids)
        attempted: list[int] = []
        ranked_all: list[tuple[object, float]] = []
        exact_scored = 0
        accepted = False

        if ordered:
            for limit in self.candidate_ladder:
                attempted.append(limit)
                ids = ordered[: min(limit, len(ordered))]
                ranked_all = self._score_ids(terms, ids)
                exact_scored = len(ids)
                eligible = [(record, score) for record, score in ranked_all if score >= self.threshold]
                if eligible:
                    best = eligible[0][1]
                    runner = eligible[1][1] if len(eligible) > 1 else 0.0
                    margin = best - runner
                    conflict_pair = len(eligible) > 1 and _conflicts(eligible[0][0].terms, eligible[1][0].terms)
                    if conflict_pair or len(eligible) == 1 or margin >= self.ambiguity_margin:
                        accepted = True
                        break
                if exact_scored >= len(ordered):
                    break

            if not accepted and exact_scored < len(ordered):
                # Conservative fallback: if the ladder could not establish a safe
                # decision, score all indexed candidates rather than forcing one.
                attempted.append(len(ordered))
                ranked_all = self._score_ids(terms, ordered)
                exact_scored = len(ordered)

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
        self._last_adaptive_stats = AdaptiveCandidateStatsV099(
            raw_candidates=raw_count,
            exact_scored=exact_scored,
            attempted_limits=tuple(attempted),
            final_limit=final_limit,
            expanded=len(attempted) > 1,
            retained_fraction=retained,
        )
        metrics = CoreMetricsV098(
            len(self), raw_count, exact_scored, len(hits), best, runner, margin,
            decision, False, latency, 0.0, 0, 0, 0, int(abstained),
        )
        return AutonomousQueryResultV098(clean, hits, abstained, exact_scored, metrics)
