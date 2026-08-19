from __future__ import annotations

from collections import Counter

from .sentence_semantic_router_v96 import SentenceSemanticRouterV96, _STOPWORDS
from .trajectory_contrastive_v96 import TrajectoryContrastiveRouterV96
from .textual import tokenize


_NEGATORS = {"nao", "sem", "nunca", "jamais"}


class StateAwareSentenceSemanticRouterV96(SentenceSemanticRouterV96):
    """Sparse non-neural sentence router with local state/negation features.

    The v0.96 sentence baseline is bag-of-content-words. That representation
    loses relations such as `fibra nao rompeu` versus `fibra rompeu` and tends
    to overreact to entity words such as `roteador`, `fibra` or `conta`.

    This experimental router preserves the baseline unigrams and adds:
    - adjacent content-word bigrams (`bi:a|b`);
    - local negation scope markers (`neg:token`) for up to two content words
      following a negator.

    It remains deterministic and non-neural. The feature expansion is kept in a
    separate experiment so the published/baseline behavior is not silently
    changed.
    """

    @staticmethod
    def _content_profile(text: str) -> Counter[str]:
        raw = tokenize(text)
        profile: Counter[str] = Counter()
        content_sequence: list[str] = []
        negation_budget = 0

        for token in raw:
            if token in _NEGATORS:
                negation_budget = 2
                continue
            if token in _STOPWORDS:
                continue

            profile[token] += 1
            content_sequence.append(token)
            if negation_budget > 0:
                profile[f"neg:{token}"] += 1
                negation_budget -= 1

        for left, right in zip(content_sequence, content_sequence[1:]):
            profile[f"bi:{left}|{right}"] += 1

        return profile


class StateAwareTrajectoryContrastiveRouterV96(TrajectoryContrastiveRouterV96):
    """Trajectory contrastive router using state-aware sentence features."""

    def __init__(
        self,
        *,
        threshold: float = 0.12,
        min_margin: float = 0.02,
        negative_threshold: float = 0.20,
        min_contrast_margin: float = 0.04,
    ) -> None:
        super().__init__(
            threshold=threshold,
            min_margin=min_margin,
            negative_threshold=negative_threshold,
            min_contrast_margin=min_contrast_margin,
        )
        self.base = StateAwareSentenceSemanticRouterV96(
            threshold=threshold,
            min_margin=min_margin,
        )
