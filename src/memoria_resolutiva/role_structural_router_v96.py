from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

from .semantic_router_v96 import AdaptiveSemanticRouterV96, SemanticResolution
from .structural_router_v96 import StructuralResolution, StructuralSemanticRouterV96
from .textual import tokenize


@dataclass(frozen=True, slots=True)
class RoleTokenEvidence:
    token: str
    role_id: str
    source: str
    score: float
    margin: float


@dataclass(frozen=True, slots=True)
class RoleStructuralResolution:
    text: str
    concept_id: str | None
    score: float
    margin: float
    source: str
    canonical_roles: tuple[str, ...]
    role_evidence: tuple[RoleTokenEvidence, ...]
    structural: StructuralResolution


class RoleStructuralRouterV96:
    """Experimental abstraction layer: lexical tokens -> semantic roles -> structure.

    Exact registered anchors map deterministically to roles. Unseen lexical variants
    may still map through the non-neural contextual semantic router. The structural
    scorer therefore compares ordered role signatures instead of raw words.
    """

    def __init__(
        self,
        *,
        role_threshold: float = 0.45,
        role_min_margin: float = 0.05,
        structural_threshold: float = 0.45,
        structural_min_margin: float = 0.08,
        relation_window: int = 5,
        use_native: bool | None = None,
    ) -> None:
        self.roles = AdaptiveSemanticRouterV96(
            threshold=role_threshold,
            min_margin=role_min_margin,
            use_native=use_native,
        )
        self.structure = StructuralSemanticRouterV96(
            relation_window=relation_window,
            threshold=structural_threshold,
            min_margin=structural_min_margin,
            use_native=use_native,
        )
        self._exact_roles: dict[str, str] = {}

    def observe(self, sentences: Iterable[str]) -> None:
        self.roles.observe(sentences)

    def register_role(self, role_id: str, anchors: Iterable[str]) -> None:
        normalized = {anchor.strip().lower() for anchor in anchors if anchor.strip()}
        if not normalized:
            raise ValueError("role must have at least one anchor")
        self.roles.register_concept(role_id, normalized)
        for anchor in normalized:
            existing = self._exact_roles.get(anchor)
            if existing is not None and existing != role_id:
                raise ValueError(f"anchor {anchor!r} already belongs to role {existing!r}")
            self._exact_roles[anchor] = role_id

    def register_intent_pattern(self, concept_id: str, role_ids: Iterable[str], *, repeat: int = 1) -> None:
        roles = [role.strip().lower() for role in role_ids if role.strip()]
        if len(roles) < 2:
            raise ValueError("intent pattern must contain at least two roles")
        self.structure.register_pattern(concept_id, " ".join(roles), repeat=repeat)

    def register_intent_many(self, concept_id: str, patterns: Iterable[Iterable[str]]) -> None:
        for pattern in patterns:
            self.register_intent_pattern(concept_id, pattern)

    def _resolve_role(self, token: str) -> tuple[str | None, RoleTokenEvidence | None]:
        exact = self._exact_roles.get(token)
        if exact is not None:
            return exact, RoleTokenEvidence(token, exact, "exact", 1.0, 1.0)
        semantic: SemanticResolution = self.roles.resolve_token(token)
        if semantic.concept_id is None:
            return None, None
        return semantic.concept_id, RoleTokenEvidence(
            token,
            semantic.concept_id,
            "context",
            semantic.score,
            semantic.margin,
        )

    def canonicalize(self, text: str) -> tuple[tuple[str, ...], tuple[RoleTokenEvidence, ...]]:
        canonical: list[str] = []
        evidence: list[RoleTokenEvidence] = []
        for token in tokenize(text.strip().lower()):
            role_id, role_evidence = self._resolve_role(token)
            if role_id is None or role_evidence is None:
                continue
            canonical.append(role_id)
            evidence.append(role_evidence)
        return tuple(canonical), tuple(evidence)

    def resolve_text(self, text: str) -> RoleStructuralResolution:
        normalized = text.strip().lower()
        canonical, evidence = self.canonicalize(normalized)
        if len(canonical) < 2:
            empty = StructuralResolution(normalized, None, 0.0, 0.0, "unresolved", ())
            return RoleStructuralResolution(normalized, None, 0.0, 0.0, "unresolved", canonical, evidence, empty)
        structural = self.structure.resolve_text(" ".join(canonical))
        source = "role_structural" if structural.concept_id is not None else "unresolved"
        return RoleStructuralResolution(
            normalized,
            structural.concept_id,
            structural.score,
            structural.margin,
            source,
            canonical,
            evidence,
            structural,
        )
