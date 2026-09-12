from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

from .world_state_candidate_resolution_v2 import WorldStateCandidate


@dataclass(frozen=True, slots=True)
class LiveWorldStateFrame:
    """Godot-agnostic snapshot contract for Live.Infinita -> Memoria.ia V2.

    The adapter layer is responsible only for stable addressing and ordering. It does
    not encode semantic types such as entity, color, intent, or concept into the V2
    engine. `state_addresses` describes the currently observed configuration.
    """

    frame_id: str
    state_addresses: tuple[str, ...]
    provenance: str = "live.infinita"


@dataclass(frozen=True, slots=True)
class LiveInterventionFrame:
    """One externally delimited intervention applied to a world-state frame."""

    intervention_id: str
    address: str
    provenance: str = "live.infinita"


@dataclass(frozen=True, slots=True)
class LiveCandidateFrame:
    """A concrete possible/observed world continuation supplied by Live.Infinita."""

    candidate_id: str
    consequence_addresses: tuple[str, ...]
    next_state_addresses: tuple[str, ...]
    provenance: str = "live.infinita"


@dataclass(frozen=True, slots=True)
class LiveWorldStateRequest:
    """Minimal serializable bridge request consumed by the V2 world-state resolver."""

    state: LiveWorldStateFrame
    intervention: LiveInterventionFrame
    candidates: tuple[LiveCandidateFrame, ...]


def _collapse(addresses: Iterable[str]) -> tuple[str, ...]:
    output: list[str] = []
    current: str | None = None
    for value in addresses:
        if not isinstance(value, str) or not value:
            raise ValueError("addresses must be non-empty strings")
        if value == current:
            continue
        output.append(value)
        current = value
    return tuple(output)


def make_live_request(
    *,
    frame_id: str,
    state_addresses: Iterable[str],
    intervention_id: str,
    intervention_address: str,
    candidates: Iterable[tuple[str, Iterable[str], Iterable[str]]],
    provenance: str = "live.infinita",
) -> LiveWorldStateRequest:
    """Normalize a Live.Infinita frame into the V2 bridge contract.

    The function is intentionally transport-agnostic. Godot, WebSocket, HTTP or a
    local simulator may produce the same payload as long as addresses are stable.
    """
    if not frame_id:
        raise ValueError("frame_id must be non-empty")
    if not intervention_id:
        raise ValueError("intervention_id must be non-empty")
    if not intervention_address:
        raise ValueError("intervention_address must be non-empty")

    state = _collapse(state_addresses)
    if not state:
        raise ValueError("state_addresses must be non-empty")

    normalized_candidates: list[LiveCandidateFrame] = []
    seen_ids: set[str] = set()
    for candidate_id, consequence, next_state in candidates:
        if not candidate_id or candidate_id in seen_ids:
            raise ValueError("candidate_id must be unique and non-empty")
        seen_ids.add(candidate_id)
        consequence_addresses = _collapse(consequence)
        next_state_addresses = _collapse(next_state)
        if not consequence_addresses or not next_state_addresses:
            raise ValueError("candidate consequence/next state must be non-empty")
        normalized_candidates.append(
            LiveCandidateFrame(
                candidate_id=candidate_id,
                consequence_addresses=consequence_addresses,
                next_state_addresses=next_state_addresses,
                provenance=provenance,
            )
        )

    normalized_candidates.sort(key=lambda item: item.candidate_id)
    return LiveWorldStateRequest(
        state=LiveWorldStateFrame(frame_id, state, provenance),
        intervention=LiveInterventionFrame(intervention_id, intervention_address, provenance),
        candidates=tuple(normalized_candidates),
    )


def to_world_state_candidates(
    request: LiveWorldStateRequest,
) -> tuple[WorldStateCandidate, ...]:
    return tuple(
        WorldStateCandidate(
            candidate_id=item.candidate_id,
            consequence_addresses=item.consequence_addresses,
            next_state_addresses=item.next_state_addresses,
        )
        for item in request.candidates
    )
