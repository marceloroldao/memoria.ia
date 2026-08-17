from __future__ import annotations

from dataclasses import dataclass
from math import sqrt


@dataclass(frozen=True, slots=True)
class RegimeProfile:
    name: str
    signature: tuple[float, ...]
    observations: int


def cosine(a: tuple[float, ...], b: tuple[float, ...]) -> float:
    if len(a) != len(b) or not a:
        raise ValueError("signatures must have same non-zero length")
    dot = sum(x * y for x, y in zip(a, b))
    na = sqrt(sum(x * x for x in a))
    nb = sqrt(sum(y * y for y in b))
    if na == 0 or nb == 0:
        return 0.0
    return dot / (na * nb)


class RegimeMemory:
    """Non-destructive memory of previously observed regimes.

    Historical regime profiles stay stored. A current stream prefix can be
    compared against those profiles and reactivate the closest known regime
    when similarity exceeds a threshold.
    """

    def __init__(self, threshold: float = 0.90):
        self.threshold = threshold
        self._profiles: dict[str, RegimeProfile] = {}

    def store(self, name: str, signature: tuple[float, ...], observations: int) -> None:
        if observations <= 0:
            raise ValueError("observations must be positive")
        self._profiles[name] = RegimeProfile(name, signature, observations)

    def profiles(self) -> list[RegimeProfile]:
        return list(self._profiles.values())

    def match(self, signature: tuple[float, ...]) -> tuple[str | None, float]:
        if not self._profiles:
            return None, 0.0
        scored = [(cosine(signature, p.signature), p.name) for p in self._profiles.values()]
        score, name = max(scored)
        if score < self.threshold:
            return None, score
        return name, score
