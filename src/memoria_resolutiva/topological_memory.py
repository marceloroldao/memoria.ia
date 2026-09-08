from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
import hashlib
import re
from typing import Iterable
import unicodedata


_TOKEN_RE = re.compile(r"\w+(?:[:h]\w+)?", re.UNICODE)


def _canonical(value: str) -> str:
    value = unicodedata.normalize("NFC", value)
    return " ".join(value.strip().casefold().split())


def _address(kind: str, canonical_value: str) -> str:
    payload = f"memoria.topology.v1\x00{kind}\x00{canonical_value}".encode("utf-8")
    return "mt1:" + hashlib.blake2b(payload, digest_size=16).hexdigest()


@dataclass(slots=True)
class TopologicalNode:
    address: str
    kind: str
    canonical_value: str
    occurrences: int = 0
    components: tuple[str, ...] = ()
    edges_out: set[str] = field(default_factory=set)
    edges_in: set[str] = field(default_factory=set)

    @property
    def density(self) -> int:
        return len(self.edges_out) + len(self.edges_in)


@dataclass(frozen=True, slots=True)
class RawMemory:
    address: str
    text: str


@dataclass(frozen=True, slots=True)
class IngestionResult:
    raw_memory_address: str
    text_address: str
    word_addresses: tuple[str, ...]
    new_nodes: int
    reused_nodes: int


class AddressSpace:
    """Experimental deterministic address space.

    This is deliberately additive and independent from the frozen RC7 storage path.
    Stable node identity is based on ``kind + canonical value``. Composition is
    represented by explicit edges instead of being encoded into temporal occurrences.
    """

    def __init__(self) -> None:
        self._nodes: dict[str, TopologicalNode] = {}
        self._raw: dict[str, RawMemory] = {}
        self._ingestions = 0
        self._new_nodes = 0
        self._reused_nodes = 0

    def _intern(self, kind: str, value: str, *, components: Iterable[str] = ()) -> tuple[TopologicalNode, bool]:
        canonical = _canonical(value)
        if not canonical:
            raise ValueError("node value must be non-empty")
        address = _address(kind, canonical)
        component_tuple = tuple(components)
        node = self._nodes.get(address)
        created = node is None
        if created:
            node = TopologicalNode(address, kind, canonical, components=component_tuple)
            self._nodes[address] = node
            self._new_nodes += 1
        else:
            self._reused_nodes += 1
            if component_tuple and not node.components:
                node.components = component_tuple
        node.occurrences += 1
        for child_address in component_tuple:
            if child_address not in self._nodes:
                raise KeyError(f"unknown component address: {child_address}")
            node.edges_out.add(child_address)
            self._nodes[child_address].edges_in.add(address)
        return node, created

    def resolve(self, kind: str, value: str) -> TopologicalNode | None:
        canonical = _canonical(value)
        if not canonical:
            return None
        return self._nodes.get(_address(kind, canonical))

    def node(self, address: str) -> TopologicalNode | None:
        return self._nodes.get(address)

    def reconstruct_raw(self, raw_memory_address: str) -> str | None:
        raw = self._raw.get(raw_memory_address)
        return None if raw is None else raw.text

    def ingest_text(self, text: str) -> IngestionResult:
        if not text or not text.strip():
            raise ValueError("text must be non-empty")
        new_before = self._new_nodes
        reused_before = self._reused_nodes

        raw_digest = hashlib.blake2b(text.encode("utf-8"), digest_size=16).hexdigest()
        raw_address = "raw1:" + raw_digest
        self._raw.setdefault(raw_address, RawMemory(raw_address, text))

        words: list[TopologicalNode] = []
        for match in _TOKEN_RE.finditer(text):
            surface = match.group(0)
            canonical_word = _canonical(surface)
            symbol_nodes = [self._intern("symbol", char)[0] for char in canonical_word if not char.isspace()]

            # Prefix fragments make the lower trajectory inspectable without forcing
            # every possible substring into memory.
            for length in range(2, len(canonical_word)):
                prefix = canonical_word[:length]
                prefix_components = tuple(node.address for node in symbol_nodes[:length])
                self._intern("fragment", prefix, components=prefix_components)

            word, _ = self._intern(
                "word",
                canonical_word,
                components=tuple(node.address for node in symbol_nodes),
            )
            words.append(word)

        phrase_value = " ".join(word.canonical_value for word in words)
        phrase, _ = self._intern("phrase", phrase_value, components=(word.address for word in words))
        text_node, _ = self._intern("text", text, components=(phrase.address,))
        self._ingestions += 1
        return IngestionResult(
            raw_memory_address=raw_address,
            text_address=text_node.address,
            word_addresses=tuple(word.address for word in words),
            new_nodes=self._new_nodes - new_before,
            reused_nodes=self._reused_nodes - reused_before,
        )

    def metrics(self) -> dict[str, float | int]:
        total_interns = self._new_nodes + self._reused_nodes
        edge_count = sum(len(node.edges_out) for node in self._nodes.values())
        return {
            "nodes": len(self._nodes),
            "node_reuse_ratio": 0.0 if total_interns == 0 else self._reused_nodes / total_interns,
            "branching_factor": 0.0 if not self._nodes else edge_count / len(self._nodes),
            "duplicate_address_count": 0,
            "ingestions": self._ingestions,
        }


