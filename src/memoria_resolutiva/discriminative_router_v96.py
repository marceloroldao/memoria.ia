from __future__ import annotations

from collections import Counter, defaultdict
from dataclasses import dataclass
from math import log
from typing import Iterable

from .semantic_router_v96 import SemanticResolution, SemanticRouterV96


@dataclass(frozen=True, slots=True)
class CandidateStats:
    total_concepts: int
    candidate_concepts: int
    retained_fraction: float


class DiscriminativeSemanticRouterV96(SemanticRouterV96):
    """Experimental candidate pruning using inverse concept frequency.

    When the native core is available, both discriminative candidate selection
    and exact top-two scoring are performed authoritatively in C++. The Python
    implementation remains the reference/fallback path.
    """

    def __init__(
        self,
        *,
        radius: int = 3,
        threshold: float = 0.60,
        min_margin: float = 0.08,
        candidate_limit: int = 32,
        use_native: bool | None = None,
    ) -> None:
        super().__init__(
            radius=radius,
            threshold=threshold,
            min_margin=min_margin,
            indexed=False,
            use_native=use_native,
            native_authoritative=None if use_native is not False else False,
        )
        if candidate_limit < 2:
            raise ValueError("candidate_limit must be >= 2")
        self.candidate_limit = candidate_limit
        self._feature_df: Counter[str] = Counter()
        self._feature_to_concepts_weighted: dict[str, set[str]] = defaultdict(set)
        self._disc_dirty = True
        self._last_candidate_count = 0

    def observe(self, sentences: Iterable[str]) -> None:
        super().observe(sentences)
        self._disc_dirty = True

    def register_concept(self, concept_id: str, anchors: Iterable[str]) -> None:
        super().register_concept(concept_id, anchors)
        self._disc_dirty = True

    def _rebuild_discriminative_index(self) -> None:
        feature_to_concepts: dict[str, set[str]] = defaultdict(set)
        profiles = self.memory.associator.profiles
        for concept_id, anchors in self._concepts.items():
            features: set[str] = set()
            for anchor in anchors:
                features.update(self._profile_tokens(profiles.get(anchor)))
            for feature in features:
                feature_to_concepts[feature].add(concept_id)
        self._feature_to_concepts_weighted = feature_to_concepts
        self._feature_df = Counter({f: len(ids) for f, ids in feature_to_concepts.items()})
        self._disc_dirty = False

    def _discriminative_candidates(self, query: str) -> list[str]:
        native = self.memory.discriminative_candidates(query, self.candidate_limit)
        if native is not None:
            self._last_candidate_count = len(native)
            return native

        if self._disc_dirty:
            self._rebuild_discriminative_index()
        profile = self.memory.associator.profiles.get(query)
        features = self._profile_tokens(profile)
        if not features:
            self._last_candidate_count = 0
            return []

        n = max(1, len(self._concepts))
        score: Counter[str] = Counter()
        for feature in features:
            df = self._feature_df.get(feature, 0)
            if df == 0:
                continue
            weight = log((n + 1) / (df + 1)) + 1.0
            for concept_id in self._feature_to_concepts_weighted.get(feature, ()):
                score[concept_id] += weight

        ranked = sorted(score.items(), key=lambda x: (-x[1], x[0]))
        ids = [concept_id for concept_id, _ in ranked[: self.candidate_limit]]
        self._last_candidate_count = len(ids)
        return ids

    def candidate_stats(self) -> CandidateStats:
        total = len(self._concepts)
        count = self._last_candidate_count
        return CandidateStats(
            total_concepts=total,
            candidate_concepts=count,
            retained_fraction=(count / total if total else 0.0),
        )

    def resolve_token(self, query: str) -> SemanticResolution:
        q = query.strip().lower()
        if not q:
            raise ValueError("query must not be empty")
        candidate_ids = self._discriminative_candidates(q)
        if not candidate_ids:
            return SemanticResolution(q, None, 0.0, 0.0, "unresolved")

        ranked = self.memory.rank_registered(q, candidate_ids, top_k=2)
        if ranked is None:
            ranked = []
            for concept_id in candidate_ids:
                anchors = self._concepts[concept_id]
                best = max((self._score(q, anchor) for anchor in anchors), default=0.0)
                ranked.append((concept_id, best))
            ranked.sort(key=lambda item: (-item[1], item[0]))
            ranked = ranked[:2]

        best_id, best_score = ranked[0]
        second_score = ranked[1][1] if len(ranked) > 1 else 0.0
        margin = best_score - second_score
        if best_score >= self.threshold and margin >= self.min_margin:
            return SemanticResolution(q, best_id, best_score, margin, "memory")
        return SemanticResolution(q, None, best_score, margin, "unresolved")
