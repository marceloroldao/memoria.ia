from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class InterventionOption:
    intervention_address: str
    possible_outcomes: tuple[tuple[str, ...], ...]
    available: bool = True


@dataclass(frozen=True, slots=True)
class ActiveCausalExperiment:
    active: bool
    intervention_address: str | None
    discriminative_outcomes: tuple[tuple[str, ...], ...]
    shared_outcomes: tuple[tuple[str, ...], ...]
    reason: str


def select_active_causal_experiment(
    *,
    hypothesis_outcomes: tuple[tuple[str, tuple[str, ...]], ...],
    options: tuple[InterventionOption, ...],
) -> ActiveCausalExperiment:
    """Choose an available intervention that best separates live hypotheses.

    `hypothesis_outcomes` contains pairs of (hypothesis_id, expected_outcome).
    No semantic meaning or learned scalar score is used. Selection is ordinal:
    prefer an intervention whose available outcomes maximize distinct partitions and
    minimize outcome sharing across hypotheses. Ties resolve deterministically by
    intervention address. No unavailable intervention is invented.
    """

    if len(hypothesis_outcomes) < 2:
        return ActiveCausalExperiment(False, None, (), (), "insufficient-competing-hypotheses")

    active_options = tuple(item for item in options if item.available and item.intervention_address)
    if not active_options:
        return ActiveCausalExperiment(False, None, (), (), "no-available-intervention")

    expected = tuple(outcome for _, outcome in hypothesis_outcomes)
    expected_set = set(expected)
    candidates: list[tuple[int, int, str, InterventionOption, tuple[tuple[str, ...], ...], tuple[tuple[str, ...], ...]]] = []

    for option in active_options:
        offered = tuple(dict.fromkeys(tuple(outcome) for outcome in option.possible_outcomes if outcome))
        discriminative = tuple(sorted(outcome for outcome in offered if outcome in expected_set))
        if len(set(discriminative)) < 2:
            continue

        shared = tuple(sorted(outcome for outcome in offered if expected.count(outcome) > 1))
        distinct_count = len(set(discriminative))
        shared_count = len(shared)
        candidates.append((distinct_count, -shared_count, option.intervention_address, option, discriminative, shared))

    if not candidates:
        return ActiveCausalExperiment(False, None, (), (), "no-discriminative-available-intervention")

    candidates.sort(key=lambda item: (-item[0], -item[1], item[2]))
    _, _, _, chosen, discriminative, shared = candidates[0]
    return ActiveCausalExperiment(
        True,
        chosen.intervention_address,
        discriminative,
        shared,
        "available-intervention-separates-competing-hypotheses",
    )