class TemporalOperator(str, Enum):
    CURRENT = "CURRENT"
    PREVIOUS_STATE = "PREVIOUS_STATE"
    FIRST_STATE = "FIRST_STATE"
    EXISTED_IN_HISTORY = "EXISTED_IN_HISTORY"
    STATE_BEFORE_VALUE = "STATE_BEFORE_VALUE"
    STATE_AFTER_VALUE = "STATE_AFTER_VALUE"
    STATE_DIFF = "STATE_DIFF"
    HISTORY = "HISTORY"


@dataclass(frozen=True, slots=True)
class TemporalEvent:
    event_id: str
    sequence: int
    subject_address: str
    attribute_address: str
    value_address: str
    source: str
    raw_memory_address: str | None
    event_time: str | None
    ingestion_time: str


@dataclass(frozen=True, slots=True)
class Transition:
    subject_address: str
    attribute_address: str
    from_value_address: str
    to_value_address: str
    from_sequence: int
    to_sequence: int


@dataclass(frozen=True, slots=True)
class CognitiveResult:
    operator: TemporalOperator
    subject_address: str
    attribute_address: str
    value_address: str | None = None
    sequence: int | None = None
    exists: bool | None = None
    history: tuple[tuple[int, str], ...] = ()
    transitions: tuple[Transition, ...] = ()


