import pytest

from memoria_resolutiva.adjudication_cycle_guard_v116 import (
    AdjudicationCycleGuardMemoryV116,
)


def test_v116_rejects_direct_mutual_reputation_cycle():
    mem = AdjudicationCycleGuardMemoryV116()
    mem.adjudicate_origin(
        "b",
        resolution_id="a-validates-b",
        confirmed=True,
        adjudicator_origins=("a",),
    )
    before = mem.origin_evidence_count("a")
    with pytest.raises(ValueError, match="reliability cycle"):
        mem.adjudicate_origin(
            "a",
            resolution_id="b-validates-a",
            confirmed=True,
            adjudicator_origins=("b",),
        )
    assert mem.origin_evidence_count("a") == before
    assert mem.adjudication_path("a", "b") == ("a", "b")
    assert mem.adjudication_path("b", "a") is None


def test_v116_rejects_three_origin_indirect_cycle():
    mem = AdjudicationCycleGuardMemoryV116()
    mem.adjudicate_origin(
        "b",
        resolution_id="a-b",
        confirmed=True,
        adjudicator_origins=("a",),
    )
    mem.adjudicate_origin(
        "c",
        resolution_id="b-c",
        confirmed=True,
        adjudicator_origins=("b",),
    )
    assert mem.adjudication_path("a", "c") == ("a", "b", "c")
    with pytest.raises(ValueError, match=r"a -> b -> c -> a"):
        mem.adjudicate_origin(
            "a",
            resolution_id="c-a",
            confirmed=True,
            adjudicator_origins=("c",),
        )


def test_v116_allows_acyclic_multi_adjudicator_dag():
    mem = AdjudicationCycleGuardMemoryV116()
    mem.adjudicate_origin(
        "target",
        resolution_id="multi-target",
        confirmed=True,
        adjudicator_origins=("judge-b", "judge-a", "judge-a"),
    )
    deps = mem.adjudication_dependencies()
    assert deps["judge-a"] == ("target",)
    assert deps["judge-b"] == ("target",)
    assert mem.origin_evidence_count("target") == 1.0


def test_v116_rejected_cycle_does_not_consume_resolution_id():
    mem = AdjudicationCycleGuardMemoryV116()
    mem.adjudicate_origin(
        "b",
        resolution_id="a-b",
        confirmed=True,
        adjudicator_origins=("a",),
    )
    with pytest.raises(ValueError, match="reliability cycle"):
        mem.adjudicate_origin(
            "a",
            resolution_id="candidate",
            confirmed=True,
            adjudicator_origins=("b",),
        )

    # The same resolution id is still valid for a non-circular adjudication,
    # proving the failed transaction did not partially mutate v1.15 state.
    mem.adjudicate_origin(
        "c",
        resolution_id="candidate",
        confirmed=True,
        adjudicator_origins=("b",),
    )
    assert mem.origin_evidence_count("c") == 1.0


def test_v116_contradictory_adjudications_also_create_dependencies():
    mem = AdjudicationCycleGuardMemoryV116()
    mem.adjudicate_origin(
        "b",
        resolution_id="a-contradicts-b",
        confirmed=False,
        adjudicator_origins=("a",),
    )
    with pytest.raises(ValueError, match="reliability cycle"):
        mem.adjudicate_origin(
            "a",
            resolution_id="b-contradicts-a",
            confirmed=False,
            adjudicator_origins=("b",),
        )


def test_v116_preserves_v115_observation_without_automatic_reputation():
    mem = AdjudicationCycleGuardMemoryV116()
    mem.observe(
        "A fonte Delta alimenta o controlador.",
        provenance="channel-a",
        origin="origin-a",
        confidence=0.9,
    )
    assert mem.infer_path("Delta", "controlador").inferred
    assert mem.origin_reliability("origin-a") == 0.5
    assert mem.origin_evidence_count("origin-a") == 0.0


def test_v116_preserves_v115_reliability_gate():
    mem = AdjudicationCycleGuardMemoryV116()
    for i in range(6):
        mem.adjudicate_origin(
            "trusted",
            resolution_id=f"trusted-{i}",
            confirmed=True,
            adjudicator_origins=(f"judge-{i}",),
        )
    mem.observe(
        "A fonte Delta alimenta o controlador.",
        provenance="trusted-channel",
        origin="trusted",
        confidence=0.8,
    )
    result = mem.infer_path(
        "Delta",
        "controlador",
        min_origin_reliability=0.6,
    )
    assert result.inferred
    assert result.paths[0].confidence == 0.8
