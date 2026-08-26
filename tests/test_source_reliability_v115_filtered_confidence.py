from memoria_resolutiva.source_reliability_v115 import (
    SourceReliabilityCorroborationMemoryV115,
)


def test_v115_reported_confidence_ignores_reliability_filtered_origin():
    mem = SourceReliabilityCorroborationMemoryV115()
    for i in range(8):
        mem.adjudicate_origin(
            "trusted",
            resolution_id=f"trusted-{i}",
            confirmed=True,
            adjudicator_origins=(f"judge-t-{i}",),
        )
        mem.adjudicate_origin(
            "unreliable",
            resolution_id=f"unreliable-{i}",
            confirmed=False,
            adjudicator_origins=(f"judge-u-{i}",),
        )

    mem.observe(
        "A fonte Delta alimenta o controlador.",
        provenance="trusted-channel",
        origin="trusted",
        confidence=0.70,
        epoch=0,
    )
    mem.observe(
        "A fonte Delta alimenta o controlador.",
        provenance="unreliable-channel",
        origin="unreliable",
        confidence=0.99,
        epoch=1,
    )

    result = mem.infer_path(
        "Delta",
        "controlador",
        min_origin_reliability=0.6,
    )
    assert result.inferred
    assert result.paths[0].origins_by_edge == (("trusted",),)
    assert result.paths[0].confidence == 0.70
    assert result.paths[0].edge_confidences == (0.70,)
