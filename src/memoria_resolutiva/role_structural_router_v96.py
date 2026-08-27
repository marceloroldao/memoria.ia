from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

from .semantic_router_v96 import AdaptiveSemanticRouterV96, SemanticResolution
from .structural_router_v96 import StructuralResolution, StructuralSemanticRouterV96
from .textual import tokenize

_ROLE_STOPWORDS = {
    "a", "ao", "aos", "as", "com", "da", "das", "de", "do", "dos", "e",
    "em", "na", "nas", "no", "nos", "o", "os", "para", "por", "sem", "um", "uma",
}


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

    Exact anchors are deterministic. Context-only words keep several candidate
    roles until the phrase structure is evaluated, so locally ambiguous words can
    be disambiguated by the globally coherent ordered role signature. No neural
    model or embedding is used.
    """

    def __init__(
        self,
        *,
        role_threshold: float = 0.45,
        role_min_margin: float = 0.05,
        structural_threshold: float = 0.45,
        structural_min_margin: float = 0.08,
        relation_window: int = 5,
        role_top_k: int = 4,
        beam_width: int = 64,
        candidate_floor: float = 0.02,
        use_native: bool | None = None,
    ) -> None:
        if role_top_k < 1:
            raise ValueError("role_top_k must be >= 1")
        if beam_width < 1:
            raise ValueError("beam_width must be >= 1")
        if candidate_floor < 0.0:
            raise ValueError("candidate_floor must be >= 0")
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
        self.role_top_k = role_top_k
        self.beam_width = beam_width
        self.candidate_floor = candidate_floor
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

    def _rank_role_candidates(self, token: str) -> list[RoleTokenEvidence]:
        exact = self._exact_roles.get(token)
        if exact is not None:
            return [RoleTokenEvidence(token, exact, "exact", 1.0, 1.0)]

        ranked = self.roles.memory.rank_registered(token, None, top_k=self.role_top_k)
        if ranked is None:
            ranked = []
            for role_id, anchors in self.roles._concepts.items():
                score = max((self.roles._score(token, anchor) for anchor in anchors), default=0.0)
                ranked.append((role_id, score))
            ranked.sort(key=lambda item: (-item[1], item[0]))
            ranked = ranked[: self.role_top_k]

        candidates: list[RoleTokenEvidence] = []
        for index, (role_id, score) in enumerate(ranked):
            score = float(score)
            if score < self.candidate_floor or score <= 0.0:
                continue
            next_score = float(ranked[index + 1][1]) if index + 1 < len(ranked) else 0.0
            candidates.append(
                RoleTokenEvidence(
                    token,
                    role_id,
                    "context_joint",
                    score,
                    max(0.0, score - next_score),
                )
            )
        return candidates

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
        """Greedy lexical canonicalization retained for inspection/debug."""
        canonical: list[str] = []
        evidence: list[RoleTokenEvidence] = []
        for token in tokenize(text.strip().lower()):
            if token in _ROLE_STOPWORDS:
                continue
            role_id, role_evidence = self._resolve_role(token)
            if role_id is None or role_evidence is None:
                continue
            canonical.append(role_id)
            evidence.append(role_evidence)
        return tuple(canonical), tuple(evidence)

    def _joint_candidates(self, text: str):
        beams: list[tuple[tuple[str, ...], tuple[RoleTokenEvidence, ...], float]] = [((), (), 0.0)]
        for token in tokenize(text.strip().lower()):
            if token in _ROLE_STOPWORDS:
                continue
            options = self._rank_role_candidates(token)
            if not options:
                continue
            expanded = []
            for roles, evidence, lexical_sum in beams:
                for option in options:
                    expanded.append(
                        (
                            roles + (option.role_id,),
                            evidence + (option,),
                            lexical_sum + option.score,
                        )
                    )
            expanded.sort(key=lambda item: (-item[2], item[0]))
            beams = expanded[: self.beam_width]
        return beams

    def resolve_text(self, text: str) -> RoleStructuralResolution:
        normalized = text.strip().lower()
        beams = self._joint_candidates(normalized)
        ranked_global = []
        for canonical, evidence, lexical_sum in beams:
            if len(canonical) < 2:
                continue
            structural = self.structure.resolve_text(" ".join(canonical))
            if structural.concept_id is None:
                continue
            lexical_mean = lexical_sum / max(1, len(evidence))
            combined = structural.score * lexical_mean
            ranked_global.append((combined, canonical, evidence, structural))

        if not ranked_global:
            canonical, evidence = self.canonicalize(normalized)
            empty = StructuralResolution(normalized, None, 0.0, 0.0, "unresolved", ())
            return RoleStructuralResolution(
                normalized, None, 0.0, 0.0, "unresolved", canonical, evidence, empty
            )

        ranked_global.sort(key=lambda item: (-item[0], item[3].concept_id or "", item[1]))
        best_combined, canonical, evidence, structural = ranked_global[0]
        second_combined = ranked_global[1][0] if len(ranked_global) > 1 else 0.0
        global_margin = max(0.0, best_combined - second_combined)
        return RoleStructuralResolution(
            normalized,
            structural.concept_id,
            structural.score,
            max(structural.margin, global_margin),
            "role_structural_joint",
            canonical,
            evidence,
            structural,
        )
