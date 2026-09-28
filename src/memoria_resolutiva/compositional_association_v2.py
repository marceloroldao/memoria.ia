"""Rebuildable associations among discovered structural compositions.

Every scale uses the same positional and event-order kernels. A composition
found later is projected onto earlier unique observations during rebuilding;
neither the original payload graph nor its observation order is changed.
"""
from __future__ import annotations

from dataclasses import dataclass
from math import exp
from typing import Iterable

from .hierarchical_composition_v2 import (
    HierarchyLevelV2, ScaleAddress, _composition_address,
)
from .structural_association_continuous import ContinuousStructuralAssociationField


@dataclass(frozen=True, slots=True)
class CompositionObservation:
    payload_id: str
    stream_id: str
    symbols: tuple[int, ...]


@dataclass(frozen=True, slots=True)
class _Occurrence:
    address: str
    start: int
    end: int


@dataclass(frozen=True, slots=True)
class _ProjectedEvent:
    payload_id: str
    occurrences: tuple[_Occurrence, ...]


@dataclass(frozen=True, slots=True)
class AssociatedNodule:
    address: str
    symbols: tuple[int, ...]
    weight: float
    cue_addresses: tuple[str, ...]
    # Within: the same payload on both sides. Temporal: earlier -> later.
    witnesses: tuple[tuple[str, str, str], ...]  # source, target, stream

    @property
    def rank_score(self) -> float:
        # A longer recurrent route carries more positional structure. This is
        # an uncalibrated specificity prior, never a truth probability.
        return self.weight * len(self.symbols)


@dataclass(frozen=True, slots=True)
class CompositionalRecall:
    channel: str
    depth: int
    cues: tuple[str, ...]
    candidates: tuple[AssociatedNodule, ...]
    ambiguous: bool
    truncated: bool
    total_rank_score: float = 0.0

    @property
    def selected(self) -> tuple[int, ...] | None:
        if len(self.candidates) == 1 and not self.truncated:
            return self.candidates[0].symbols
        return None


@dataclass(frozen=True, slots=True)
class WitnessedNodulePath:
    # The query is the starting cue; these are its successive evoked nodules.
    nodules: tuple[tuple[int, ...], ...]
    # Capture ID and the exact ordered input payload IDs at each hop.
    witnesses: tuple[tuple[str, tuple[str, ...]], ...]

    @property
    def supporting_streams(self) -> tuple[str, ...]:
        return tuple(sorted({stream for stream, _ in self.witnesses}))


@dataclass(frozen=True, slots=True)
class NodulePathTrace:
    first_hop: CompositionalRecall
    paths: tuple[WitnessedNodulePath, ...]
    truncated: bool


