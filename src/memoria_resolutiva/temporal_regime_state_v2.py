from __future__ import annotations

from dataclasses import dataclass

from .world_state_candidate_resolution_v2 import WorldStateCandidate, WorldStateCandidateResolution, WorldStateCandidateMatch


@dataclass(frozen=True, slots=True)
class TemporalOutcomeKey:
    consequence_addresses: tuple[str, ...]
    next_state_addresses: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class TemporalRegimeState:
    """Ephemeral continuity state layered above persistent historical memory.

    Historical evidence is never deleted or marked false.  This state only records
    which concrete outcome has shown uninterrupted/repeated continuity in the current
    stream, plus a pending alternative that may become a new regime if independently
    repeated across successive observations.
    """

    active: TemporalOutcomeKey | None
    pending: TemporalOutcomeKey | None
    pending_count: int
    active_run: int
    generation: int
    switches: int
    observations: int

    @classmethod
    def empty(cls) -> "TemporalRegimeState":
        return cls(None, None, 0, 0, 0, 0, 0)


def outcome_key(candidate: WorldStateCandidate) -> TemporalOutcomeKey:
    return TemporalOutcomeKey(candidate.consequence_addresses, candidate.next_state_addresses)


def observe_regime(
    state: TemporalRegimeState,
    candidate: WorldStateCandidate,
    *,
    min_contiguous_support: int = 2,
) -> TemporalRegimeState:
    """Advance current-regime continuity without recency weights or history deletion."""
    if min_contiguous_support < 2:
        raise ValueError("min_contiguous_support must be >= 2")

    observed = outcome_key(candidate)
    observations = state.observations + 1

    if state.active is None:
        if state.pending == observed:
            count = state.pending_count + 1
        else:
            count = 1
        if count >= min_contiguous_support:
            return TemporalRegimeState(
                active=observed,
                pending=None,
                pending_count=0,
                active_run=count,
                generation=state.generation + 1,
                switches=state.switches,
                observations=observations,
            )
        return TemporalRegimeState(
            active=None,
            pending=observed,
            pending_count=count,
            active_run=0,
            generation=state.generation,
            switches=state.switches,
            observations=observations,
        )

    if observed == state.active:
        return TemporalRegimeState(
            active=state.active,
            pending=None,
            pending_count=0,
            active_run=state.active_run + 1,
            generation=state.generation,
            switches=state.switches,
            observations=observations,
        )

    # A different observation challenges the current regime but does not replace it
    # until the alternative itself has contiguous support.
    if state.pending == observed:
        count = state.pending_count + 1
    else:
        count = 1

    if count >= min_contiguous_support:
        return TemporalRegimeState(
            active=observed,
            pending=None,
            pending_count=0,
            active_run=count,
            generation=state.generation + 1,
            switches=state.switches + 1,
            observations=observations,
        )

    return TemporalRegimeState(
        active=state.active,
        pending=observed,
        pending_count=count,
        active_run=state.active_run,
        generation=state.generation,
        switches=state.switches,
        observations=observations,
    )


def constrain_prediction_to_active_regime(
    resolution: WorldStateCandidateResolution,
    regime: TemporalRegimeState,
) -> WorldStateCandidateResolution:
    """Use current continuity to narrow historical ambiguity, never to invent a future.

    If the active concrete regime is among structurally compatible world candidates,
    it becomes the current prediction. If it is absent, the historical structural
    resolution is returned unchanged so the next observation can challenge/reorient
    the regime rather than being forced into an unsupported answer.
    """
    if regime.active is None or not resolution.matches:
        return resolution

    compatible = tuple(
        match for match in resolution.matches if outcome_key(match.candidate) == regime.active
    )
    if not compatible:
        return resolution
    if len(compatible) > 1:
        return WorldStateCandidateResolution(
            structural=resolution.structural,
            matches=compatible,
            resolved_candidate=None,
            resolved=False,
            ambiguous=True,
            reason="active-regime-still-ambiguous",
        )

    match: WorldStateCandidateMatch = compatible[0]
    return WorldStateCandidateResolution(
        structural=resolution.structural,
        matches=compatible,
        resolved_candidate=match.candidate,
        resolved=True,
        ambiguous=False,
        reason="active-temporal-regime",
    )
