from memoria_resolutiva.context_compiler_v2 import ContextCompilerV2
from memoria_resolutiva.resolutive_inference_v2 import ResolutiveInferenceEngineV2
from memoria_resolutiva.evolving_address_state_v2 import EvolvingAddressStateJournalV2
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



def test_context_compiler_v2_compiles_current_previous_change_without_language_rules():
    index = _index([("trajectory", [1, 2, 3])])
    journal = EvolvingAddressStateJournalV2()
    journal.append(
        77, hierarchy_id="r10", sequence=1, payload_addresses=[700],
        trajectory_ids=["t:old"], provenance_ids=["p:old"],
    )
    journal.append(
        77, hierarchy_id="r10", sequence=2, payload_addresses=[800],
        trajectory_ids=["t:new"], provenance_ids=["p:new"],
    )
    engine = ResolutiveInferenceEngineV2(index, state_reader=journal)

    current = ContextCompilerV2.compile_temporal(
        engine.infer_temporal_state(77, hierarchy_id="r10", operation="current")
    )
    previous = ContextCompilerV2.compile_temporal(
        engine.infer_temporal_state(77, hierarchy_id="r10", operation="previous")
    )
    change = ContextCompilerV2.compile_temporal(
        engine.infer_temporal_state(77, hierarchy_id="r10", operation="change")
    )

    assert current.payload_addresses == (800,)
    assert previous.payload_addresses == (700,)
    assert change.previous_payload_addresses == (700,)
    assert change.payload_addresses == (800,)
    assert change.removed_addresses == (700,)
    assert change.added_addresses == (800,)
    assert current.external_calls == previous.external_calls == change.external_calls == 0
    assert current.llm_calls == previous.llm_calls == change.llm_calls == 0
    assert current.semantic_projection is previous.semantic_projection is change.semantic_projection is False
