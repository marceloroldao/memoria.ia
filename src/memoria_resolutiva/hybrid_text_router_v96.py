from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

from .semantic_router_v96 import AdaptiveSemanticRouterV96, TextResolution
from .structural_router_v96 import StructuralResolution, StructuralSemanticRouterV96


@dataclass(frozen=True, slots=True)
class HybridRoutingStats:
    total: int
    semantic: int
    structural: int
    consensus: int
    conflict: int
    unresolved: int


@dataclass(frozen=True, slots=True)
class HybridTextResolution:
    text: str
    concept_id: str | None
    score: float
    margin: float
    source: str
    semantic: TextResolution
    structural: StructuralResolution


class HybridTextRouterV96:
    """Experimental conservative phrase router combining meaning and structure.

    The semantic router remains authoritative when it resolves and the structural
    router has no contradictory evidence.  Structural routing is allowed to
    resolve a phrase when semantic evidence abstains.  If both resolve to
    different concepts, the hybrid abstains instead of silently overriding one
    resolver with the other.
    """

    def __init__(
        self,
        *,
        semantic_threshold: float = 0.55,
        semantic_min_margin: float = 0.08,
        structural_threshold: float = 0.45,
        structural_min_margin: float = 0.08,
        relation_window: int = 3,
        use_native: bool | None = None,
    ) -> None:
        self.semantic = AdaptiveSemanticRouterV96(
            threshold=semantic_threshold,
            min_margin=semantic_min_margin,
            use_native=use_native,
        )
        self.structural = StructuralSemanticRouterV96(
            relation_window=relation_window,
            threshold=structural_threshold,
            min_margin=structural_min_margin,
            use_native=use_native,
        )
        self._counts = {
            "semantic": 0,
            "structural": 0,
            "consensus": 0,
            "conflict": 0,
            "unresolved": 0,
        }

    def observe(self, sentences: Iterable[str]) -> None:
        self.semantic.observe(sentences)

    def register_semantic_concept(self, concept_id: str, anchors: Iterable[str]) -> None:
        self.semantic.register_concept(concept_id, anchors)

    def register_structural_pattern(self, concept_id: str, text: str, *, repeat: int = 1) -> None:
        self.structural.register_pattern(concept_id, text, repeat=repeat)

    def register_structural_many(self, concept_id: str, patterns: Iterable[str]) -> None:
        self.structural.register_many(concept_id, patterns)

    def reset_stats(self) -> None:
        for key in self._counts:
            self._counts[key] = 0

    def stats(self) -> HybridRoutingStats:
        return HybridRoutingStats(
            total=sum(self._counts.values()),
            semantic=self._counts["semantic"],
            structural=self._counts["structural"],
            consensus=self._counts["consensus"],
            conflict=self._counts["conflict"],
            unresolved=self._counts["unresolved"],
        )

    def resolve_text(self, text: str) -> HybridTextResolution:
        semantic = self.semantic.resolve_text(text)
        structural = self.structural.resolve_text(text)
        sid = semantic.concept_id
        tid = structural.concept_id

        if sid is not None and tid is not None:
            if sid == tid:
                self._counts["consensus"] += 1
                return HybridTextResolution(
                    text.strip().lower(), sid,
                    max(semantic.score, structural.score),
                    min(semantic.margin, structural.margin),
                    "consensus", semantic, structural,
                )
            self._counts["conflict"] += 1
            return HybridTextResolution(
                text.strip().lower(), None,
                max(semantic.score, structural.score),
                0.0, "conflict", semantic, structural,
            )

        if sid is not None:
            self._counts["semantic"] += 1
            return HybridTextResolution(
                text.strip().lower(), sid, semantic.score, semantic.margin,
                "semantic", semantic, structural,
            )

        if tid is not None:
            self._counts["structural"] += 1
            return HybridTextResolution(
                text.strip().lower(), tid, structural.score, structural.margin,
                "structural", semantic, structural,
            )

        self._counts["unresolved"] += 1
        return HybridTextResolution(
            text.strip().lower(), None,
            max(semantic.score, structural.score),
            max(semantic.margin, structural.margin),
            "unresolved", semantic, structural,
        )
