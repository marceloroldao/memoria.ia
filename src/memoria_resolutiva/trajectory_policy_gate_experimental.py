from __future__ import annotations

import itertools
from dataclasses import dataclass
from typing import Iterable, Literal

from .role_structural_router_v96 import RoleStructuralRouterV96
from .textual import tokenize

TrajectoryDecision = Literal["accept", "reject", "fail_closed"]
BOS = "__bos__"
EOS = "__eos__"


@dataclass(frozen=True, slots=True)
class TrajectoryPolicyResolution:
    text: str
    decision: TrajectoryDecision
    coverage: float
    threshold: float | None
    margin: float | None
    reason: str
    token_count: int


class ExperimentalTrajectoryPolicyGate:
    """Opt-in non-neural policy gate for bounded relational trajectories.

    This class is deliberately separate from RoleStructuralRouterV96. It does not
    replace or alter the current routing policy. It classifies evidence into three
    states:

    * accept: enough evidence exists and the learned trajectory is covered;
    * reject: enough evidence exists but trajectory topology/coverage is wrong;
    * fail_closed: evidence or calibration is insufficient/contradictory.

    Calibration is deterministic and uses only registered role anchors/patterns.
    It requires at least two anchors per role so a meaningful held-out semantic
    generalization claim can be made.
    """

    def __init__(self, *, radius: int = 3, use_native: bool | None = None) -> None:
        self.router = RoleStructuralRouterV96(
            role_top_k=8,
            beam_width=4096,
            max_context_relabels=8,
            use_native=use_native,
        )
        # ContextAssociator radius is currently owned by the underlying textual
        # memory. Keep the argument explicit for forward compatibility and reject
        # unsupported values rather than silently pretending it changed.
        actual_radius = self.router.roles.memory.associator.radius
        if radius != actual_radius:
            raise ValueError(f"experimental gate currently requires radius={actual_radius}")
        self._patterns: list[tuple[str, ...]] = []
        self._threshold: float | None = None
        self._margin: float | None = None
        self._calibration_reason = "not calibrated"

    @property
    def calibrated(self) -> bool:
        return self._threshold is not None and self._margin is not None and self._margin > 0.0

    @property
    def threshold(self) -> float | None:
        return self._threshold

    @property
    def calibration_margin(self) -> float | None:
        return self._margin

    def observe(self, sentences: Iterable[str]) -> None:
        self.router.observe(f"{BOS} {sentence} {EOS}" for sentence in sentences)
        self._invalidate_calibration("observations changed")

    def register_role(self, role_id: str, anchors: Iterable[str]) -> None:
        self.router.register_role(role_id, anchors)
        self._invalidate_calibration("roles changed")

    def register_pattern(self, role_ids: Iterable[str]) -> None:
        pattern = tuple(role.strip().lower() for role in role_ids if role.strip())
        if len(pattern) < 2:
            raise ValueError("trajectory pattern must contain at least two roles")
        if pattern not in self._patterns:
            self._patterns.append(pattern)
        self._invalidate_calibration("patterns changed")

    def _invalidate_calibration(self, reason: str) -> None:
        self._threshold = None
        self._margin = None
        self._calibration_reason = reason

    def _coverage(self, tokens: tuple[str, ...]) -> float:
        assoc = self.router.roles.memory.associator
        seq = (BOS,) + tokens + (EOS,)
        supported = 0
        expected = 0
        radius = assoc.radius
        for i, token in enumerate(seq):
            profile = assoc.profiles.get(token)
            lo = max(0, i - radius)
            hi = min(len(seq), i + radius + 1)
            for j in range(lo, hi):
                if j == i:
                    continue
                expected += 1
                if profile and profile.get((j - i, seq[j]), 0) > 0:
                    supported += 1
        return supported / max(1, expected)

    def _token_supported(self, token: str) -> bool:
        token = token.lower()
        if token in self.router._exact_roles:
            return True
        if token not in self.router.roles.memory.associator.profiles:
            return False
        return bool(self.router._rank_role_candidates(token))

    def calibrate(self) -> bool:
        if not self._patterns:
            self._invalidate_calibration("no patterns registered")
            return False

        concepts = self.router.roles._concepts
        used_roles = {role for pattern in self._patterns for role in pattern}
        if any(role not in concepts or len(concepts[role]) < 2 for role in used_roles):
            self._invalidate_calibration("at least two anchors per used role are required")
            return False

        role_by_anchor = {
            anchor: role
            for role in used_roles
            for anchor in concepts[role]
        }
        pattern_set = set(self._patterns)
        max_anchors = max(len(concepts[role]) for role in used_roles)
        rows: dict[tuple[str, ...], tuple[bool, float]] = {}

        for pattern in self._patterns:
            for shift in range(max_anchors):
                seq = tuple(sorted(concepts[role])[shift % len(concepts[role])] for role in pattern)
                for perm in itertools.permutations(seq):
                    roles = tuple(role_by_anchor[token] for token in perm)
                    rows[perm] = (roles in pattern_set, self._coverage(perm))

        valid = [coverage for is_valid, coverage in rows.values() if is_valid]
        invalid = [coverage for is_valid, coverage in rows.values() if not is_valid]
        if not valid or not invalid:
            self._invalidate_calibration("insufficient calibration classes")
            return False

        vmin = min(valid)
        imax = max(invalid)
        margin = vmin - imax
        if margin <= 0.0:
            self._invalidate_calibration("trajectory classes are not separable")
            return False

        self._threshold = (vmin + imax) / 2.0
        self._margin = margin
        self._calibration_reason = "calibrated"
        return True

    def resolve(self, text: str) -> TrajectoryPolicyResolution:
        normalized = text.strip().lower()
        tokens = tuple(tokenize(normalized))

        if not self.calibrated:
            return TrajectoryPolicyResolution(
                normalized, "fail_closed", 0.0, self._threshold, self._margin,
                self._calibration_reason, len(tokens),
            )

        unsupported = [token for token in tokens if not self._token_supported(token)]
        if unsupported:
            return TrajectoryPolicyResolution(
                normalized, "fail_closed", 0.0, self._threshold, self._margin,
                "absolute open-set token(s): " + ", ".join(unsupported), len(tokens),
            )

        expected_lengths = {len(pattern) for pattern in self._patterns}
        if len(tokens) not in expected_lengths:
            return TrajectoryPolicyResolution(
                normalized, "reject", self._coverage(tokens), self._threshold, self._margin,
                "trajectory arity mismatch", len(tokens),
            )

        coverage = self._coverage(tokens)
        decision: TrajectoryDecision = "accept" if coverage > self._threshold else "reject"
        reason = "trajectory coverage accepted" if decision == "accept" else "trajectory coverage below boundary"
        return TrajectoryPolicyResolution(
            normalized, decision, coverage, self._threshold, self._margin, reason, len(tokens)
        )
