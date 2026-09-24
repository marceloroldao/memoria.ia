from __future__ import annotations

from dataclasses import dataclass

from memoria_resolutiva.evolving_address_state_v2 import EvolvingAddressStateJournalV2
from memoria_resolutiva.resolutive_inference_v2 import ResolutiveInferenceEngineV2
from memoria_resolutiva.structural_branch_state_v2 import DynamicStructuralBranchResolverV2
from memoria_resolutiva.structural_equivalence_v2 import StructuralReformulationV2
from memoria_resolutiva.structural_trajectory_v2 import StructuralTrajectoryIndex


def _index(rows, *, hierarchy_id="h"):
    index = StructuralTrajectoryIndex()
    for sequence, row in enumerate(rows):
        if len(row) == 2:
            source_id, addresses = row
            observation_id = f"obs:{sequence}"
        else:
            source_id, addresses, observation_id = row
        index.ingest_addresses(
            addresses,
            hierarchy_id=hierarchy_id,
            source_id=source_id,
            sequence=sequence,
            observation_id=observation_id,
        )
    return index


def test_direct_attractor_resolves_and_exposes_provenance_without_external_calls():
    index = _index([
        ("a", [1, 2, 3], "obs:a"),
        ("b", [1, 2, 3], "obs:b"),
        ("c", [1, 2, 4], "obs:c"),
    ])
    before = index.snapshot()
    engine = ResolutiveInferenceEngineV2(index)

    result = engine.infer_structural([1, 2], hierarchy_id="h")

    assert result.status == "resolved"
    assert result.source_tier == "direct-attractor"
    assert result.resolved_address == 3
    assert result.supporting_trajectory_ids
    assert result.provenance_ids == ("obs:a", "obs:b")
    assert result.diagnostics.external_calls == 0
    assert result.diagnostics.llm_calls == 0
    assert result.diagnostics.semantic_projection is False
    assert index.snapshot() == before


def test_equal_direct_evidence_remains_ambiguous():
    index = _index([
        ("a", [1, 2, 3]),
        ("b", [1, 2, 4]),
    ])
    engine = ResolutiveInferenceEngineV2(index)

    result = engine.infer_structural([1, 2], hierarchy_id="h")

    assert result.status == "ambiguous"
    assert result.source_tier == "direct-attractor"
    assert result.resolved_address is None
    assert result.competing_addresses == (3, 4)
    assert "direct-structural-ambiguity" in result.conflicts


def test_direct_terminal_is_preserved_as_terminal_not_rewritten():
    index = _index([
        ("a", [1, 2]),
        ("b", [1, 2]),
    ])
    engine = ResolutiveInferenceEngineV2(index)

    result = engine.infer_structural([1, 2], hierarchy_id="h")

    assert result.status == "terminal"
    assert result.terminal is True
    assert result.resolved_address is None
    assert result.source_tier == "direct-attractor"


def test_supported_equivalence_is_evaluated_as_secondary_diagnostic_only():
    index = _index([
        ("L1", [1, 10, 11, 99]),
        ("L2", [2, 10, 11, 99]),
        ("L3", [1, 10, 11, 99]),
        ("L4", [2, 10, 11, 99]),
    ])
    engine = ResolutiveInferenceEngineV2(index)

    result = engine.infer_structural([1], hierarchy_id="h")

    assert result.status == "resolved"
    assert result.source_tier == "direct-attractor"
    assert result.resolved_address == 10
    assert result.diagnostics.supported_equivalences >= 1
    assert result.equivalent_attempts
    assert all(
        attempt.attractor.resolved_address == 10
        for attempt in result.equivalent_attempts
        if attempt.attractor.resolved
    )
    assert result.equivalence_witness_ids


@dataclass(frozen=True)
class _FakeEquivalenceCandidate:
    state: str
    supporting_witness_ids: tuple[str, ...]


class _FakeSnapshot:
    def candidate_by_pair(self, left, right):
        return _FakeEquivalenceCandidate("supported", ("w:1", "w:2"))


class _FakeEquivalence:
    def reformulate_addresses(self, addresses, *, hierarchy_id):
        query = tuple(addresses)
        return (
            StructuralReformulationV2(
                signature_id="direct",
                addresses=query,
                direct=True,
                equivalence_state="direct",
                independent_convergence=0,
                independent_divergence=0,
            ),
            StructuralReformulationV2(
                signature_id="alternate",
                addresses=(50,),
                direct=False,
                equivalence_state="supported",
                independent_convergence=2,
                independent_divergence=0,
            ),
        )

    def snapshot(self, *, hierarchy_id):
        return _FakeSnapshot()


