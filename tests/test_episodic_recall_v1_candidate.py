from memoria_resolutiva.episodic_recall import Episode, EpisodicRecallService
from memoria_resolutiva.evidence_core import EvidenceCore


def test_latest_matching_episode_is_selected_without_domain_rules():
    core = EvidenceCore()
    svc = EpisodicRecallService(core)
    svc.record(Episode("e1", "assistant", "Primeira criação sobre transporte urbano", "s", 1, "2026-08-28T10:00:00Z", "creation", ("transporte",)))
    svc.record(Episode("e2", "user", "vamos falar de outra coisa", "s", 2, None))
    svc.record(Episode("e3", "assistant", "Segunda criação sobre transporte urbano", "s", 3, "2026-08-28T10:05:00Z", "creation", ("transporte",)))
    result = svc.recall_latest(query="qual foi a última criação sobre transporte?", namespace="s", role="assistant", event_type="creation", topics=("transporte",))
    assert result.status == "HIT"
    assert result.episode_ids == ("e3",)
    assert result.selected_context == "Segunda criação sobre transporte urbano"
    assert result.order == 3
    assert result.source_type == "assistant_generated"


def test_different_topics_do_not_cross_contaminate():
    core = EvidenceCore()
    svc = EpisodicRecallService(core)
    svc.record(Episode("north", "assistant", "Relatório do laboratório Norte", "s", 1, None, "report", ("laboratório norte",)))
    svc.record(Episode("south", "assistant", "Relatório do laboratório Sul", "s", 2, None, "report", ("laboratório sul",)))
    result = svc.recall_latest(query="último relatório do laboratório norte", namespace="s", event_type="report", topics=("laboratório norte",))
    assert result.status == "HIT"
    assert result.episode_ids == ("north",)


def test_ambiguous_same_order_query_abstains():
    core = EvidenceCore()
    svc = EpisodicRecallService(core)
    svc.record(Episode("a", "assistant", "nota alfa", "s", 4, None, "note", ("alfa",)))
    svc.record(Episode("b", "assistant", "nota beta", "s", 4, None, "note", ("beta",)))
    result = svc.recall_latest(query="qual foi a última nota?", namespace="s", event_type="note")
    assert result.status == "UNRESOLVED"


def test_replay_restart_preserves_temporal_and_provenance_selection():
    core = EvidenceCore()
    svc = EpisodicRecallService(core)
    svc.record(Episode("m1", "assistant", "Resumo antigo do projeto Atlas", "s", 1, None, "summary", ("atlas",)))
    svc.record(Episode("m2", "assistant", "Resumo novo do projeto Atlas", "s", 9, None, "summary", ("atlas",)))
    replay = EvidenceCore()
    for edge in core.active_edges(namespace="s"):
        replay.observe_relation(edge.subject, edge.predicate, edge.object, evidence_id=edge.evidence_id, source_text=edge.source_text, provenance=edge.provenance, origin=edge.origin, confidence=edge.confidence, namespace=edge.namespace, epoch=edge.epoch)
    result = EpisodicRecallService(replay).recall_latest(query="último resumo do Atlas", namespace="s", event_type="summary", topics=("atlas",))
    assert result.status == "HIT"
    assert result.episode_ids == ("m2",)
    assert result.source_type == "assistant_generated"


def test_assistant_episode_with_parent_exposes_ultimate_user_source():
    core = EvidenceCore()
    svc = EpisodicRecallService(core)
    svc.record(Episode("u1", "user", "tema definido para o projeto Boreal", "s", 1, None, "instruction", ("boreal",)))
    svc.record(Episode("a1", "assistant", "Síntese do projeto Boreal", "s", 2, None, "summary", ("boreal",), ("u1",)))
    result = svc.recall_latest(query="último resumo do Boreal", namespace="s", event_type="summary", topics=("boreal",))
    assert result.status == "HIT"
    assert result.episode_ids == ("a1",)
    assert result.source_type == "user_assertion"
    assert result.ultimate_source_memory_id == "u1"
