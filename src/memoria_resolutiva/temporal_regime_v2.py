from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class TemporalRegimeState:
    """Ephemeral continuity state over concrete world outcomes.

    Historical evidence is not deleted or reweighted. This state only records which
    concrete continuation has shown sufficient *contiguous* support in the current
    stream. A competing continuation must itself accumulate contiguous support before
    it can replace the active regime.
    """

    active_key: str | None
    challenger_key: str | None
    challenger_streak: int
    active_streak: int
    generation: int
    observations: int


@dataclass(frozen=True, slots=True)
class TemporalRegimeUpdate:
    previous: TemporalRegimeState
    current: TemporalRegimeState
    observed_key: str
    event: str
    switched: bool


def initial_temporal_regime() -> TemporalRegimeState:
    return TemporalRegimeState(
        active_key=None,
        challenger_key=None,
        challenger_streak=0,
        active_streak=0,
        generation=0,
        observations=0,
    )


def observe_temporal_regime(
    state: TemporalRegimeState,
    observed_key: str,
    *,
    min_contiguous_support: int = 2,
) -> TemporalRegimeUpdate:
    if not observed_key:
        raise ValueError("observed_key must be non-empty")
    if min_contiguous_support < 1:
        raise ValueError("min_contiguous_support must be >= 1")

    observations = state.observations + 1

    # No regime yet: accumulate contiguous evidence for the first candidate.
    if state.active_key is None:
        streak = state.challenger_streak + 1 if state.challenger_key == observed_key else 1
        if streak >= min_contiguous_support:
            current = TemporalRegimeState(
                active_key=observed_key,
                challenger_key=None,
                challenger_streak=0,
                active_streak=streak,
                generation=state.generation + 1,
                observations=observations,
            )
            return TemporalRegimeUpdate(state, current, observed_key, "regime-established", True)

        current = TemporalRegimeState(
            active_key=None,
            challenger_key=observed_key,
            challenger_streak=streak,
            active_streak=0,
            generation=state.generation,
            observations=observations,
        )
        return TemporalRegimeUpdate(state, current, observed_key, "candidate-accumulating", False)

    # Observation agrees with current continuity. Any challenger loses continuity.
    if observed_key == state.active_key:
        current = TemporalRegimeState(
            active_key=state.active_key,
            challenger_key=None,
            challenger_streak=0,
            active_streak=state.active_streak + 1,
            generation=state.generation,
            observations=observations,
        )
        return TemporalRegimeUpdate(state, current, observed_key, "active-confirmed", False)

    # Competing observation: accumulate contiguous evidence without erasing history.
    challenger_streak = (
        state.challenger_streak + 1 if state.challenger_key == observed_key else 1
    )
    if challenger_streak >= min_contiguous_support:
        current = TemporalRegimeState(
            active_key=observed_key,
            challenger_key=None,
            challenger_streak=0,
            active_streak=challenger_streak,
            generation=state.generation + 1,
            observations=observations,
        )
        return TemporalRegimeUpdate(state, current, observed_key, "regime-switched", True)

    current = TemporalRegimeState(
        active_key=state.active_key,
        challenger_key=observed_key,
        challenger_streak=challenger_streak,
        active_streak=state.active_streak,
        generation=state.generation,
        observations=observations,
    )
    return TemporalRegimeUpdate(state, current, observed_key, "challenger-accumulating", False)
