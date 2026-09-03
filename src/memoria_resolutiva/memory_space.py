from __future__ import annotations

from enum import Enum


class MemorySpace(str, Enum):
    """Logical epistemic space for persisted memory records.

    `FACTUAL` records may participate in factual resolution subject to provenance,
    authority, supersession and conflict rules. `GENERATIVE` records are retained
    for conversational continuity/history but cannot independently establish fact.
    """

    FACTUAL = "factual"
    GENERATIVE = "generative"


_GENERATIVE_SOURCE_TYPES = frozenset({"assistant_generated", "retrieved_replay"})


def memory_space_for_source_type(source_type: str) -> MemorySpace:
    """Classify a provenance source type without requiring a schema migration.

    The classification is intentionally deterministic and additive: existing
    stores continue to persist `source_type`, while callers can expose an explicit
    memory-space discriminator immediately.
    """

    value = str(source_type).strip()
    if not value:
        raise ValueError("source_type must be non-empty")
    if value in _GENERATIVE_SOURCE_TYPES:
        return MemorySpace.GENERATIVE
    return MemorySpace.FACTUAL


def may_be_factual_root(source_type: str) -> bool:
    """Whether a record may independently anchor factual state."""

    return memory_space_for_source_type(source_type) is MemorySpace.FACTUAL
