from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, Mapping, Hashable

from .adaptive_recompute import HysteresisRecomputePolicy
from .incremental_recompute import IncrementalRecomputeGraph, RecomputeDecision
from .workload_profile import WorkloadProfile, classify_workload


@dataclass(frozen=True, slots=True)
class WorkloadExecution:
    profile: WorkloadProfile
    requested_strategy: str
    executed_strategy: str
    decision: RecomputeDecision
    fallback_used: bool


class WorkloadStrategyExecutor:
    """Execute the classifier recommendation with explicit, auditable fallback.

    The executor keeps classification and execution separate in the result so a
    caller can inspect what the classifier recommended and what actually ran.
    Unknown recommendations fall back to the existing single-threshold adaptive
    path rather than guessing a new strategy.
    """

    def __init__(
        self,
        *,
        adaptive_threshold: float = 0.40,
        enter_full_threshold: float = 0.45,
        exit_full_threshold: float = 0.30,
    ) -> None:
        self.adaptive_threshold = adaptive_threshold
        self.hysteresis = HysteresisRecomputePolicy(
            enter_full_threshold=enter_full_threshold,
            exit_full_threshold=exit_full_threshold,
        )

    def execute(
        self,
        graph: IncrementalRecomputeGraph,
        updates: Mapping[Hashable, float],
        recent_affected_fractions: Iterable[float],
    ) -> WorkloadExecution:
        profile = classify_workload(recent_affected_fractions)
        requested = profile.recommended_strategy
        fallback = False

        if requested == "incremental":
            if not updates:
                decision = RecomputeDecision("incremental", (), 0.0)
            else:
                changed = graph._validate_root_updates(updates)
                affected = graph._affected(changed)
                fraction = len(affected) / len(graph.nodes) if graph.nodes else 0.0
                touched = graph.update_roots_incremental(updates)
                decision = RecomputeDecision("incremental", tuple(touched), fraction)
            executed = "incremental"
        elif requested == "hysteresis":
            decision = self.hysteresis.apply(graph, updates)
            executed = "hysteresis"
        elif requested == "adaptive":
            decision = graph.update_roots_adaptive(
                updates,
                full_threshold=self.adaptive_threshold,
            )
            executed = "adaptive"
        else:
            fallback = True
            decision = graph.update_roots_adaptive(
                updates,
                full_threshold=self.adaptive_threshold,
            )
            executed = "adaptive"

        return WorkloadExecution(
            profile=profile,
            requested_strategy=requested,
            executed_strategy=executed,
            decision=decision,
            fallback_used=fallback,
        )
