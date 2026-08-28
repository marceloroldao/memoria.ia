import pytest

from memoria_resolutiva.evidence_core import EvidenceCore


def add(mem, s, p, o, eid, *, ns=None, epoch=None, origin=None, provenance="conversation", confidence=1.0):
    return mem.observe_relation(
        s, p, o,
        evidence_id=eid,
        source_text=f"{s} {p} {o}",
        namespace=ns,
        epoch=epoch,
        origin=origin,
        provenance=provenance,
        confidence=confidence,
    )


def test_structural_path_is_source_backed_and_never_synthesizes_claim():
    mem = EvidenceCore()
    add(mem, "Delta", "powers", "controlador", "m1")
    add(mem, "controlador", "belongs_to", "Orion", "m2")
    result = mem.infer_path("Delta", "Orion")
    assert result.inferred
    path = result.paths[0]
    assert path.predicates == ("powers", "belongs_to")
    assert path.evidence_ids == ("m1", "m2")
    assert path.kind == "evidence_path"
    assert path.synthesized_claims == 0
    assert result.unsupported_claims == 0


def test_namespace_is_strict_and_default_is_not_wildcard():
    mem = EvidenceCore()
    add(mem, "Delta", "powers", "controlador", "m1", ns="a")
    add(mem, "controlador", "belongs_to", "Orion", "m2", ns="b")
    assert not mem.infer_path("Delta", "Orion", namespace="a").inferred
    assert not mem.infer_path("Delta", "Orion", namespace="b").inferred
    assert not mem.infer_path("Delta", "Orion").inferred


def test_latest_epoch_supersedes_single_value_relation():
    mem = EvidenceCore()
    add(mem, "Delta", "belongs_to", "Orion", "m1", epoch=0)
    add(mem, "Delta", "belongs_to", "Vega", "m2", epoch=1)
    assert mem.infer_path("Delta", "Orion", epoch=0).inferred
    assert not mem.infer_path("Delta", "Orion").inferred
    assert mem.infer_path("Delta", "Vega").inferred


def test_same_epoch_single_value_conflict_abstains():
    mem = EvidenceCore()
    add(mem, "Delta", "belongs_to", "Orion", "m1", epoch=3)
    add(mem, "Delta", "belongs_to", "Vega", "m2", epoch=3)
    conflicts = mem.conflicts()
    assert len(conflicts) == 1
    assert set(conflicts[0].values) == {"Orion", "Vega"}
    assert not mem.infer_path("Delta", "Orion").inferred
    assert not mem.infer_path("Delta", "Vega").inferred


def test_multivalued_relation_is_not_false_conflict():
    mem = EvidenceCore()
    add(mem, "Delta", "powers", "controlador", "m1", epoch=2)
    add(mem, "Delta", "powers", "sensor", "m2", epoch=2)
    assert not mem.conflicts()
    assert mem.infer_path("Delta", "controlador").inferred
    assert mem.infer_path("Delta", "sensor").inferred


def test_confidence_gate_keeps_weak_edge_visible_only_when_allowed():
    mem = EvidenceCore()
    add(mem, "Delta", "powers", "controlador", "m1", confidence=0.9)
    add(mem, "controlador", "belongs_to", "Orion", "m2", confidence=0.4)
    assert mem.infer_path("Delta", "Orion", min_confidence=0.3).inferred
    assert not mem.infer_path("Delta", "Orion", min_confidence=0.5).inferred
    path = mem.infer_path("Delta", "Orion", min_confidence=0.3).paths[0]
    assert path.confidence == 0.4


def test_repeated_same_origin_does_not_count_as_independent_corroboration():
    mem = EvidenceCore()
    add(mem, "Delta", "powers", "controlador", "m1", origin="report-a")
    add(mem, "Delta", "powers", "controlador", "m2", origin="report-a")
    assert not mem.infer_path("Delta", "controlador", min_independent_origins=2).inferred
    add(mem, "Delta", "powers", "controlador", "m3", origin="report-b", epoch=1)
    # latest epoch is authoritative for this logical slot, so provide both independent
    # observations in the same latest epoch.
    add(mem, "Delta", "powers", "controlador", "m4", origin="report-a", epoch=1)
    assert mem.infer_path("Delta", "controlador", min_independent_origins=2).inferred


def test_reliability_changes_only_through_explicit_external_adjudication():
    mem = EvidenceCore()
    add(mem, "Delta", "powers", "controlador", "m1", origin="sensor-a")
    before = mem.origin_reliability("sensor-a")
    mem.infer_path("Delta", "controlador")
    assert mem.origin_reliability("sensor-a") == before
    mem.adjudicate_origin(
        "sensor-a",
        resolution_id="r1",
        confirmed=True,
        adjudicator_origins=("auditor-b",),
    )
    assert mem.origin_reliability("sensor-a") > before


def test_reliability_replay_self_adjudication_and_cycles_are_rejected():
    mem = EvidenceCore()
    mem.adjudicate_origin("b", resolution_id="r1", confirmed=True, adjudicator_origins=("a",))
    with pytest.raises(ValueError, match="already been applied"):
        mem.adjudicate_origin("b", resolution_id="r1", confirmed=True, adjudicator_origins=("c",))
    with pytest.raises(ValueError, match="cannot adjudicate"):
        mem.adjudicate_origin("x", resolution_id="r2", confirmed=True, adjudicator_origins=("x",))
    with pytest.raises(ValueError, match="cycle"):
        mem.adjudicate_origin("a", resolution_id="r3", confirmed=True, adjudicator_origins=("b",))


def test_reliability_gate_can_reject_low_reliability_origin():
    mem = EvidenceCore()
    add(mem, "Delta", "powers", "controlador", "m1", origin="sensor-a")
    mem.adjudicate_origin("sensor-a", resolution_id="r1", confirmed=False, adjudicator_origins=("auditor",), weight=4.0)
    assert not mem.infer_path("Delta", "controlador", min_origin_reliability=0.5).inferred
