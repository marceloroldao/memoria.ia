"""Rebuildable associations among discovered structural compositions.

Every scale uses the same positional and event-order kernels. A composition
found later is projected onto earlier observations during rebuilding. Content
is counted once; later occurrences can create previously unseen ordered pairs.
"""
from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, field, replace
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
    profile: tuple[tuple[str, float], ...]


@dataclass(frozen=True, slots=True)
class AssociatedNodule:
    address: str
    symbols: tuple[int, ...]
    weight: float
    cue_addresses: tuple[str, ...]
    # Within: the same payload on both sides. Temporal: earlier -> later.
    witnesses: tuple[tuple[str, str, str], ...]  # source, target, stream
    source_width: int = 0  # Atomic span of the primary cue, not target length.
    # Non-voting occurrence provenance is available for path joins, but does
    # not change the equality of a recall result or its structural support.
    occurrence_witnesses: tuple[tuple[str, str, str, int, int], ...] = field(
        default=(), compare=False, repr=False,
    )

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
    """Derived projection; reads are pure, known occurrences can be appended."""

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
        self._occurrence_witnesses: dict[
            tuple[int, str, str, str], set[tuple[str, str, str, int, int]]
        ] = {}
        self._temporal_votes: dict[
            tuple[int, str, str], dict[str, list[tuple[float, int]]]
        ] = {}
        self._ticks: dict[tuple[int, str], int] = {}
        events = tuple(observations)
        self._known_payloads = {event.payload_id: event.symbols for event in events}
        self._histories: dict[int, dict[str, list[_ProjectedEvent]]] = {}
        self._seen_content: dict[int, set[str]] = {}
        self._seen_pairs: dict[int, set[tuple[str, str]]] = {}
        self._projected_events: dict[tuple[int, str], _ProjectedEvent] = {}
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
            self._histories[level.depth] = {}
            self._seen_content[level.depth] = set()
            self._seen_pairs[level.depth] = set()

            for event in events:
                self._append_event(level.depth, event)

    def append_known_occurrence(self, event: CompositionObservation) -> None:
        """Update only occurrence order under this projection's fixed catalogue.

        New content requires a full rebuild, including retrospective discovery.
        The owner handles observation-ID idempotence before calling this method.
        """
        if self._known_payloads.get(event.payload_id) != event.symbols:
            raise ValueError("incremental occurrence requires unchanged known content")
        for depth in self._patterns:
            self._append_event(depth, event)

    def _append_event(self, depth: int, event: CompositionObservation) -> None:
        field = self._fields[depth]
        identifiers = self._identifiers[depth]
        key = depth, event.payload_id
        projected = self._projected_events.get(key)
        if projected is None:
            occurrences = self._project(event.symbols, self._patterns[depth])
            projected = _ProjectedEvent(event.payload_id, occurrences, self._profile(occurrences))
            self._projected_events[key] = projected
        occurrences = projected.occurrences
        scope = event.stream_id
        self._streams[depth].add(scope)
        prior_events = self._histories[depth].setdefault(scope, [])
        tick = self._ticks.get((depth, scope), 0) + 1
        self._ticks[(depth, scope)] = tick
        if event.payload_id not in self._seen_content[depth]:
            self._seen_content[depth].add(event.payload_id)
            envelope = {
                "observation_id": event.payload_id,
                "semantic_projection": False,
                "event": {"trail": tuple(identifiers[item.address] for item in occurrences)},
                "provenance": {"hierarchy_id": scope},
            }
            field.observe(envelope, spans=tuple((item.start, item.end) for item in occurrences))
            self._record_within_witnesses(depth, scope, event.payload_id, occurrences, field)
        self._record_temporal_pairs(
            depth, scope, projected, prior_events, field, self._seen_pairs[depth], tick,
        )
        prior_events.append(projected)
        # Absolute occurrence ticks preserve witness identity after pruning.
        if len(prior_events) > field.temporal_horizon:
            del prior_events[:-field.temporal_horizon]

    @staticmethod
    def _profile(occurrences: tuple[_Occurrence, ...]) -> tuple[tuple[str, float], ...]:
        if not occurrences:
            return ()
        counts = Counter(item.address for item in occurrences)
        return tuple(sorted((address, count / len(occurrences))
                            for address, count in counts.items()))

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

    def _record_within_witnesses(
        self,
        depth: int,
        stream: str,
        current_payload: str,
        occurrences: tuple[_Occurrence, ...],
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

    def _record_temporal_pairs(
        self, depth: int, stream: str, current: _ProjectedEvent,
        previous: list[_ProjectedEvent], field: ContinuousStructuralAssociationField,
        seen_pairs: set[tuple[str, str]], tick: int,
    ) -> None:
        for lag, past in enumerate(reversed(previous[-field.temporal_horizon:]), start=1):
            kernel = exp(-field.temporal_decay * (lag - 1))
            if kernel < field.trace_floor:
                break
            pair = past.payload_id, current.payload_id
            if pair[0] == pair[1]:
                continue
            new_pair = pair not in seen_pairs
            if new_pair:
                seen_pairs.add(pair)
            for source, source_mass in past.profile:
                for target, target_mass in current.profile:
                    key = (depth, source, target, "temporal")
                    self._occurrence_witnesses.setdefault(key, set()).add(
                        (pair[0], pair[1], stream, tick - lag, tick)
                    )
                    if not new_pair:
                        continue
                    weight = kernel * source_mass * target_mass
                    self._temporal_votes.setdefault(
                        (depth, stream, source), {},
                    ).setdefault(target, []).append((weight, tick))
                    self._witnesses.setdefault(key, set()).add((pair[0], pair[1], stream))

    def recall(
        self, query: tuple[int, ...], *, channel: str = "temporal", limit: int = 8,
        include_shorter: bool = False,
    ) -> CompositionalRecall:
        if channel not in ContinuousStructuralAssociationField.CHANNELS:
            raise ValueError("channel must be 'within' or 'temporal'")
        if type(limit) is not int or limit < 1:
            raise ValueError("limit must be a positive integer")
        if type(include_shorter) is not bool:
            raise ValueError("include_shorter must be a boolean")
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
        # Keep one displayed weight per destination. A shorter cue may supply
        # another witness, but cannot multiply support already attributed to
        # a more specific cue for the same destination.
        routes: dict[tuple[int, ...], tuple[int, int, AssociatedNodule]] = {}
        activated_cues: list[str] = []
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
            # once per width; a shorter witnessed cue remains an alternative
            # even when a longer cue already has a different destination.
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
                activated_cues.extend(cues_at_width)
                for candidate in candidates:
                    previous = routes.get(candidate.symbols)
                    if previous is None:
                        routes[candidate.symbols] = (
                            size, max(by_depth), replace(candidate, source_width=size),
                        )
                    else:
                        width, depth, primary = previous
                        routes[candidate.symbols] = (width, depth, replace(
                            primary,
                            cue_addresses=tuple(sorted(set(primary.cue_addresses) |
                                                       set(candidate.cue_addresses))),
                            witnesses=tuple(sorted(set(primary.witnesses) |
                                                   set(candidate.witnesses))),
                            occurrence_witnesses=tuple(sorted(
                                set(primary.occurrence_witnesses) |
                                set(candidate.occurrence_witnesses)
                            )),
                        ))
                if not include_shorter:
                    break
        if routes:
            # A target fragment with the same witness set and no greater
            # support than its enclosing target is a second view of one route.
            available = tuple(routes.values())
            survivors = tuple(
                row for row in available
                if not any(
                    other_width >= row[0]
                    and len(other.symbols) > len(row[2].symbols)
                    and self._contained(row[2].symbols, other.symbols)
                    and row[2].witnesses == other.witnesses
                    and other.weight >= row[2].weight
                    for other_width, _, other in available
                )
            )
            survivors = tuple(sorted(
                survivors, key=lambda row: (-row[0], -row[2].rank_score,
                                            -row[2].weight, row[2].address),
            ))
            return CompositionalRecall(
                channel, max(depth for _, depth, _ in survivors),
                tuple(dict.fromkeys(activated_cues)),
                tuple(candidate for _, _, candidate in survivors[:limit]),
                len(survivors) > 1, len(survivors) > limit,
                sum(candidate.rank_score for _, _, candidate in survivors),
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
                if channel == "within":
                    edges = (
                        (reverse[edge.target], edge.weight)
                        for edge in field.strongest(
                            scope, identifiers[cue], channel=channel,
                            top_k=max(1, len(identifiers)),
                        )
                    )
                else:
                    now = self._ticks[(depth, scope)]
                    edges = (
                        (target, sum(weight * exp(-field.forgetting_rate * (now - tick))
                                     for weight, tick in votes))
                        for target, votes in self._temporal_votes.get(
                            (depth, scope, cue), {},
                        ).items()
                    )
                for target, weight in edges:
                    if weight < field.trace_floor:
                        continue
                    if target in cues:
                        continue
                    scores[target] = scores.get(target, 0.0) + weight / len(cues)
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
                occurrence_witnesses=tuple(sorted(set().union(*(
                    self._occurrence_witnesses.get((depth, cue, address, channel), set())
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
                (stream, (source, target), target_tick)
                for source, target, stream, _source_tick, target_tick
                in candidate.occurrence_witnesses
                if source != target
            }
            if not chains:
                continue
            routes.setdefault((candidate.symbols,), set()).update(
                (stream, payloads) for stream, payloads, _tick in chains
            )
            if max_hops == 1:
                continue
            next_hop = self.recall(candidate.symbols, channel="temporal", limit=limit)
            truncated |= next_hop.truncated
            for following in next_hop.candidates:
                if following.symbols == candidate.symbols:
                    continue
                joined = {
                    (stream, payloads + (target,))
                    for stream, payloads, middle_tick in chains
                    for source, target, edge_stream, source_tick, _target_tick
                    in following.occurrence_witnesses
                    if edge_stream == stream and source == payloads[-1]
                    and source_tick == middle_tick
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
