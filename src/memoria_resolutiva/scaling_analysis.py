from __future__ import annotations

from dataclasses import dataclass
import math


@dataclass(frozen=True, slots=True)
class ScalingPoint:
    events: int
    elapsed_s: float
    peak_bytes: int
    items: int

    @property
    def latency_us(self) -> float:
        return (self.elapsed_s / self.events) * 1e6

    @property
    def throughput(self) -> float:
        return self.events / self.elapsed_s if self.elapsed_s > 0 else float("inf")

    @property
    def bytes_per_item(self) -> float:
        return self.peak_bytes / max(1, self.items)


def log_slope(x1: float, y1: float, x2: float, y2: float) -> float:
    if min(x1, y1, x2, y2) <= 0 or x1 == x2:
        raise ValueError("positive distinct inputs required")
    return math.log(y2 / y1) / math.log(x2 / x1)


def latency_growth(points: list[ScalingPoint]) -> list[float]:
    pts = sorted(points, key=lambda p: p.events)
    return [p2.latency_us / p1.latency_us for p1, p2 in zip(pts, pts[1:])]


def empirical_time_exponents(points: list[ScalingPoint]) -> list[float]:
    pts = sorted(points, key=lambda p: p.events)
    return [log_slope(p1.events, p1.elapsed_s, p2.events, p2.elapsed_s) for p1, p2 in zip(pts, pts[1:])]


def empirical_memory_exponents(points: list[ScalingPoint]) -> list[float]:
    pts = sorted(points, key=lambda p: p.events)
    return [log_slope(p1.items, p1.peak_bytes, p2.items, p2.peak_bytes) for p1, p2 in zip(pts, pts[1:]) if p1.items != p2.items]


def classify_exponent(alpha: float, tolerance: float = 0.15) -> str:
    if alpha < tolerance:
        return "near_constant"
    if abs(alpha - 1.0) <= tolerance:
        return "near_linear"
    if alpha < 1.0 - tolerance:
        return "sublinear"
    return "superlinear"
