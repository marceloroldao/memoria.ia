from memoria_resolutiva.context_compiler_v2 import ContextCompilerV2
from memoria_resolutiva.resolutive_inference_v2 import ResolutiveInferenceEngineV2
from memoria_resolutiva.structural_trajectory_v2 import StructuralTrajectoryIndex


def _index(rows):
    index = StructuralTrajectoryIndex()
    for sequence, (source, addresses) in enumerate(rows):
        index.ingest_addresses(
            addresses,
            hierarchy_id="r10",
            source_id=source,
            sequence=sequence,
            observation_id=f"obs:{source}",
        )
    return index


def test_context_compiler_v2_collapses_resolved_structural_state_without_llm():
    result = ResolutiveInferenceEngineV2(
        _index([("a", [1, 2, 3]), ("b", [1, 2, 3])])
    ).infer_structural([1, 2], hierarchy_id="r10")

    packet = ContextCompilerV2.compile_structural(result)

    assert packet.addresses == (1, 2)
    assert packet.resolved_state == (3,)
    assert packet.competing_states == ()
    assert packet.uncertainty == "resolved"
    assert packet.provenance_ids == ("obs:a", "obs:b")
    assert packet.external_calls == packet.llm_calls == 0
    assert packet.semantic_projection is False
    assert not hasattr(packet, "raw_text")


def test_context_compiler_v2_preserves_conflict_instead_of_forcing_consensus():
    result = ResolutiveInferenceEngineV2(
        _index([("a", [5, 6, 7]), ("b", [5, 6, 8])])
    ).infer_structural([5, 6], hierarchy_id="r10")

    packet = ContextCompilerV2.compile_structural(result)

    assert packet.status == "ambiguous"
    assert packet.resolved_state == ()
    assert packet.competing_states == (7, 8)
    assert packet.uncertainty == "competing-evidence"
    assert "direct-structural-ambiguity" in packet.conflicts


def test_context_compiler_v2_keeps_negative_case_explicit():
    result = ResolutiveInferenceEngineV2(_index([("a", [10, 20, 30])])).infer_structural(
        [999, 1000],
        hierarchy_id="r10",
    )

    packet = ContextCompilerV2.compile_structural(result)

    assert packet.status == "unresolved"
    assert packet.resolved_state == ()
    assert packet.competing_states == ()
    assert packet.uncertainty == "insufficient-evidence"
