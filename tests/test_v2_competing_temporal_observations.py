from memoria_resolutiva.evidence_core import EvidenceCore


def test_v2_competing_temporal_observations_preserve_history_and_reinforcement():
    """Acceptance test for non-destructive V2 observation semantics.

    The adapter/parser is deliberately out of scope here. This freezes the
    cognitive storage invariant underneath natural-language ingestion:
    reusable subject/predicate identity, distinct occurrences, competing
    values preserved in history, and recurrence represented as additional
    evidence rather than destructive overwrite.
    """
    core = EvidenceCore()
    observations = (
        ("feliz", "wake-1", "Hoje me acordei feliz."),
        ("triste", "wake-2", "Hoje me acordei triste."),
        ("feliz", "wake-3", "Hoje me acordei feliz."),
    )

    edges = [
        core.observe_relation(
            "eu",
            "acordou_com_estado",
            state,
            evidence_id=evidence_id,
            source_text=source_text,
            provenance="conversation",
            origin="user",
            namespace="v2-acceptance",
        )
        for state, evidence_id, source_text in observations
    ]

    # One reusable structural slot; three occurrence/evidence records.
    assert {(e.subject, e.predicate) for e in edges} == {("eu", "acordou_com_estado")}
    assert [e.epoch for e in edges] == [0, 1, 2]
    assert len({e.evidence_id for e in edges}) == 3

    history = core.evidence_history(namespace="v2-acceptance")
    assert [e.object for e in history] == ["feliz", "triste", "feliz"]
    assert [e.source_text for e in history] == [
        "Hoje me acordei feliz.",
        "Hoje me acordei triste.",
        "Hoje me acordei feliz.",
    ]

    # Neither alternative disappears from memory.
    by_value = {}
    for edge in history:
        by_value.setdefault(edge.object, []).append(edge)
    assert set(by_value) == {"feliz", "triste"}

    # Recurrence reinforces FELIZ through a second independent occurrence,
    # not by creating a new semantic value or erasing TRISTE.
    assert len(by_value["feliz"]) == 2
    assert len(by_value["triste"]) == 1

    # The latest-state projection is allowed to select the latest occurrence,
    # while the complete history remains inspectable.
    active = core.active_edges(namespace="v2-acceptance")
    assert len(active) == 1
    assert active[0].object == "feliz"
    assert active[0].epoch == 2
