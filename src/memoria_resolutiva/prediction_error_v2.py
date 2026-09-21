from __future__ import annotations

from dataclasses import dataclass

from .cognitive_cycle_v2 import CausalPrediction, PredictionCorrection


@dataclass(frozen=True, slots=True)
class StructuralPredictionError:
    """Discrete structural mismatch between prediction and observation.

    This is intentionally categorical rather than a learned scalar. It captures
    what changed in the active hypothesis geometry after an observation.
    """

    kind: str
    predicted_branches: int
    surviving_branches: int
    eliminated_branches: int
    observation_depth: int
    surprising: bool


def classify_prediction_error(
    prediction: CausalPrediction,
    correction: PredictionCorrection,
) -> StructuralPredictionError:
    predicted = len(prediction.branches.active)
    surviving = len(correction.corrected.active)
    eliminated = max(0, predicted - surviving)
    depth = len(correction.observation_addresses)

    if correction.outcome == "no-observation":
        kind = "no-observation"
    elif correction.outcome == "no-prediction":
        kind = "unconstrained-observation"
    elif correction.corrected.exhausted:
        kind = "total-surprise"
    elif surviving < predicted:
        kind = "hypothesis-reduction"
    elif surviving == predicted:
        kind = "prediction-confirmed"
    else:
        # Current branch filtering cannot normally create extra branches, but the
        # classifier fails closed if a future resolver ever does so.
        kind = "structural-expansion"

    return StructuralPredictionError(
        kind=kind,
        predicted_branches=predicted,
        surviving_branches=surviving,
        eliminated_branches=eliminated,
        observation_depth=depth,
        surprising=(kind == "total-surprise"),
    )
