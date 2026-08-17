from __future__ import annotations

from collections import Counter, defaultdict
from dataclasses import dataclass, field
import re

TOKEN_RE = re.compile(r"[\wÀ-ÿ]+", re.UNICODE)


def tokenize(text: str) -> list[str]:
    return TOKEN_RE.findall(text.lower())


def jaccard(a: set[str], b: set[str]) -> float:
    if not a and not b:
        return 1.0
    union = a | b
    return len(a & b) / len(union) if union else 0.0


@dataclass(slots=True)
class Sense:
    sense_id: int
    contexts: Counter[str] = field(default_factory=Counter)
    occurrences: int = 0

    def signature(self, top_k: int = 12) -> set[str]:
        return {token for token, _ in self.contexts.most_common(top_k)}


class PolysemyMemory:
    """Incremental word-sense memory based on contextual trajectories.

    A surface token can own multiple sense nodes. New observations are attached
    to the closest existing sense when contextual overlap is sufficient;
    otherwise a new sense is created. No neural model or global retraining is
    required.
    """

    def __init__(self, window: int = 3, split_threshold: float = 0.18):
        self.window = window
        self.split_threshold = split_threshold
        self._senses: dict[str, list[Sense]] = defaultdict(list)

    def _context(self, tokens: list[str], index: int) -> set[str]:
        left = tokens[max(0, index - self.window):index]
        right = tokens[index + 1:index + 1 + self.window]
        return set(left + right)

    def observe(self, text: str) -> None:
        tokens = tokenize(text)
        for i, token in enumerate(tokens):
            context = self._context(tokens, i)
            if not context:
                continue
            senses = self._senses[token]
            if not senses:
                senses.append(Sense(0))
                target = senses[0]
            else:
                scored = [(jaccard(context, s.signature()), s) for s in senses]
                score, target = max(scored, key=lambda item: item[0])
                if score < self.split_threshold:
                    target = Sense(len(senses))
                    senses.append(target)
            target.contexts.update(context)
            target.occurrences += 1

    def senses(self, token: str) -> list[Sense]:
        return list(self._senses.get(token.lower(), []))

    def resolve(self, token: str, context_words: set[str]) -> tuple[int | None, float]:
        senses = self._senses.get(token.lower(), [])
        if not senses:
            return None, 0.0
        scored = [(jaccard(context_words, s.signature()), s.sense_id) for s in senses]
        score, sense_id = max(scored)
        return sense_id, score

    def describe(self, token: str, top_k: int = 8) -> list[dict]:
        return [
            {
                "sense_id": s.sense_id,
                "occurrences": s.occurrences,
                "signature": s.contexts.most_common(top_k),
            }
            for s in self._senses.get(token.lower(), [])
        ]