class CompositionalAssociationView:
    """Read-only projection derived from a hierarchy and unique input events."""

    def __init__(
        self,
        levels: tuple[HierarchyLevelV2, ...],
        observations: Iterable[CompositionObservation],
        *,
        within_decay: float,
        temporal_decay: float,
        forgetting_rate: float,
        trace_floor: float,
        max_pattern_size: int,
    ) -> None:
        self._patterns: dict[int, dict[str, tuple[int, ...]]] = {}
        self._identifiers: dict[int, dict[str, int]] = {}
        self._fields: dict[int, ContinuousStructuralAssociationField] = {}
        self._streams: dict[int, set[str]] = {}
        self._witnesses: dict[
            tuple[int, str, str, str], set[tuple[str, str, str]]
        ] = {}
        events = tuple(observations)
        if type(max_pattern_size) is not int or max_pattern_size < 1:
            raise ValueError("max_pattern_size must be a positive integer")
        # The greedy trajectory view is useful for generation, but its packing
        # boundaries can differ when a recurring phrase has different
        # surroundings. Recurrent raw spans remain eligible as nodules here.
        # No language-dependent segmentation, labels, or manual links.
        recurrent: dict[tuple[int, ...], set[str]] = {}
        for event in events:
            for width in range(2, min(len(event.symbols), max_pattern_size) + 1):
                for start in range(len(event.symbols) - width + 1):
                    pattern = event.symbols[start:start + width]
                    recurrent.setdefault(pattern, set()).add(event.payload_id)
        raw_patterns = {
            pattern for pattern, roots in recurrent.items() if len(roots) >= 2
        }
        catalogue: dict[str, tuple[ScaleAddress, ...]] = {}
        expanded: dict[str, tuple[int, ...]] = {}

        def expand(address: ScaleAddress) -> tuple[int, ...]:
            if type(address) is int:
                return (address,)
            if address not in expanded:
                result = tuple(symbol for child in catalogue[address] for symbol in expand(child))
                expanded[address] = result
            return expanded[address]

        for level in levels:
            catalogue.update({item.address: item.children for item in level.compositions})
            patterns = {item.address: expand(item.address) for item in level.compositions}
            if level.depth == 1:
                for pattern in raw_patterns:
                    address = _composition_address(
                        hierarchy_id=level.hierarchy_id, depth=1, children=pattern,
                    )
                    previous = patterns.get(address)
                    if previous is not None and previous != pattern:
                        raise ValueError("recurrent composition address collision")
                    patterns[address] = pattern
            if not patterns:
                continue
            identifiers = {address: index for index, address in enumerate(sorted(patterns))}
            field = ContinuousStructuralAssociationField(
                within_decay=within_decay, temporal_decay=temporal_decay,
                forgetting_rate=forgetting_rate, trace_floor=trace_floor,
            )
            self._patterns[level.depth] = patterns
            self._identifiers[level.depth] = identifiers
            self._fields[level.depth] = field
            self._streams[level.depth] = set()
            by_stream: dict[str, list[_ProjectedEvent]] = {}

            for event in events:
                occurrences = self._project(event.symbols, patterns)
                scope = event.stream_id
                self._streams[level.depth].add(scope)
                envelope = {
                    "observation_id": event.payload_id,
                    "semantic_projection": False,
                    "event": {"trail": tuple(identifiers[item.address] for item in occurrences)},
                    "provenance": {"hierarchy_id": scope},
                }
                field.observe(
                    envelope, spans=tuple((item.start, item.end) for item in occurrences),
                )
                prior_events = by_stream.setdefault(scope, [])
                self._record_witnesses(
                    level.depth, scope, event.payload_id, occurrences,
                    prior_events, field,
                )
                prior_events.append(_ProjectedEvent(event.payload_id, occurrences))

    @staticmethod
    def _project(
        symbols: tuple[int, ...], patterns: dict[str, tuple[int, ...]],
    ) -> tuple[_Occurrence, ...]:
        # All exact spans remain visible even when greedy packing selected a
        # larger overlapping nodule in another trajectory view.
        occurrences = (
            _Occurrence(address, start, start + len(pattern))
            for address, pattern in patterns.items()
            for start in range(len(symbols) - len(pattern) + 1)
            if symbols[start:start + len(pattern)] == pattern
        )
        return tuple(sorted(occurrences, key=lambda item: (item.start, item.end, item.address)))

    def _record_witnesses(
        self,
        depth: int,
        stream: str,
        current_payload: str,
        occurrences: tuple[_Occurrence, ...],
        previous: list[_ProjectedEvent],
        field: ContinuousStructuralAssociationField,
    ) -> None:
        for index, source in enumerate(occurrences):
            for target in occurrences[index + 1:]:
                gap = target.start - source.end
                if gap < 0:
                    continue
                if gap >= field.within_horizon:
                    break
                if exp(-field.within_decay * gap) < field.trace_floor:
                    continue
                key = (depth, source.address, target.address, "within")
                self._witnesses.setdefault(key, set()).add(
                    (current_payload, current_payload, stream)
                )
        if not occurrences:
            return
        for lag, past in enumerate(reversed(previous), start=1):
            if lag > field.temporal_horizon:
                break
            if exp(-field.temporal_decay * (lag - 1)) < field.trace_floor:
                continue
            for source in past.occurrences:
                for target in occurrences:
                    key = (depth, source.address, target.address, "temporal")
                    self._witnesses.setdefault(key, set()).add(
                        (past.payload_id, current_payload, stream)
                    )

    def recall(
        self, query: tuple[int, ...], *, channel: str = "temporal", limit: int = 8,
    ) -> CompositionalRecall:
        if channel not in ContinuousStructuralAssociationField.CHANNELS:
            raise ValueError("channel must be 'within' or 'temporal'")
        if type(limit) is not int or limit < 1:
            raise ValueError("limit must be a positive integer")
        if not query or any(type(symbol) is not int or symbol < 0 for symbol in query):
            raise ValueError("query must contain non-negative symbol addresses")
        matched = [
            (len(pattern), depth, address)
            for depth, patterns in self._patterns.items()
            for address, pattern in patterns.items()
            if len(pattern) <= len(query)
            and any(
                query[start:start + len(pattern)] == pattern
                for start in range(len(query) - len(pattern) + 1)
            )
        ]
        if not matched:
            return CompositionalRecall(channel, 0, (), (), False, False)
        empty: CompositionalRecall | None = None
        for size in sorted({width for width, _, _ in matched}, reverse=True):
            by_depth: dict[int, tuple[str, ...]] = {
                depth: tuple(sorted(address for width, level, address in matched
                                    if width == size and level == depth))
                for depth in sorted({level for width, level, _ in matched if width == size})
            }
            cues_at_width = tuple(address for cues in by_depth.values() for address in cues)
            if empty is None:
                empty = CompositionalRecall(channel, max(by_depth), cues_at_width,
                                            (), False, False)
            # A cue can be represented at several depths. Keep each target
            # once, and only fall back to a shorter cue if this entire width
            # has no outgoing candidate. A longer repeated wrapper with no
            # successor must not erase a previously witnessed shorter route.
            representatives: dict[tuple[int, ...], tuple[int, AssociatedNodule]] = {}
            for depth, cues in by_depth.items():
                for candidate in self._recall_depth(depth, cues, channel):
                    prior = representatives.get(candidate.symbols)
                    if prior is None or (candidate.weight, depth) > (prior[1].weight, prior[0]):
                        representatives[candidate.symbols] = depth, candidate
            candidates = tuple(
                candidate for _, candidate in representatives.values()
                if not self._contained(candidate.symbols, query)
            )
            candidates = tuple(
                candidate for candidate in candidates
                if not any(
                    len(other.symbols) > len(candidate.symbols)
                    and self._contained(candidate.symbols, other.symbols)
                    and candidate.witnesses == other.witnesses
                    and other.weight >= candidate.weight
                    for other in candidates
                )
            )
            if candidates:
                candidates = tuple(sorted(
                    candidates, key=lambda item: (-item.rank_score, -item.weight, item.address),
                ))
                return CompositionalRecall(
                    channel, max(by_depth), cues_at_width,
                    candidates[:limit], len(candidates) > 1, len(candidates) > limit,
                    sum(candidate.rank_score for candidate in candidates),
                )
        assert empty is not None
        return empty

    def _recall_depth(
        self, depth: int, cues: tuple[str, ...], channel: str,
    ) -> tuple[AssociatedNodule, ...]:
        field = self._fields[depth]
        identifiers = self._identifiers[depth]
        reverse = {value: address for address, value in identifiers.items()}
        scores: dict[str, float] = {}
        sources: dict[str, set[str]] = {}
        for cue in cues:
            for scope in sorted(self._streams[depth]):
                for edge in field.strongest(
                    scope, identifiers[cue], channel=channel,
                    top_k=max(1, len(identifiers)),
                ):
                    if edge.weight < field.trace_floor:
                        continue
                    target = reverse[edge.target]
                    if target in cues:
                        continue
                    scores[target] = scores.get(target, 0.0) + edge.weight / len(cues)
                    sources.setdefault(target, set()).add(cue)
        cue_patterns = tuple(self._patterns[depth][cue] for cue in cues)
        candidates = tuple(
            AssociatedNodule(
                address=address, symbols=self._patterns[depth][address],
                weight=weight, cue_addresses=tuple(sorted(sources[address])),
                witnesses=tuple(sorted(set().union(*(
                    self._witnesses.get((depth, cue, address, channel), set())
                    for cue in sources[address]
                )))),
            )
            for address, weight in sorted(scores.items(), key=lambda item: (-item[1], item[0]))
            if not any(
                self._contained(self._patterns[depth][address], pattern)
                for pattern in cue_patterns
            )
        )
        return candidates

    def trace_paths(
        self, query: tuple[int, ...], *, max_hops: int = 2, limit: int = 8,
    ) -> NodulePathTrace:
        """Join observed edges through the same middle payload and capture.

        This is a structural route trace, not an answer selector. It does not
        multiply edge weights or infer a link across two separate captures.
        """
        if type(max_hops) is not int or max_hops not in (1, 2):
            raise ValueError("max_hops must be 1 or 2")
        first = self.recall(query, channel="temporal", limit=limit)
        routes: dict[
            tuple[tuple[int, ...], ...], set[tuple[str, tuple[str, ...]]]
        ] = {}
        truncated = first.truncated
        for candidate in first.candidates:
            chains = {
                (stream, (source, target))
                for source, target, stream in candidate.witnesses
                if source != target
            }
            if not chains:
                continue
            routes.setdefault((candidate.symbols,), set()).update(chains)
            if max_hops == 1:
                continue
            next_hop = self.recall(candidate.symbols, channel="temporal", limit=limit)
            truncated |= next_hop.truncated
            for following in next_hop.candidates:
                if following.symbols == candidate.symbols:
                    continue
                joined = {
                    (stream, payloads + (target,))
                    for stream, payloads in chains
                    for source, target, edge_stream in following.witnesses
                    if edge_stream == stream and source == payloads[-1]
                    and target not in payloads
                }
                if joined:
                    routes.setdefault(
                        (candidate.symbols, following.symbols), set()
                    ).update(joined)
        paths = tuple(
            WitnessedNodulePath(nodules, tuple(sorted(chains)))
            for nodules, chains in routes.items()
        )
        paths = tuple(sorted(
            paths,
            key=lambda path: (-len(path.supporting_streams),
                              -len(path.witnesses), len(path.nodules), path.nodules),
        ))
        return NodulePathTrace(first, paths[:limit], truncated or len(paths) > limit)

    @staticmethod
    def _contained(part: tuple[int, ...], whole: tuple[int, ...]) -> bool:
        return any(
            whole[start:start + len(part)] == part
            for start in range(len(whole) - len(part) + 1)
        )
