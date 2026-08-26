import pytest

from memoria_resolutiva.source_reliability_v115 import (
    SourceReliabilityCorroborationMemoryV115,
)


def confirm_many(mem, origin, prefix, count):
    for i in range(count):
        mem.adjudicate_origin(
            origin,
            resolution_id=f"{prefix}-confirm-{i}",
            confirmed=True,
            adjudicator_origins=(f"judge-{prefix}-{i}",),
        )


def contradict_many(mem, origin, prefix, count):
    for i in range(count):
        mem.adjudicate_origin(
            origin,
            resolution_id=f"{prefix}-contradict-{i}",
            confirmed=False,
            adjudicator_origins=(f"judge-{prefix}-{i}",),
        )


def test_v115_observation_does_not_auto_confirm_its_origin():
    mem = SourceReliabilityCorroborationMemoryV115()
    mem.observe(
        "A fonte Delta alimenta o controlador.",
        provenance="channel-a",
        origin="origin-a",
        confidence=0.9,
    )
    assert mem.infer_path("Delta", "controlador").inferred
    assert mem.origin_reliability("origin-a") == 0.5
    assert mem.origin_evidence_count("origin-a") == 0.0


def test_v115_external_adjudication_updates_origin_reliability():
    mem = SourceReliabilityCorroborationMemoryV115()
    before = mem.origin_reliability("origin-a")
    mem.adjudicate_origin(
        "origin-a",
        resolution_id="resolution-1",
        confirmed=True,
        adjudicator_origins=("independent-judge",),
    )
    assert mem.origin_reliability("origin-a") > before
    assert mem.origin_evidence_count("origin-a") == 1.0


def test_v115_origin_cannot_adjudicate_itself():
    mem = SourceReliabilityCorroborationMemoryV115()
    with pytest.raises(ValueError, match="cannot adjudicate its own"):
        mem.adjudicate_origin(
            "origin-a",
            resolution_id="resolution-1",
            confirmed=True,
            adjudicator_origins=("origin-a",),
        )
    assert mem.origin_evidence_count("origin-a") == 0.0


def test_v115_resolution_id_cannot_stack_reputation_twice():
    mem = SourceReliabilityCorroborationMemoryV115()
    mem.adjudicate_origin(
        "origin-a",
        resolution_id="resolution-1",
        confirmed=True,
        adjudicator_origins=("judge-a",),
    )
    with pytest.raises(ValueError, match="already been applied"):
        mem.adjudicate_origin(
            "origin-a",
            resolution_id="resolution-1",
            confirmed=True,
            adjudicator_origins=("judge-b",),
        )
    assert mem.origin_evidence_count("origin-a") == 1.0


def test_v115_reliability_gate_does_not_replace_independent_origin_gate():
    mem = SourceReliabilityCorroborationMemoryV115()
    confirm_many(mem, "good-a", "ga", 8)
    contradict_many(mem, "weak-b", "wb", 8)
    mem.observe(
        "A fonte Delta alimenta o controlador.",
        provenance="p-a",
        origin="good-a",
        confidence=0.9,
        epoch=0,
    )
    mem.observe(
        "A fonte Delta alimenta o controlador.",
        provenance="p-b",
        origin="weak-b",
        confidence=0.9,
        epoch=1,
    )

    assert mem.infer_path(
        "Delta",
        "controlador",
        min_independent_origins=2,
    ).inferred
    assert not mem.infer_path(
        "Delta",
        "controlador",
        min_independent_origins=2,
        min_origin_reliability=0.6,
    ).inferred

    confirm_many(mem, "good-c", "gc", 8)
    mem.observe(
        "A fonte Delta alimenta o controlador.",
        provenance="p-c",
        origin="good-c",
        confidence=0.9,
        epoch=2,
    )
    assert mem.infer_path(
        "Delta",
        "controlador",
        min_independent_origins=2,
        min_origin_reliability=0.6,
    ).inferred


def test_v115_explicit_confidence_and_reliability_remain_separate_gates():
    mem = SourceReliabilityCorroborationMemoryV115()
    confirm_many(mem, "trusted", "trusted", 10)
    mem.observe(
        "A fonte Delta alimenta o controlador.",
        provenance="trusted-channel",
        origin="trusted",
        confidence=0.4,
    )
    assert not mem.infer_path(
        "Delta",
        "controlador",
        min_confidence=0.5,
        min_origin_reliability=0.6,
    ).inferred

    mem2 = SourceReliabilityCorroborationMemoryV115()
    contradict_many(mem2, "unreliable", "unreliable", 10)
    mem2.observe(
        "A fonte Delta alimenta o controlador.",
        provenance="unreliable-channel",
        origin="unreliable",
        confidence=0.95,
    )
    assert not mem2.infer_path(
        "Delta",
        "controlador",
        min_confidence=0.9,
        min_origin_reliability=0.6,
    ).inferred


def test_v115_wilson_gate_is_more_conservative_for_little_history():
    mem = SourceReliabilityCorroborationMemoryV115()
    mem.adjudicate_origin(
        "small-history",
        resolution_id="small-1",
        confirmed=True,
        adjudicator_origins=("judge-small",),
    )
    posterior = mem.origin_reliability("small-history", metric="posterior")
    wilson = mem.origin_reliability("small-history", metric="wilson")
    assert posterior > wilson

    mem.observe(
        "A fonte Delta alimenta o controlador.",
        provenance="small-channel",
        origin="small-history",
        confidence=0.9,
    )
    assert mem.infer_path(
        "Delta",
        "controlador",
        min_origin_reliability=0.6,
        reliability_metric="posterior",
    ).inferred
    assert not mem.infer_path(
        "Delta",
        "controlador",
        min_origin_reliability=0.6,
        reliability_metric="wilson",
    ).inferred


def test_v115_multihop_path_reliability_is_limited_by_weakest_edge():
    mem = SourceReliabilityCorroborationMemoryV115()
    confirm_many(mem, "origin-a", "oa", 10)
    confirm_many(mem, "origin-b", "ob", 2)
    mem.observe(
        "A fonte Delta alimenta o controlador.",
        provenance="p-a",
        origin="origin-a",
        confidence=0.95,
        epoch=0,
    )
    mem.observe(
        "O controlador controlador pertence ao Orion.",
        provenance="p-b",
        origin="origin-b",
        confidence=0.90,
        epoch=1,
    )

    result = mem.infer_path("Delta", "Orion")
    assert result.inferred
    path = result.paths[0]
    assert path.reliability_floor == min(path.edge_reliabilities)
    assert path.confidence == 0.90
    assert path.independent_origin_floor == 1


def test_v115_namespace_isolation_is_preserved():
    mem = SourceReliabilityCorroborationMemoryV115()
    confirm_many(mem, "origin-a", "na", 5)
    mem.observe(
        "A fonte Delta alimenta o controlador.",
        provenance="p-a",
        origin="origin-a",
        namespace="alpha",
    )
    assert mem.infer_path("Delta", "controlador", namespace="alpha").inferred
    assert not mem.infer_path("Delta", "controlador", namespace="beta").inferred