def test_equivalence_fallback_can_resolve_only_when_direct_is_unresolved():
    index = _index([
        ("alt-a", [50, 60]),
        ("alt-b", [50, 60]),
    ])
    engine = ResolutiveInferenceEngineV2(index)
    engine.equivalence = _FakeEquivalence()

    result = engine.infer_structural([999], hierarchy_id="h")

    assert result.direct_attractor.resolved is False
    assert result.direct_attractor.ambiguous is False
    assert result.status == "resolved"
    assert result.source_tier == "equivalent-attractor"
    assert result.resolved_address == 60
    assert result.equivalence_witness_ids == ("w:1", "w:2")


def test_equivalence_fallback_cannot_override_direct_ambiguity():
    index = _index([
        ("direct-a", [1, 2, 3]),
        ("direct-b", [1, 2, 4]),
        ("alt-a", [50, 60]),
        ("alt-b", [50, 60]),
    ])
    engine = ResolutiveInferenceEngineV2(index)
    engine.equivalence = _FakeEquivalence()

    result = engine.infer_structural([1, 2], hierarchy_id="h")

    assert result.status == "ambiguous"
    assert result.source_tier == "direct-attractor"
    assert result.resolved_address is None
    assert result.competing_addresses == (3, 4)


def test_temporal_state_uses_same_zero_llm_inference_surface():
    index = _index([("a", [1, 2, 3])])
    journal = EvolvingAddressStateJournalV2()
    journal.append(
        42,
        hierarchy_id="h",
        sequence=10,
        payload_addresses=[100],
        trajectory_ids=["t1"],
        provenance_ids=["p1"],
    )
    journal.append(
        42,
        hierarchy_id="h",
        sequence=20,
        payload_addresses=[200],
        trajectory_ids=["t2"],
        provenance_ids=["p2"],
    )
    engine = ResolutiveInferenceEngineV2(index, state_reader=journal)

    result = engine.infer_temporal_state(
        42,
        hierarchy_id="h",
        operation="change",
    )

    assert result.status == "resolved"
    assert result.temporal.change is not None
    assert result.temporal.change.removed_addresses == (100,)
    assert result.temporal.change.added_addresses == (200,)
    assert result.supporting_trajectory_ids == ("t1", "t2")
    assert result.provenance_ids == ("p1", "p2")
    assert result.external_calls == 0
    assert result.llm_calls == 0


def test_temporal_state_requires_explicit_state_reader():
    index = _index([("a", [1, 2, 3])])
    engine = ResolutiveInferenceEngineV2(index)

    try:
        engine.infer_temporal_state(
            42,
            hierarchy_id="h",
            operation="current",
        )
    except RuntimeError as exc:
        assert "state_reader" in str(exc)
    else:
        raise AssertionError("missing state_reader must fail")


def test_branch_possibilities_share_inference_surface_without_becoming_history():
    index = _index([
        ("a", [1, 2, 3]),
        ("b", [1, 2, 4]),
    ])
    state = DynamicStructuralBranchResolverV2(index).begin_addresses(
        [1, 2],
        hierarchy_id="h",
    )

    result = ResolutiveInferenceEngineV2.infer_temporal_possibilities(state)

    assert result.status == "ambiguous"
    assert {(item.kind, item.address) for item in result.possibilities.outcomes} == {
        ("next-address", 3),
        ("next-address", 4),
    }
    assert result.external_calls == 0
    assert result.llm_calls == 0


def test_hierarchy_isolation_remains_visible_at_inference_surface():
    index = StructuralTrajectoryIndex()
    index.ingest_addresses(
        [1, 2, 3],
        hierarchy_id="left",
        source_id="left",
        sequence=0,
        observation_id="obs:left",
    )
    index.ingest_addresses(
        [1, 2, 4],
        hierarchy_id="right",
        source_id="right",
        sequence=0,
        observation_id="obs:right",
    )
    engine = ResolutiveInferenceEngineV2(index)

    left = engine.infer_structural([1, 2], hierarchy_id="left")
    right = engine.infer_structural([1, 2], hierarchy_id="right")

    assert left.status == "resolved"
    assert left.resolved_address == 3
    assert left.provenance_ids == ("obs:left",)
    assert right.status == "resolved"
    assert right.resolved_address == 4
    assert right.provenance_ids == ("obs:right",)
