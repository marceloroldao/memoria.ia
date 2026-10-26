"""Experimental memoria.ia baseline.

No neural network is used. The implementation is intentionally small and
reproducible so architectural hypotheses can be falsified by ablation.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from hashlib import blake2b
from typing import Dict, List, Optional, Tuple


@dataclass
class Entry:
    concept: str
    value: str
    observations: int = 1
    conflicts: int = 0
    last_tick: int = 0


@dataclass
class Layer:
    bits: int
    update_period: int
    entries: Dict[str, Entry] = field(default_factory=dict)


class ResolutiveMemory:
    """Hierarchical memory with deduplication and multiscale update clocks."""

    def __init__(self, bits=(8, 16, 32, 64), temporal_scaling=True):
        self.temporal_scaling = temporal_scaling
        self.layers: List[Layer] = []
        for i, b in enumerate(bits):
            # Ablation: uniform clock versus progressively slower deep layers.
            period = (2 ** i) if temporal_scaling else 1
            self.layers.append(Layer(bits=b, update_period=period))
        self.tick = 0

    @staticmethod
    def _key(concept: str) -> str:
        return blake2b(concept.strip().lower().encode(), digest_size=16).hexdigest()

    def observe(self, concept: str, value: str) -> None:
        self.tick += 1
        key = self._key(concept)
        root = self.layers[0]
        current = root.entries.get(key)
        if current is None:
            root.entries[key] = Entry(concept, value, last_tick=self.tick)
        elif current.value == value:
            current.observations += 1
            current.last_tick = self.tick
        else:
            current.conflicts += 1
            # Recent contradictory evidence is retained at the fast layer.
            root.entries[key] = Entry(
                concept, value, observations=1,
                conflicts=current.conflicts, last_tick=self.tick
            )
        self._consolidate(key)

    def _consolidate(self, key: str) -> None:
        for i in range(len(self.layers) - 1):
            src, dst = self.layers[i], self.layers[i + 1]
            item = src.entries.get(key)
            if item is None:
                continue
            threshold = 2 ** (i + 1)
            if item.observations < threshold:
                continue
            if self.tick % dst.update_period != 0:
                continue
            old = dst.entries.get(key)
            # Deep memory changes only after repeated coherent evidence.
            if old is None or old.value == item.value:
                dst.entries[key] = Entry(
                    item.concept, item.value, item.observations,
                    item.conflicts, self.tick
                )

    def recall(self, concept: str) -> Optional[Tuple[str, int]]:
        key = self._key(concept)
        # Prefer the deepest consolidated representation.
        for layer in reversed(self.layers):
            if key in layer.entries:
                return layer.entries[key].value, layer.bits
        return None

    def footprint(self) -> int:
        return sum(len(layer.entries) for layer in self.layers)
