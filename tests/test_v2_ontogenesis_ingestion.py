from memoria_resolutiva.evidence_core import EvidenceCore
from memoria_resolutiva.v2_ontogenesis import V2OntogenesisIngestor


def test_v2_raw_ingestion_preserves_recurrence_and_competing_observations_without_phrase_rules():
    core = EvidenceCore()
    ingest = V2OntogenesisIngestor(core)

    first = ingest.observe("Hoje me acordei feliz.", namespace="wake")
    second = ingest.observe("Hoje me acordei triste.", namespace="wake")
    third = ingest.observe("Hoje me acordei feliz.", namespace="wake")

    assert [first.order, second.order, third.order] == [0, 1, 2]
    assert first.tokens == ("hoje", "me", "acordei", "feliz")
    assert second.tokens == ("hoje", "me", "acordei", "triste")
    assert third.tokens == first.tokens
    assert len({first.episode_id, second.episode_id, third.episode_id}) == 3

    # Raw observations are immutable episodes: recurrence does not overwrite.
    episodes = ingest.episodes.episodes(namespace="wake")
    assert [e.text for e in episodes] == [
        "Hoje me acordei feliz.",
        "Hoje me acordei triste.",
        "Hoje me acordei feliz.",
    ]

    history = core.evidence_history(namespace="wake")
    next_edges = [e for e in history if e.predicate == ingest.NEXT_PREDICATE]

    # Shared lexical structure is represented by the same canonical token values.
    assert sum(e.subject == "hoje" and e.object == "me" for e in next_edges) == 3
    assert sum(e.subject == "me" and e.object == "acordei" for e in next_edges) == 3

    # Competing continuations coexist and recurrence becomes repeated evidence.
    assert sum(e.subject == "acordei" and e.object == "feliz" for e in next_edges) == 2
    assert sum(e.subject == "acordei" and e.object == "triste" for e in next_edges) == 1


def test_v2_ingestion_is_generic_not_hardcoded_to_waking_example():
    core = EvidenceCore()
    ingest = V2OntogenesisIngestor(core)
    result = ingest.observe("Sensor temperatura subiu rapidamente.", namespace="sensor")
    assert result.tokens == ("sensor", "temperatura", "subiu", "rapidamente")
    history = core.evidence_history(namespace="sensor")
    assert any(e.subject == "temperatura" and e.predicate == "next_token" and e.object == "subiu" for e in history)
