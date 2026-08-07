from __future__ import annotations

from collections import deque
from dataclasses import dataclass


@dataclass(slots=True)
class _Bin:
    positives: float = 0.0
    total: float = 0.0


class AdaptiveBinnedCalibrator:
    """Online binned calibrator with optional window or exponential decay.

    Modes:
    - cumulative: all resolved history has equal weight;
    - window: only the most recent `window_size` resolved decisions are retained;
    - decay: historical bin counts are multiplied by `decay` before each update.
    """

    def __init__(self, bins: int = 10, mode: str = "cumulative", window_size: int = 250, decay: float = 0.995, prior: float = 1.0):
        if bins <= 0 or prior <= 0:
            raise ValueError("bins and prior must be positive")
        if mode not in {"cumulative", "window", "decay"}:
            raise ValueError("unknown mode")
        if window_size <= 0 or not 0.0 < decay <= 1.0:
            raise ValueError("invalid adaptive parameters")
        self.bins = bins
        self.mode = mode
        self.window_size = window_size
        self.decay = decay
        self.prior = prior
        self._stats = [_Bin() for _ in range(bins)]
        self._window: deque[tuple[int, int]] = deque()

    def _idx(self, p: float) -> int:
        if not 0.0 <= p <= 1.0:
            raise ValueError("probability must be in [0,1]")
        return min(self.bins - 1, int(p * self.bins))

    def predict(self, raw_p: float) -> float:
        b = self._stats[self._idx(raw_p)]
        # Symmetric Beta prior keeps unseen bins neutral.
        return (self.prior + b.positives) / (2.0 * self.prior + b.total)

    def update(self, raw_p: float, outcome: int) -> None:
        if outcome not in (0, 1):
            raise ValueError("outcome must be binary")
        idx = self._idx(raw_p)
        if self.mode == "decay":
            for b in self._stats:
                b.positives *= self.decay
                b.total *= self.decay
        b = self._stats[idx]
        b.positives += outcome
        b.total += 1.0
        if self.mode == "window":
            self._window.append((idx, outcome))
            if len(self._window) > self.window_size:
                old_idx, old_y = self._window.popleft()
                old = self._stats[old_idx]
                old.positives -= old_y
                old.total -= 1.0

    def effective_mass(self) -> float:
        return sum(b.total for b in self._stats)
