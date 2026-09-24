from __future__ import annotations

from dataclasses import dataclass

from .resolutive_inference_v2 import ResolutiveInferenceResultV2


@dataclass(frozen=True, slots=True)
class CognitiveContextPacketV2:
    """Deterministic pre-language cognitive packet.

    The packet contains structural state only. Raw text is deliberately absent from
    the cognitive representation and may be carried separately as provenance/debug
    data by adapters.
    """

    version: int
    hierarchy_id: str
    addresses: tuple[int, ...]
    status: str
    resolved_state: tuple[int, ...]
    competing_states: tuple[int, ...]
    trajectory_ids: tuple[str, ...]
    provenance_ids: tuple[str, ...]
    equivalence_witness_ids: tuple[str, ...]
    conflicts: tuple[str, ...]
    source_tier: str
    terminal: bool
    bounded_out: bool
    uncertainty: str
    external_calls: int = 0
    llm_calls: int = 0
    semantic_projection: bool = False


class ContextCompilerV2:
    """Collapse an inference result into the minimal structured context for a consumer."""

    @staticmethod
    def compile_structural(result: ResolutiveInferenceResultV2) -> CognitiveContextPacketV2:
        resolved = () if result.resolved_address is None else (result.resolved_address,)
        if result.status == "resolved":
            uncertainty = "resolved"
        elif result.status == "ambiguous":
            uncertainty = "competing-evidence"
        elif result.status == "terminal":
            uncertainty = "observed-terminal"
        else:
            uncertainty = "insufficient-evidence"

        return CognitiveContextPacketV2(
            version=2,
            hierarchy_id=result.hierarchy_id,
            addresses=result.query_addresses,
            status=result.status,
            resolved_state=resolved,
            competing_states=result.competing_addresses,
            trajectory_ids=result.supporting_trajectory_ids,
            provenance_ids=result.provenance_ids,
            equivalence_witness_ids=result.equivalence_witness_ids,
            conflicts=result.conflicts,
            source_tier=result.source_tier,
            terminal=result.terminal,
            bounded_out=result.bounded_out,
            uncertainty=uncertainty,
        )
