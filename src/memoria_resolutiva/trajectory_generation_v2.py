"""Experimental online generation over reusable opaque trajectories.

This is a generative hypothesis layer, separate from occurrence-local recall.
No semantic labels, manual reply links, language model, or truth promotion.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
from hashlib import blake2b
import json
from math import isclose, isfinite, log
from typing import Iterable

from .compositional_association_v2 import (
    CompositionObservation,
    CompositionalAssociationView,
    CompositionalRecall,
    NodulePathTrace,
)
from .hierarchical_composition_v2 import (
    HierarchicalCompositionEngineV2,
    HierarchyLevelV2,
    ScaleAddress,
)
from .structural_association_continuous import ContinuousStructuralAssociationField
from .structural_state_persistence import (
    ContentAddressedStatePersistence,
    StateSnapshotReceipt,
)
from .structural_trajectory_v2 import StructuralTrajectoryIndex


SCHEMA = "memoria.ia-trajectory-generation-experiment-v1"


def _encoded(value: object) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()


def _digest(value: object) -> str:
    return blake2b(_encoded(value), digest_size=20).hexdigest()


def _name(value: str) -> str:
    if not isinstance(value, str) or not value or value.strip() != value:
        raise ValueError("identifiers must be non-empty strings without outer whitespace")
    return value


def _symbols(values: Iterable[int]) -> tuple[int, ...]:
    result = tuple(values)
    if not result or any(type(item) is not int or item < 0 for item in result):
        raise ValueError("payload must contain non-negative integer symbol addresses")
    return result


def _payload_id(symbols: tuple[int, ...]) -> str:
    return "payload:" + _digest(symbols)


@dataclass(frozen=True, slots=True)
class GenerationConfig:
    min_context: int = 2
    max_context: int = 32
    max_depth: int = 3
    max_composition_size: int = 3
    within_decay: float = 0.35
    temporal_decay: float = 0.35
    forgetting_rate: float = 0.0
    trace_floor: float = 1e-6

    def __post_init__(self) -> None:
        for name in ("min_context", "max_context", "max_depth", "max_composition_size"):
            value = getattr(self, name)
            minimum = 2 if name == "max_composition_size" else 1
            if type(value) is not int or value < minimum:
                raise ValueError(f"invalid {name}")
        if self.min_context > self.max_context:
            raise ValueError("min_context cannot exceed max_context")
        for name in ("within_decay", "temporal_decay", "forgetting_rate", "trace_floor"):
            if not isfinite(getattr(self, name)):
                raise ValueError(f"{name} must be finite")
        if self.within_decay <= 0 or self.temporal_decay <= 0 or self.forgetting_rate < 0:
            raise ValueError("invalid association decay")
        if not 0 < self.trace_floor < 1:
            raise ValueError("trace_floor must be in (0, 1)")


@dataclass(frozen=True, slots=True)
class ObservationReceipt:
    payload_id: str
    learned: bool
    replayed: bool


@dataclass(frozen=True, slots=True)
class RouteStep:
    context: tuple[ScaleAddress, ...]
    next_address: ScaleAddress | None  # None is an observed end, not a symbol.
    supporting_payloads: tuple[str, ...]
    relative_support: float


@dataclass(frozen=True, slots=True)
class GenerationCandidate:
    output: tuple[int, ...]
    continuation: tuple[int, ...]
    log_score: float
    stop_reason: str
    steps: tuple[RouteStep, ...]


@dataclass(frozen=True, slots=True)
class TemporalNeighbor:
    payload_id: str
    symbols: tuple[int, ...]
    weight: float
    streams: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class EmbeddedRootLink:
    cue_payload_id: str
    target_payload_id: str
    weight: float
    streams: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class EmbeddedRootRecall:
    cue_payload_ids: tuple[str, ...]
    links: tuple[EmbeddedRootLink, ...]
    neighbors: tuple[TemporalNeighbor, ...]
    ambiguous: bool
    truncated: bool


@dataclass(frozen=True, slots=True)
class RouteStabilityCandidate:
    symbols: tuple[int, ...]
    weight: float
    weight_share: float
    rank_share: float
    witness_pairs: int
    independent_streams: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class RouteStability:
    candidates: tuple[RouteStabilityCandidate, ...]
    ambiguous: bool
    truncated: bool

    @property
    def strongest(self) -> tuple[int, ...] | None:
        """Unique highest structural rank, without asserting truth."""
        if not self.candidates or self.truncated:
            return None
        first = self.candidates[0]
        if len(self.candidates) > 1 and isclose(
            first.rank_share, self.candidates[1].rank_share,
        ):
            return None
        return first.symbols

    @property
    def cross_stream_strongest(self) -> tuple[int, ...] | None:
        """Unique strongest route witnessed in at least two captures."""
        strongest = self.strongest
        if strongest is None or len(self.candidates[0].independent_streams) < 2:
            return None
        return strongest


@dataclass(frozen=True, slots=True)
class GenerationResult:
    mode: str  # Operation label, including COMBINED_RECALL and COMBINED_ROUTES.
    candidates: tuple[GenerationCandidate, ...]
    ambiguous: bool
    truncated: bool
    scale: int
    temporal_evidence: tuple[TemporalNeighbor, ...] = ()
    association_evidence: CompositionalRecall | None = None
    embedded_evidence: EmbeddedRootRecall | None = None

    @property
    def selected(self) -> tuple[int, ...] | None:
        if len(self.candidates) == 1 and not self.ambiguous and not self.truncated:
            return self.candidates[0].output
        return None


class TrajectoryGenerationExperiment:
    """Small inspectable experiment, not the native/mobile response runtime.

    The durable graph stores each payload once as atoms/references to existing
    payloads. Occurrences only reference roots. Derived indexes/fields can be
    rebuilt by replay. Learning support is unique content per hierarchy; an
    identical payload, even from another stream, supplies no second vote.
    """

    def __init__(self, config: GenerationConfig | None = None) -> None:
        self.config = config or GenerationConfig()
        self._nodes: dict[str, tuple[ScaleAddress, ...]] = {}
        self._observations: dict[str, dict[str, str]] = {}
        self._learned: set[tuple[str, str]] = set()
        self._index = StructuralTrajectoryIndex(preserve_repetitions=True)
        self._hierarchy = HierarchicalCompositionEngineV2(
            self._index, max_depth=self.config.max_depth,
            max_size=self.config.max_composition_size,
        )
        field_options = dict(
            within_decay=self.config.within_decay,
            temporal_decay=self.config.temporal_decay,
            forgetting_rate=self.config.forgetting_rate,
            trace_floor=self.config.trace_floor,
        )
        self._symbol_field = ContinuousStructuralAssociationField(**field_options)
        self._root_field = ContinuousStructuralAssociationField(**field_options)
        self._streams: dict[tuple[str, str], str] = {}
        self._roots: dict[int, str] = {}

    def expand(self, address: ScaleAddress) -> tuple[int, ...]:
        """Lossless expansion of a stored root, including repeated symbols."""
        output: list[int] = []
        pending: list[ScaleAddress] = [address]
        while pending:
            item = pending.pop()
            if type(item) is int:
                output.append(item)
            else:
                pending.extend(reversed(self._nodes[item]))
        return tuple(output)

    def _intern(self, symbols: tuple[int, ...]) -> str:
        address = _payload_id(symbols)
        if address in self._nodes:
            if self.expand(address) != symbols:
                raise ValueError("payload address collision")
            return address
        catalogue = sorted(
            ((key, self.expand(key)) for key in self._nodes),
            key=lambda item: (-len(item[1]), item[0]),
        )
        children: list[ScaleAddress] = []
        cursor = 0
        while cursor < len(symbols):
            for key, pattern in catalogue:
                if symbols[cursor:cursor + len(pattern)] == pattern:
                    children.append(key)
                    cursor += len(pattern)
                    break
            else:
                children.append(symbols[cursor])
                cursor += 1
        self._nodes[address] = tuple(children)
        return address

    def observe(
        self, payload: Iterable[int], *, observation_id: str,
        hierarchy_id: str = "default", stream_id: str = "default",
    ) -> ObservationReceipt:
        symbols = _symbols(payload)
        observation = _name(observation_id)
        hierarchy = _name(hierarchy_id)
        stream = _name(stream_id)
        address = _payload_id(symbols)
        row = dict(payload_id=address, hierarchy_id=hierarchy, stream_id=stream)
        previous = self._observations.get(observation)
        if previous is not None:
            if previous != row or self.expand(address) != symbols:
                raise ValueError("observation identity reused with different content or scope")
            return ObservationReceipt(address, learned=False, replayed=True)

        root_symbol = int(address.removeprefix("payload:"), 16)
        if root_symbol in self._roots and self._roots[root_symbol] != address:
            raise ValueError("root symbol collision")
        address = self._intern(symbols)
        self._observations[observation] = row
        if (hierarchy, address) in self._learned:
            return ObservationReceipt(address, learned=False, replayed=False)

        # Capture boundaries are provenance, not manually authored relations.
        field_scope = "stream:" + _digest([hierarchy, stream])
        self._streams[(hierarchy, stream)] = field_scope
        event_id = "content:" + _digest([hierarchy, address])
        envelope = dict(
            observation_id=event_id, semantic_projection=False,
            event={"trail": symbols}, provenance={"hierarchy_id": field_scope},
        )
        self._symbol_field.observe(envelope)
        self._root_field.observe({**envelope, "event": {"trail": (root_symbol,)}})
        self._roots[root_symbol] = address
        self._index.ingest_addresses(
            symbols, hierarchy_id=hierarchy, source_id=address,
            sequence=0, observation_id=event_id,
        )
        self._learned.add((hierarchy, address))
        return ObservationReceipt(address, learned=True, replayed=False)

    def levels(self, *, hierarchy_id: str = "default") -> tuple[HierarchyLevelV2, ...]:
        return self._hierarchy.build(hierarchy_id=_name(hierarchy_id))

    def association(
        self, source: int, target: int, *, hierarchy_id: str = "default",
        channel: str = "within",
    ) -> float:
        hierarchy = _name(hierarchy_id)
        _symbols((source, target))
        if channel not in {"within", "temporal"}:
            raise ValueError("unknown association channel")
        return sum(
            self._symbol_field.association(scope, source, target, channel=channel)
            for (hid, _stream), scope in self._streams.items() if hid == hierarchy
        )

    def temporal_neighbors(
        self, payload: Iterable[int], *, hierarchy_id: str = "default",
    ) -> tuple[TemporalNeighbor, ...]:
        hierarchy = _name(hierarchy_id)
        address = _payload_id(_symbols(payload))
        if (hierarchy, address) not in self._learned:
            return ()
        symbol = int(address.removeprefix("payload:"), 16)
        weights: dict[str, float] = {}
        streams: dict[str, set[str]] = {}
        for (hid, stream), scope in self._streams.items():
            if hid != hierarchy:
                continue
            for edge in self._root_field.strongest(
                scope, symbol, channel="temporal", top_k=max(1, len(self._roots)),
            ):
                if edge.weight < self.config.trace_floor:
                    continue
                target = self._roots[edge.target]
                weights[target] = weights.get(target, 0.0) + edge.weight
                streams.setdefault(target, set()).add(stream)
        return tuple(
            TemporalNeighbor(target, self.expand(target), weight, tuple(sorted(streams[target])))
            for target, weight in sorted(weights.items(), key=lambda item: (-item[1], item[0]))
        )

    def embedded_root_relations(
        self, payload: Iterable[int], *, hierarchy_id: str = "default",
        limit: int = 8,
    ) -> EmbeddedRootRecall:
        """Evoked whole-payload roots contained in a new input, read-only.

        One observed root is already a nodule. Exact copies cannot add votes;
        only roots of the longest matching width activate temporal neighbors.
        """
        query = _symbols(payload)
        hierarchy = _name(hierarchy_id)
        if type(limit) is not int or limit < 1:
            raise ValueError("limit must be a positive integer")
        matches = []
        for hid, address in self._learned:
            if hid != hierarchy:
                continue
            pattern = self.expand(address)
            if not self.config.min_context <= len(pattern) < len(query):
                continue
            if any(query[start:start + len(pattern)] == pattern
                   for start in range(len(query) - len(pattern) + 1)):
                matches.append((len(pattern), address, pattern))
        if not matches:
            return EmbeddedRootRecall((), (), (), False, False)
        longest = max(size for size, _, _ in matches)
        cues = sorted((address, pattern) for size, address, pattern in matches
                      if size == longest)
        truncated = len(cues) > limit
        active = cues[:limit]
        links: list[EmbeddedRootLink] = []
        weights: dict[str, float] = {}
        streams: dict[str, set[str]] = {}
        for address, pattern in active:
            for neighbor in self.temporal_neighbors(pattern, hierarchy_id=hierarchy):
                links.append(EmbeddedRootLink(
                    address, neighbor.payload_id, neighbor.weight, neighbor.streams,
                ))
                weights[neighbor.payload_id] = (
                    weights.get(neighbor.payload_id, 0.0) + neighbor.weight / len(active)
                )
                streams.setdefault(neighbor.payload_id, set()).update(neighbor.streams)
        targets = tuple(
            TemporalNeighbor(address, self.expand(address), weight,
                             tuple(sorted(streams[address])))
            for address, weight in sorted(weights.items(), key=lambda item: (-item[1], item[0]))
        )
        return EmbeddedRootRecall(
            tuple(address for address, _ in active), tuple(links), targets[:limit],
            len(cues) > 1 or len(targets) > 1,
            truncated or len(targets) > limit,
        )

    def associated_nodules(
        self, payload: Iterable[int], *, hierarchy_id: str = "default",
        channel: str = "temporal", limit: int = 8,
    ) -> CompositionalRecall:
        """Rebuild associations at every discovered scale without learning.

        A newly discovered composition is projected over earlier unique input
        events. Each event contributes once in its original stream and order.
        The longest recurring cue activates all scales representing it;
        identical targets are not reinforced merely by appearing at several
        depths, and independent shorter targets remain visible.
        """
        query = _symbols(payload)
        hierarchy = _name(hierarchy_id)
        return self._compositional_view(hierarchy).recall(
            query, channel=channel, limit=limit,
        )

    def route_stability(
        self, payload: Iterable[int], *, hierarchy_id: str = "default",
        limit: int = 8,
    ) -> RouteStability:
        """Measure recurrent temporal routes without promoting one to fact.

        Each witness is an ordered pair of distinct payload roots in one
        capture. Exact payload copies never enter the derived learning view.
        Rank shares are relative structural evidence, not probabilities.
        """
        recall = self.associated_nodules(
            payload, hierarchy_id=hierarchy_id, channel="temporal", limit=limit,
        )
        total_weight = sum(candidate.weight for candidate in recall.candidates)
        candidates = tuple(
            RouteStabilityCandidate(
                candidate.symbols, candidate.weight,
                candidate.weight / total_weight,
                candidate.rank_score / recall.total_rank_score,
                len(candidate.witnesses),
                tuple(sorted({stream for _, _, stream in candidate.witnesses})),
            )
            for candidate in recall.candidates
        )
        return RouteStability(candidates, recall.ambiguous, recall.truncated)

    def trace_nodule_paths(
        self, payload: Iterable[int], *, hierarchy_id: str = "default",
        max_hops: int = 2, limit: int = 8,
    ) -> NodulePathTrace:
        """Expose observed temporal paths; never select a fact from them."""
        query = _symbols(payload)
        hierarchy = _name(hierarchy_id)
        return self._compositional_view(hierarchy).trace_paths(
            query, max_hops=max_hops, limit=limit,
        )

    def _compositional_view(self, hierarchy: str) -> CompositionalAssociationView:
        observations: list[CompositionObservation] = []
        seen: set[str] = set()
        for row in self._observations.values():
            address = row["payload_id"]
            if row["hierarchy_id"] != hierarchy or address in seen:
                continue
            seen.add(address)
            observations.append(CompositionObservation(
                address, row["stream_id"], self.expand(address),
            ))
        return CompositionalAssociationView(
            self.levels(hierarchy_id=hierarchy), observations,
            within_decay=self.config.within_decay,
            temporal_decay=self.config.temporal_decay,
            forgetting_rate=self.config.forgetting_rate,
            trace_floor=self.config.trace_floor,
            max_pattern_size=self.config.max_context,
        )

    def _views(self, query: tuple[int, ...], hierarchy: str):
        trajectories = tuple(t for t in self._index.snapshot() if t.hierarchy_id == hierarchy)
        ids = {t.trajectory_id: t.source_id for t in trajectories}
        yield 0, query, tuple((t.source_id, t.addresses) for t in trajectories), {}
        transformed: tuple[ScaleAddress, ...] = query
        catalogue: dict[str, tuple[ScaleAddress, ...]] = {}
        for level in self.levels(hierarchy_id=hierarchy):
            catalogue = {**catalogue, **{c.address: c.children for c in level.compositions}}
            transformed = self._hierarchy.collapse_with_catalogue(transformed, level.compositions)
            yield level.depth, transformed, tuple(
                (ids[key], trail) for key, trail in level.transformed_trajectories
            ), catalogue

    @staticmethod
    def _expand_view(trail, catalogue) -> tuple[int, ...]:
        output: list[int] = []
        pending = list(reversed(trail))
        while pending:
            item = pending.pop()
            if type(item) is int:
                output.append(item)
            else:
                pending.extend(reversed(catalogue[item]))
        return tuple(output)

    def _frontier(self, trail, streams, catalogue) -> tuple[RouteStep, ...]:
        # Same variable-context rule applies to atoms and composed addresses.
        # Match through an enclosing composition too: greedy packing must not
        # hide the prefix/suffix of a nodule or erase a competing trajectory.
        expanded_streams = []
        for payload_id, stored in streams:
            atoms: tuple[int, ...] = ()
            boundaries: dict[int, ScaleAddress] = {}
            for address in stored:
                boundaries[len(atoms)] = address
                atoms += self._expand_view((address,), catalogue)
            expanded_streams.append((payload_id, atoms, boundaries))
        minimum = min(len(trail), self.config.min_context)
        for width in range(min(len(trail), self.config.max_context), minimum - 1, -1):
            context = trail[-width:]
            pattern = self._expand_view(context, catalogue)
            support: dict[ScaleAddress | None, set[str]] = {}
            for payload_id, stored, boundaries in expanded_streams:
                for start in range(len(stored) - len(pattern) + 1):
                    end = start + len(pattern)
                    if stored[start:end] == pattern:
                        following = boundaries.get(end, stored[end]) if end < len(stored) else None
                        support.setdefault(following, set()).add(payload_id)
            if support:
                total = sum(len(roots) for roots in support.values())
                return tuple(
                    RouteStep(context, following, tuple(sorted(roots)), len(roots) / total)
                    for following, roots in sorted(support.items(), key=lambda item: repr(item[0]))
                )
        return ()

    def generate(
        self, payload: Iterable[int], *, hierarchy_id: str = "default",
        max_steps: int = 32, beam_width: int = 8, scale: int | None = None,
    ) -> GenerationResult:
        """Read-only hypotheses. A score is relative route support, not truth.

        Auto scale maximizes matched atomic span, then prefers the deeper view.
        A known end competes with continuation and prevents unbounded backoff.
        A whole-payload temporal route, a recurring nodule and an embedded
        observed payload can evoke alternatives beside a continuation.
        Neither operation establishes a fact.
        """
        query = _symbols(payload)
        hierarchy = _name(hierarchy_id)
        if any(type(v) is not int or v < 1 for v in (max_steps, beam_width)):
            raise ValueError("max_steps and beam_width must be positive integers")
        if scale is not None and (type(scale) is not int or scale < 0):
            raise ValueError("scale must be a non-negative integer or None")
        views = list(self._views(query, hierarchy))
        if scale is not None:
            views = [view for view in views if view[0] == scale]
            if not views:
                raise ValueError("requested scale has not formed in this hierarchy")

        def coverage(view):
            frontier = self._frontier(view[1], view[2], view[3])
            return (len(self._expand_view(frontier[0].context, view[3])) if frontier else 0, view[0])

        depth, prompt, streams, catalogue = max(views, key=coverage)
        # (scale trail, log score, evidence, stop reason). Finished hypotheses
        # remain in the same beam; pruning always marks the result truncated.
        beam = [(prompt, 0.0, (), "")]
        ambiguous = truncated = False
        for _ in range(max_steps):
            expanded = []
            for trail, score, evidence, reason in beam:
                if reason:
                    expanded.append((trail, score, evidence, reason))
                    continue
                frontier = self._frontier(trail, streams, catalogue)
                if not frontier:
                    expanded.append((trail, score, evidence, "no_route"))
                    continue
                ambiguous |= len(frontier) > 1
                for step in frontier:
                    is_end = step.next_address is None
                    next_trail = trail if is_end else trail + (step.next_address,)
                    expanded.append((
                        next_trail, score + log(step.relative_support),
                        evidence + (step,), "observed_end" if is_end else "",
                    ))
            expanded.sort(key=lambda row: (-row[1], repr(row[0])))
            truncated |= len(expanded) > beam_width
            beam = expanded[:beam_width]
            if all(row[3] for row in beam):
                break

        candidates = []
        for trail, score, evidence, reason in beam:
            truncated |= not bool(reason)
            continuation = self._expand_view(trail[len(prompt):], catalogue)
            candidates.append(GenerationCandidate(
                query + continuation, continuation, score, reason or "step_limit", evidence,
            ))
        has_continuation = any(candidate.continuation for candidate in candidates)
        can_recall = has_continuation or (
            not ambiguous and not truncated and all(
                candidate.stop_reason in ("no_route", "observed_end")
                for candidate in candidates
            )
        )
        if can_recall:
            neighbors = self.temporal_neighbors(query, hierarchy_id=hierarchy)
            association = self.associated_nodules(
                query, hierarchy_id=hierarchy, limit=beam_width,
            )
            embedded = self.embedded_root_relations(
                query, hierarchy_id=hierarchy, limit=beam_width,
            )
            temporal_recall: tuple[GenerationCandidate, ...] = ()
            if neighbors:
                total = sum(neighbor.weight for neighbor in neighbors)
                temporal_recall = tuple(
                    GenerationCandidate(
                        neighbor.symbols, (), log(neighbor.weight / total),
                        "temporal_recall", (),
                    )
                    for neighbor in neighbors[:beam_width]
                )
            nodule_recall = tuple(
                GenerationCandidate(
                    candidate.symbols, (),
                    log(candidate.rank_score / association.total_rank_score),
                    "nodule_association", (),
                )
                for candidate in association.candidates
            )
            embedded_recall: tuple[GenerationCandidate, ...] = ()
            if embedded.neighbors:
                total = sum(neighbor.weight for neighbor in embedded.neighbors)
                embedded_recall = tuple(
                    GenerationCandidate(
                        neighbor.symbols, (), log(neighbor.weight / total),
                        "embedded_root_relation", (),
                    )
                    for neighbor in embedded.neighbors
                )
            continuation_candidates = tuple(candidates) if has_continuation else ()
            family_count = sum(bool(family) for family in (
                continuation_candidates, temporal_recall, embedded_recall, nodule_recall,
            ))
            if family_count > 1:
                # Scores are relative within each route family, not additive.
                # Continuations come first, then the exact root, embedded
                # roots and nodules. Neither a new continuation nor an
                # adjacent payload hides an older cross-capture route.
                combined: list[GenerationCandidate] = []
                seen: set[tuple[int, ...]] = set()
                for candidate in (*continuation_candidates,
                                  *temporal_recall, *embedded_recall, *nodule_recall):
                    if candidate.output not in seen:
                        seen.add(candidate.output)
                        combined.append(candidate)
                return GenerationResult(
                    "COMBINED_ROUTES" if has_continuation else "COMBINED_RECALL",
                    tuple(combined[:beam_width]),
                    ambiguous or len(neighbors) > 1 or association.ambiguous or
                    embedded.ambiguous or len(combined) > 1,
                    truncated or len(neighbors) > beam_width or association.truncated or
                    embedded.truncated or len(combined) > beam_width,
                    association.depth if nodule_recall and not has_continuation else depth,
                    neighbors[:beam_width] if neighbors else embedded.neighbors,
                    association if nodule_recall else None,
                    embedded if embedded_recall else None,
                )
            if temporal_recall:
                return GenerationResult(
                    "TEMPORAL_RECALL", temporal_recall, len(neighbors) > 1,
                    len(neighbors) > beam_width, depth, neighbors[:beam_width],
                )
            if nodule_recall:
                return GenerationResult(
                    "NODULE_RECALL", nodule_recall, association.ambiguous,
                    association.truncated, association.depth,
                    association_evidence=association,
                )
            if embedded_recall:
                return GenerationResult(
                    "EMBEDDED_TEMPORAL_RECALL", embedded_recall, embedded.ambiguous,
                    embedded.truncated, 0, embedded.neighbors,
                    embedded_evidence=embedded,
                )
        if has_continuation:
            return GenerationResult("CONTINUATION", tuple(candidates), ambiguous, truncated, depth)
        return GenerationResult("ECHO", tuple(candidates), ambiguous, truncated, depth)

    def respond(self, payload: Iterable[int], *, observation_id: str,
                hierarchy_id: str = "default", stream_id: str = "default",
                **generation_options) -> tuple[GenerationResult, ObservationReceipt]:
        """Infer from prior experience, then learn only the external input."""
        symbols = _symbols(payload)
        result = self.generate(symbols, hierarchy_id=hierarchy_id, **generation_options)
        receipt = self.observe(symbols, observation_id=observation_id,
                               hierarchy_id=hierarchy_id, stream_id=stream_id)
        return result, receipt

    def learning_state(self) -> dict:
        """Derived diagnostics exclude mere occurrence metadata."""
        return dict(
            learned_payloads=len(self._learned), trajectories=self._index.count,
            symbol_field=self._symbol_field.snapshot(), root_field=self._root_field.snapshot(),
        )

    def snapshot(self) -> dict:
        return dict(
            schema=SCHEMA, config=asdict(self.config),
            nodes=[dict(address=address, children=list(children)) for address, children in self._nodes.items()],
            observations=[dict(observation_id=key, **row) for key, row in self._observations.items()],
        )

    @classmethod
    def restore(cls, state: dict) -> "TrajectoryGenerationExperiment":
        if state.get("schema") != SCHEMA:
            raise ValueError("unknown trajectory generation snapshot schema")
        memory = cls(GenerationConfig(**state["config"]))
        for node in state["nodes"]:
            address, children = node["address"], tuple(node["children"])
            if not children or address in memory._nodes:
                raise ValueError("empty or duplicate stored nodule")
            if any(
                not ((type(child) is int and child >= 0)
                     or (type(child) is str and child in memory._nodes))
                for child in children
            ):
                raise ValueError("nodule children must be atoms or earlier references")
            memory._nodes[address] = children
            if _payload_id(memory.expand(address)) != address:
                raise ValueError("nodule content checksum mismatch")
        for row in state["observations"]:
            memory.observe(
                memory.expand(row["payload_id"]), observation_id=row["observation_id"],
                hierarchy_id=row["hierarchy_id"], stream_id=row["stream_id"],
            )
        if memory.snapshot() != state:
            raise ValueError("non-canonical trajectory generation snapshot")
        return memory

    def save(self, persistence: ContentAddressedStatePersistence) -> StateSnapshotReceipt:
        return persistence.store_bytes(_encoded(self.snapshot()))

    @classmethod
    def load(cls, persistence: ContentAddressedStatePersistence,
             receipt: StateSnapshotReceipt) -> "TrajectoryGenerationExperiment":
        return cls.restore(json.loads(persistence.load_bytes(receipt)))
