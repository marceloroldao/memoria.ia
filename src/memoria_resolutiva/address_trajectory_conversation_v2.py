from __future__ import annotations

from dataclasses import dataclass

from .address_trajectory_v2 import AddressTrajectoryMemory, TrajectoryMatch


@dataclass(frozen=True, slots=True)
class AddressTrajectoryResolveResultV2:
    status: str
    confidence: float
    selected_context: str
    trajectory_ids: tuple[str, ...] = ()


def _evidence_key(match: TrajectoryMatch) -> tuple[int, int, int, int, int]:
    """Structural evidence only; excludes the deterministic trajectory-id tie-break."""
    return (
        match.query_coverage_num,
        -max(match.query_coverage_den, 1),
        match.ordered_overlap,
        match.adjacency_overlap,
        match.overlap,
    )


class AddressTrajectoryConversationResolverV2:
    """Conversation-compatible V2 adapter with no semantic vocabulary.

    Ingestion and query use AddressTrajectoryMemory's same mechanical decomposition.
    A result is exposed only when the best stored trajectory has strictly stronger
    structural evidence than every competitor. Equal structural evidence remains
    unresolved instead of being broken by trajectory id or a language-specific rule.
    """

    def __init__(self, memory: AddressTrajectoryMemory, *, limit: int = 8) -> None:
        if limit < 2:
            raise ValueError("limit must be >= 2")
        self.memory = memory
        self.limit = limit

    def resolve(self, *, query: str, session_id: str | None = None) -> AddressTrajectoryResolveResultV2:
        del session_id  # Namespace persistence is a later integration boundary.
        matches = self.memory.resolve(query, limit=self.limit)
        if not matches:
            return AddressTrajectoryResolveResultV2("UNRESOLVED", 0.0, "")

        best_key = _evidence_key(matches[0])
        leaders = tuple(match for match in matches if _evidence_key(match) == best_key)
        if len(leaders) != 1:
            return AddressTrajectoryResolveResultV2(
                "UNRESOLVED",
                0.0,
                "",
                tuple(match.trajectory_id for match in leaders),
            )

        winner = leaders[0]
        selected = (winner.terminal_surface or winner.raw_text or "").strip()
        if not selected:
            return AddressTrajectoryResolveResultV2("UNRESOLVED", 0.0, "")

        return AddressTrajectoryResolveResultV2(
            "HIT",
            1.0,
            selected,
            (winner.trajectory_id,),
        )
