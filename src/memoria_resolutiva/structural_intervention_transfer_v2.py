from __future__ import annotations

from dataclasses import dataclass

from .intervention_consequence_v2 import InterventionConsequenceMemory, InterventionEpisode


def _equality_pattern(values: tuple[str, ...]) -> tuple[int, ...]:
    """Return a literal-free equality topology for an ordered tuple."""
    seen: dict[str, int] = {}
    pattern: list[int] = []
    next_id = 0
    for value in values:
        if value not in seen:
            seen[value] = next_id
            next_id += 1
        pattern.append(seen[value])
    return tuple(pattern)


def _relative_pattern(
    state: tuple[str, ...],
    intervention: str,
    values: tuple[str, ...],
) -> tuple[str, ...]:
    """Describe values only by their relation to state/action and prior outputs.

    No literal address is emitted. Each output unit is encoded as:
      S<n>  -> repeats state position n
      A     -> repeats intervention address
      N<n>  -> novel address, with n preserving equality among novel outputs
    """
    state_first: dict[str, int] = {}
    for index, address in enumerate(state):
        state_first.setdefault(address, index)

    novel: dict[str, int] = {}
    next_novel = 0
    output: list[str] = []
    for value in values:
        if value in state_first:
            output.append(f"S{state_first[value]}")
            continue
        if value == intervention:
            output.append("A")
            continue
        if value not in novel:
            novel[value] = next_novel
            next_novel += 1
        output.append(f"N{novel[value]}")
    return tuple(output)


@dataclass(frozen=True, slots=True)
class StructuralInterventionKey:
    state_width: int
    state_equality_pattern: tuple[int, ...]
    intervention_role: str


@dataclass(frozen=True, slots=True)
class StructuralConsequencePattern:
    consequence_pattern: tuple[str, ...]
    next_state_pattern: tuple[str, ...]
    supporting_episode_ids: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class StructuralInterventionResolution:
    query_key: StructuralInterventionKey
    patterns: tuple[StructuralConsequencePattern, ...]
    resolved: bool
    ambiguous: bool
    reason: str


def intervention_key(
    state_addresses: tuple[str, ...],
    intervention_address: str,
) -> StructuralInterventionKey:
    state = InterventionConsequenceMemory._collapse(state_addresses)
    if not state or not intervention_address:
        return StructuralInterventionKey(0, (), "invalid")

    if intervention_address in state:
        intervention_role = f"state-position:{state.index(intervention_address)}"
    else:
        intervention_role = "novel-to-state"

    return StructuralInterventionKey(
        state_width=len(state),
        state_equality_pattern=_equality_pattern(state),
        intervention_role=intervention_role,
    )


def _episode_key(episode: InterventionEpisode) -> StructuralInterventionKey:
    return intervention_key(episode.state_addresses, episode.intervention_address)


def resolve_structural_intervention(
    memory: InterventionConsequenceMemory,
    state_addresses: tuple[str, ...],
    intervention_address: str,
    *,
    min_independent_episodes: int = 2,
) -> StructuralInterventionResolution:
    """Transfer only literal-free consequence geometry across equivalent episodes.

    This intentionally does not invent a concrete future address in a new address
    space. It returns structural consequence patterns supported by independent
    episodes whose state/intervention topology matches the query topology.
    """
    if min_independent_episodes < 1:
        raise ValueError("min_independent_episodes must be >= 1")

    key = intervention_key(state_addresses, intervention_address)
    if key.intervention_role == "invalid":
        return StructuralInterventionResolution(key, (), False, False, "invalid-query")

    grouped: dict[tuple[tuple[str, ...], tuple[str, ...]], list[str]] = {}
    for episode in memory.snapshot():
        if _episode_key(episode) != key:
            continue
        consequence = _relative_pattern(
            episode.state_addresses,
            episode.intervention_address,
            episode.consequence_addresses,
        )
        next_state = _relative_pattern(
            episode.state_addresses,
            episode.intervention_address,
            episode.next_state_addresses,
        )
        grouped.setdefault((consequence, next_state), []).append(episode.episode_id)

    patterns: list[StructuralConsequencePattern] = []
    for (consequence, next_state), ids in grouped.items():
        independent = tuple(sorted(set(ids)))
        if len(independent) < min_independent_episodes:
            continue
        patterns.append(
            StructuralConsequencePattern(
                consequence_pattern=consequence,
                next_state_pattern=next_state,
                supporting_episode_ids=independent,
            )
        )

    patterns.sort(
        key=lambda item: (
            item.consequence_pattern,
            item.next_state_pattern,
            item.supporting_episode_ids,
        )
    )
    visible = tuple(patterns)
    if not visible:
        reason = "insufficient-structural-support"
    elif len(visible) == 1:
        reason = "single-supported-structural-consequence"
    else:
        reason = "competing-supported-structural-consequences"

    return StructuralInterventionResolution(
        query_key=key,
        patterns=visible,
        resolved=len(visible) == 1,
        ambiguous=len(visible) > 1,
        reason=reason,
    )
