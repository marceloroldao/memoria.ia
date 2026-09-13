from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

from .active_causal_experiment_v2 import InterventionOption, select_active_causal_experiment


@dataclass(frozen=True, slots=True)
class CausalHypothesis:
    hypothesis_id: str
    expected_outcome: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class ActiveCausalStep:
    step_index: int
    intervention_address: str | None
    observed_outcome: tuple[str, ...] | None
    surviving_hypotheses: tuple[str, ...]
    eliminated_hypotheses: tuple[str, ...]
    stopped: bool
    reason: str


@dataclass(frozen=True, slots=True)
class ActiveCausalLoopResult:
    steps: tuple[ActiveCausalStep, ...]
    surviving_hypotheses: tuple[str, ...]
    resolved: bool
    exhausted: bool
    reason: str


def run_active_causal_loop(
    *,
    hypotheses: tuple[CausalHypothesis, ...],
    options_provider: Callable[[tuple[CausalHypothesis, ...]], tuple[InterventionOption, ...]],
    execute_intervention: Callable[[str], tuple[str, ...]],
    max_steps: int = 8,
) -> ActiveCausalLoopResult:
    """Run a deterministic active experiment loop over explicit hypotheses.

    The loop does not invent interventions or meanings. It asks the selector for an
    available discriminative intervention, executes it through the provided world
    adapter, keeps hypotheses whose expected outcome matches the observation, and
    stops when one hypothesis remains, none remain, no discriminative intervention
    is available, or `max_steps` is reached.

    This is ephemeral cognitive state. It does not mutate persistent memory by itself.
    """

    if max_steps < 1:
        raise ValueError("max_steps must be >= 1")
    if any(not item.hypothesis_id or not item.expected_outcome for item in hypotheses):
        raise ValueError("hypotheses must contain non-empty ids and outcomes")

    # deterministic de-duplication by id while preserving the first declaration
    unique: dict[str, CausalHypothesis] = {}
    for item in hypotheses:
        unique.setdefault(item.hypothesis_id, item)
    active = tuple(unique[key] for key in sorted(unique))
    steps: list[ActiveCausalStep] = []

    if len(active) <= 1:
        return ActiveCausalLoopResult(
            steps=(),
            surviving_hypotheses=tuple(item.hypothesis_id for item in active),
            resolved=len(active) == 1,
            exhausted=len(active) == 0,
            reason="already-resolved" if active else "no-active-hypotheses",
        )

    for step_index in range(max_steps):
        options = options_provider(active)
        experiment = select_active_causal_experiment(
            hypothesis_outcomes=tuple((item.hypothesis_id, item.expected_outcome) for item in active),
            options=options,
        )
        if not experiment.active or experiment.intervention_address is None:
            steps.append(
                ActiveCausalStep(
                    step_index=step_index,
                    intervention_address=None,
                    observed_outcome=None,
                    surviving_hypotheses=tuple(item.hypothesis_id for item in active),
                    eliminated_hypotheses=(),
                    stopped=True,
                    reason=experiment.reason,
                )
            )
            return ActiveCausalLoopResult(
                steps=tuple(steps),
                surviving_hypotheses=tuple(item.hypothesis_id for item in active),
                resolved=False,
                exhausted=False,
                reason=experiment.reason,
            )

        observed = tuple(execute_intervention(experiment.intervention_address))
        if not observed:
            raise ValueError("world returned an empty observation")

        survivors = tuple(item for item in active if item.expected_outcome == observed)
        survivor_ids = tuple(item.hypothesis_id for item in survivors)
        eliminated_ids = tuple(item.hypothesis_id for item in active if item.hypothesis_id not in survivor_ids)

        if len(survivors) == 1:
            reason = "ambiguity-resolved-by-active-experiment"
            stopped = True
        elif len(survivors) == 0:
            reason = "observation-exhausted-active-hypotheses"
            stopped = True
        else:
            reason = "ambiguity-reduced"
            stopped = False

        steps.append(
            ActiveCausalStep(
                step_index=step_index,
                intervention_address=experiment.intervention_address,
                observed_outcome=observed,
                surviving_hypotheses=survivor_ids,
                eliminated_hypotheses=eliminated_ids,
                stopped=stopped,
                reason=reason,
            )
        )
        active = survivors

        if stopped:
            return ActiveCausalLoopResult(
                steps=tuple(steps),
                surviving_hypotheses=survivor_ids,
                resolved=len(survivors) == 1,
                exhausted=len(survivors) == 0,
                reason=reason,
            )

    return ActiveCausalLoopResult(
        steps=tuple(steps),
        surviving_hypotheses=tuple(item.hypothesis_id for item in active),
        resolved=len(active) == 1,
        exhausted=len(active) == 0,
        reason="max-steps-reached",
    )
