from pathlib import Path

from memoria_resolutiva.conversation_contract import ConversationIngestResult, ConversationResolveResult
from memoria_resolutiva.conversation_episodic_bridge import AutoEpisodicConversationService
from memoria_resolutiva.product_evidence import ProductEvidenceService
from memoria_resolutiva.product_episodic import ProductEpisodicService
from memoria_resolutiva.reference_conversation import ConversationSemanticService


class FakeConversation:
    def __init__(self, result: ConversationIngestResult):
        self.result = result
        self.calls = []

    def ingest(self, **kwargs):
        self.calls.append(kwargs)
        return self.result

    def resolve(self, *, query: str, session_id: str | None = None):
        return ConversationResolveResult("UNRESOLVED", 0.0, (), "", (), ())


class FakeEpisodes:
    def __init__(self):
        self.requests = []

    def store_derived(self, request):
        self.requests.append(request)
        return object(), object()

    def history(self, *, session_id=None, event_type=None, limit=1000):
        return [{"episode_id": request.episode_id} for request in self.requests]


def _relation(confidence=0.95):
    return {
        "subject": "carro",
        "predicate": "is",
        "object": "Jeep",
        "memory_id": "r1",
        "confidence": confidence,
        "epoch": 1,
        "namespace": "s",
    }


def test_user_fact_forms_derived_episode_and_fills_missing_timestamp():
    conversation = FakeConversation(ConversationIngestResult(("turn1", "r1"), (_relation(),), False))
    episodes = FakeEpisodes()
    service = AutoEpisodicConversationService(conversation, episodes, clock=lambda: "2026-09-03T22:00:00.000Z")

    result = service.ingest(role="user", text="meu carro é Jeep", session_id="s", order=1)

    assert result.memory_ids[0] == "turn1"
    assert conversation.calls[0]["timestamp"] == "2026-09-03T22:00:00.000Z"
    assert len(episodes.requests) == 1
    episode = episodes.requests[0]
    assert episode.episode_id == "episode:auto:turn1"
    assert episode.parent_memory_ids == ["turn1"]
    assert episode.event_type == "assertion"
    assert episode.timestamp == "2026-09-03T22:00:00.000Z"
    assert episode.topics == ["carro", "Jeep"]


def test_assistant_question_low_confidence_and_missing_order_do_not_form_episode():
    cases = [
        dict(role="assistant", text="meu carro é Jeep", order=1, result=ConversationIngestResult(("a", "r"), (_relation(),), False)),
        dict(role="user", text="qual carro é Jeep?", order=1, result=ConversationIngestResult(("q", "r"), (_relation(),), False)),
        dict(role="user", text="meu carro é Jeep", order=1, result=ConversationIngestResult(("weak", "r"), (_relation(0.60),), False)),
        dict(role="user", text="meu carro é Jeep", order=None, result=ConversationIngestResult(("no-order", "r"), (_relation(),), False)),
    ]
    for case in cases:
        episodes = FakeEpisodes()
        service = AutoEpisodicConversationService(FakeConversation(case["result"]), episodes, clock=lambda: "2026-09-03T22:00:00Z")
        service.ingest(role=case["role"], text=case["text"], session_id="s", order=case["order"])
        assert episodes.requests == []


def test_retry_is_idempotent_for_automatic_episode():
    result = ConversationIngestResult(("turn1", "r1"), (_relation(),), False)
    episodes = FakeEpisodes()
    service = AutoEpisodicConversationService(FakeConversation(result), episodes, clock=lambda: "2026-09-03T22:00:00Z")

    service.ingest(role="user", text="meu carro é Jeep", session_id="s", order=1)
    service.ingest(role="user", text="meu carro é Jeep", session_id="s", order=1)

    assert [request.episode_id for request in episodes.requests] == ["episode:auto:turn1"]


def _python_services(root: Path):
    evidence = ProductEvidenceService.open(root, backend="sqlite", allow_fallback=True)
    conversation = ConversationSemanticService(evidence)
    episodes = ProductEpisodicService(evidence)
    return evidence, AutoEpisodicConversationService(conversation, episodes), episodes


def test_python_persistence_forms_episode_with_turn_as_factual_root(tmp_path: Path):
    root = tmp_path / "evidence"
    _evidence, service, episodes = _python_services(root)

    result = service.ingest(
        role="user",
        text="meu carro é Jeep",
        session_id="chat",
        order=1,
        timestamp="2026-09-03T22:01:00Z",
    )
    turn_id = result.memory_ids[0]
    history = episodes.history(session_id="chat")
    assert len(history) == 1
    assert history[0]["source_type"] == "derived_relation"
    assert history[0]["ultimate_source_memory_id"] == turn_id
    assert history[0]["timestamp"] == "2026-09-03T22:01:00Z"

    _evidence2, _service2, restarted_episodes = _python_services(root)
    again = restarted_episodes.history(session_id="chat")
    assert len(again) == 1
    assert again[0]["ultimate_source_memory_id"] == turn_id


def test_assistant_generated_turn_never_becomes_automatic_episode(tmp_path: Path):
    _evidence, service, episodes = _python_services(tmp_path / "evidence")
    service.ingest(role="assistant", text="meu carro é Renegade", session_id="chat", order=1)
    assert episodes.history(session_id="chat") == []
