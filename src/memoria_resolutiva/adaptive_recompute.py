from __future__ import annotations

from dataclasses import dataclass
from typing import Hashable, Mapping

from .incremental_recompute import IncrementalRecomputeGraph, RecomputeDecision


@dataclass(slots=True)
class HysteresisRecomputePolicy:
    """Stateful adaptive recompute policy with separate enter/exit thresholds.

    The policy enters full recomputation only when the affected fraction reaches
    ``enter_full_threshold``. Once in full mode, it remains there until the
    affected fraction falls below ``exit_full_threshold``. This prevents mode
    oscillation when workload density fluctuates around one boundary.
    """

    enter_full_threshold: float = 0.50
    exit_full_threshold: float = 0.35
    mode: str = "incremental"

    def __post_init__(self) -> None:
        if not 0.0 < self.exit_full_threshold < self.enter_full_threshold <= 1.0:
            raise ValueError(
                "thresholds must satisfy 0 < exit_full_threshold < "
                "enter_full_threshold <= 1"
            )
        if self.mode not in {"incremental", "full"}:
            raise ValueError("mode must be 'incremental' or 'full'")

    def apply(
        self,
        graph: IncrementalRecomputeGraph,
        updates: Mapping[Hashable, float],
    ) -> RecomputeDecision:
        if not updates:
            return RecomputeDecision(self.mode, (), 0.0)

        changed = graph._validate_root_updates(updates)
        affected = graph._affected(changed)
        affected_fraction = len(affected) / len(graph.nodes) if graph.nodes else 0.0

        if self.mode == "incremental":
            if affected_fraction >= self.enter_full_threshold:
                self.mode = "full"
        elif affected_fraction < self.exit_full_threshold:
            self.mode = "incremental"

        if self.mode == "incremental":
            touched = graph.update_roots_incremental(updates)
        else:
            graph._apply_root_updates(updates)
            touched = graph.full_recompute()

        return RecomputeDecision(self.mode, tuple(touched), affected_fraction)
