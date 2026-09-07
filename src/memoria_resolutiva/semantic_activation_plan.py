from __future__ import annotations

import unicodedata
from typing import Iterable


def _key(value: str) -> str:
    value = unicodedata.normalize("NFKD", str(value))
    value = "".join(ch for ch in value if not unicodedata.combining(ch))
    return " ".join(value.casefold().strip().split())


def plan_activation_concepts(
    base_concepts: Iterable[str],
    semantic_concepts: Iterable[str] = (),
    *,
    max_concepts: int = 2,
) -> tuple[str, ...]:
    """Build a bounded structural activation plan.

    Concepts extracted directly from the current input always keep precedence.
    Graph-derived semantic concepts are appended only when budget remains.
    Matching is accent/case insensitive so semantic aliases cannot consume the
    activation budget twice.

    The function is deliberately domain-agnostic: it does not know what ONU,
    equipment, EPON, network, model, stage, or any other concept means.
    """
    if max_concepts < 1:
        raise ValueError("max_concepts must be >= 1")

    selected: list[str] = []
    seen: set[str] = set()
    for source in (base_concepts, semantic_concepts):
        for raw in source:
            value = str(raw).strip()
            key = _key(value)
            if not key or key in seen:
                continue
            seen.add(key)
            selected.append(value)
            if len(selected) >= max_concepts:
                return tuple(selected)
    return tuple(selected)