class TemporalEventStore:
    """Monotonic occurrence history over reusable topological addresses."""

    def __init__(self, addresses: AddressSpace) -> None:
        self.addresses = addresses
        self._next_sequence = 1
        self._events: list[TemporalEvent] = []
        self._transitions: list[Transition] = []

    def _entity_address(self, value: str) -> str:
        return self.addresses._intern("entity", value)[0].address

    def _attribute_address(self, value: str) -> str:
        return self.addresses._intern("attribute", value)[0].address

    def _value_address(self, value: str) -> str:
        return self.addresses._intern("value", value)[0].address

    def observe_state(
        self,
        subject: str,
        attribute: str,
        value: str,
        *,
        source: str = "USER_CONFIRMED",
        raw_memory_address: str | None = None,
        event_time: str | None = None,
        sequence: int | None = None,
    ) -> TemporalEvent:
        if sequence is None:
            sequence = self._next_sequence
        if sequence < self._next_sequence:
            raise ValueError("sequence must be monotonic and cannot move backward")
        self._next_sequence = sequence + 1

        subject_address = self._entity_address(subject)
        attribute_address = self._attribute_address(attribute)
        value_address = self._value_address(value)
        prior = self.events_for(subject_address, attribute_address)
        event = TemporalEvent(
            event_id=f"E{sequence}",
            sequence=sequence,
            subject_address=subject_address,
            attribute_address=attribute_address,
            value_address=value_address,
            source=source,
            raw_memory_address=raw_memory_address,
            event_time=event_time,
            ingestion_time=datetime.now(timezone.utc).isoformat(),
        )
        self._events.append(event)
        if prior and prior[-1].value_address != value_address:
            previous = prior[-1]
            self._transitions.append(
                Transition(
                    subject_address,
                    attribute_address,
                    previous.value_address,
                    value_address,
                    previous.sequence,
                    sequence,
                )
            )
        return event

    def events_for(self, subject_address: str, attribute_address: str) -> tuple[TemporalEvent, ...]:
        return tuple(
            sorted(
                (
                    event for event in self._events
                    if event.subject_address == subject_address and event.attribute_address == attribute_address
                ),
                key=lambda event: event.sequence,
            )
        )

    def transitions_for(self, subject_address: str, attribute_address: str) -> tuple[Transition, ...]:
        return tuple(
            transition for transition in self._transitions
            if transition.subject_address == subject_address and transition.attribute_address == attribute_address
        )

    def resolve(
        self,
        subject: str,
        attribute: str,
        operator: TemporalOperator,
        *,
        value: str | None = None,
    ) -> CognitiveResult:
        subject_node = self.addresses.resolve("entity", subject)
        attribute_node = self.addresses.resolve("attribute", attribute)
        if subject_node is None or attribute_node is None:
            return CognitiveResult(operator, "", "")
        events = self.events_for(subject_node.address, attribute_node.address)
        transitions = self.transitions_for(subject_node.address, attribute_node.address)
        if not events:
            return CognitiveResult(operator, subject_node.address, attribute_node.address)

        history = tuple((event.sequence, event.value_address) for event in events)
        if operator is TemporalOperator.CURRENT:
            chosen = events[-1]
            return CognitiveResult(operator, subject_node.address, attribute_node.address, chosen.value_address, chosen.sequence)
        if operator is TemporalOperator.PREVIOUS_STATE:
            chosen = events[-2] if len(events) >= 2 else None
            return CognitiveResult(operator, subject_node.address, attribute_node.address, None if chosen is None else chosen.value_address, None if chosen is None else chosen.sequence)
        if operator is TemporalOperator.FIRST_STATE:
            chosen = events[0]
            return CognitiveResult(operator, subject_node.address, attribute_node.address, chosen.value_address, chosen.sequence)
        if operator is TemporalOperator.HISTORY:
            return CognitiveResult(operator, subject_node.address, attribute_node.address, history=history)
        if operator is TemporalOperator.STATE_DIFF:
            return CognitiveResult(operator, subject_node.address, attribute_node.address, history=history, transitions=transitions)
        if value is None:
            raise ValueError(f"{operator.value} requires value")
        value_node = self.addresses.resolve("value", value)
        target_address = None if value_node is None else value_node.address
        matches = [event for event in events if event.value_address == target_address]
        if operator is TemporalOperator.EXISTED_IN_HISTORY:
            chosen = matches[0] if matches else None
            return CognitiveResult(operator, subject_node.address, attribute_node.address, target_address, None if chosen is None else chosen.sequence, bool(matches))
        if not matches:
            return CognitiveResult(operator, subject_node.address, attribute_node.address)
        target = matches[-1]
        index = events.index(target)
        if operator is TemporalOperator.STATE_BEFORE_VALUE:
            chosen = events[index - 1] if index > 0 else None
        elif operator is TemporalOperator.STATE_AFTER_VALUE:
            chosen = events[index + 1] if index + 1 < len(events) else None
        else:
            raise ValueError(f"unsupported temporal operator: {operator}")
        return CognitiveResult(operator, subject_node.address, attribute_node.address, None if chosen is None else chosen.value_address, None if chosen is None else chosen.sequence)

    def value_text(self, address: str | None) -> str | None:
        if address is None:
            return None
        node = self.addresses.node(address)
        return None if node is None else node.canonical_value

    def metrics(self) -> dict[str, int]:
        return {
            "events_created": len(self._events),
            "transitions_created": len(self._transitions),
        }
