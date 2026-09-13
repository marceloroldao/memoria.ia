from __future__ import annotations

from dataclasses import dataclass

from .prediction_error_v2 import StructuralPredictionError


@dataclass(frozen=True, slots=True)
class StructuralAttention:
    """Ordinal attention state derived only from prediction geometry.

    Attention is deliberately categorical rather than a learned scalar.  It says
    whether the latest observation can remain routine, carried useful structural
    information, or requires cognitive reorientation.  No semantic labels from
    the observed addresses participate in this decision.
    """

    level: str
    reason: str
    requires_recovery: bool
    informative: bool
    prediction_constrained: bool
    eliminated_branches: int
    observation_depth: int


def derive_structural_attention(error: StructuralPredictionError) -> StructuralAttention:
    """Map a structural prediction error to an auditable attention state.

    Ordering is qualitative only:

    routine < informative < reorient

    There is intentionally no numeric score.  A total surprise requires
    reorientation because every previously active continuation was eliminated.
    Hypothesis reduction is informative because the observation removed at least
    one live alternative while preserving another.  A confirmed prediction stays
    routine.  An unconstrained observation remains exploratory: the system had no
    prediction to violate, so it must not manufacture surprise.
    """

    if error.kind == "total-surprise":
        return StructuralAttention(
            level="reorient",
            reason="all-predicted-branches-eliminated",
            requires_recovery=True,
            informative=True,
            prediction_constrained=True,
            eliminated_branches=error.eliminated_branches,
            observation_depth=error.observation_depth,
        )

    if error.kind == "hypothesis-reduction":
        return StructuralAttention(
            level="informative",
            reason="observation-reduced-live-hypotheses",
            requires_recovery=False,
            informative=True,
            prediction_constrained=True,
            eliminated_branches=error.eliminated_branches,
            observation_depth=error.observation_depth,
        )

    if error.kind == "structural-expansion":
        # Current filtering should not expand branches. If a later resolver does,
        # the conservative response is reorientation rather than arbitrary rank.
        return StructuralAttention(
            level="reorient",
            reason="unexpected-structural-expansion",
            requires_recovery=False,
            informative=True,
            prediction_constrained=True,
            eliminated_branches=error.eliminated_branches,
            observation_depth=error.observation_depth,
        )

    if error.kind == "unconstrained-observation":
        return StructuralAttention(
            level="informative",
            reason="observation-without-prior-prediction",
            requires_recovery=False,
            informative=True,
            prediction_constrained=False,
            eliminated_branches=0,
            observation_depth=error.observation_depth,
        )

    if error.kind == "no-observation":
        return StructuralAttention(
            level="routine",
            reason="no-new-observation",
            requires_recovery=False,
            informative=False,
            prediction_constrained=error.predicted_branches > 0,
            eliminated_branches=0,
            observation_depth=0,
        )

    # prediction-confirmed and any future benign classifier state default to
    # routine attention rather than creating urgency without structural evidence.
    return StructuralAttention(
        level="routine",
        reason="prediction-remains-compatible",
        requires_recovery=False,
        informative=False,
        prediction_constrained=error.predicted_branches > 0,
        eliminated_branches=error.eliminated_branches,
        observation_depth=error.observation_depth,
    )
