from types import SimpleNamespace

from memoria_resolutiva.concept_aware_conversation import ConceptAwareConversationResolver
from memoria_resolutiva.product_identity import MemoryScope, OrganizationIdentity
from memoria_resolutiva.product_service import EnterpriseMemoryService
from memoria_resolutiva.semantic_concept_store import PersistentSemanticConceptStore
from memoria_resolutiva.semantic_concepts import SemanticConceptIndex


class FakeResolver:
    def __init__(self, responses=None):
        self.responses = responses or {}
        self.calls = []

    def resolve(self, *, query: str, session_id: str | None = None):
        self.calls.append((query, session_id))
        status = self.responses.get(query, "UNRESOLVED")
        return SimpleNamespace(
            status=status,
            confidence=0.8 if status == "HIT" else 0.0,
            memory_ids=("r1",) if status == "HIT" else (),
            selected_context="resolved" if status == "HIT" else "",
            relations=(),
            provenance=(),
        )


def _scope():
    return MemoryScope("org-a", application_id="app", user_id="user", agent_id="agent")


def _store():
    return PersistentSemanticConceptStore(
        EnterpriseMemoryService(OrganizationIdentity("org-a", "Org A"))
    )


def test_index_context_selects_exactly_one_explicit_sense():
    index = SemanticConceptIndex()
    finance = index.register_concept(
        "financial bank",
        aliases=("bank",),
        namespace="en",
        sense_key="finance",
        context_cues=("loan", "money"),
    )
    index.register_concept(
        "river bank",
        aliases=("bank",),
        namespace="en",
        sense_key="geography",
        context_cues=("river", "water"),
    )

    result = index.resolve_with_context("bank", "bank loan approval", namespace="en")
    assert result.status == "HIT"
    assert result.concept_id == finance.concept_id
    assert result.reason == "context_cue"


def test_index_context_without_cue_remains_ambiguous():
    index = SemanticConceptIndex()
    index.register_concept(
        "financial bank", aliases=("bank",), namespace="en", sense_key="finance", context_cues=("loan",)
    )
    index.register_concept(
        "river bank", aliases=("bank",), namespace="en", sense_key="geography", context_cues=("river",)
    )

    result = index.resolve_with_context("bank", "bank status", namespace="en")
    assert result.status == "UNRESOLVED"
    assert result.reason == "ambiguous"


def test_index_competing_context_cues_fail_closed():
    index = SemanticConceptIndex()
    index.register_concept(
        "financial bank", aliases=("bank",), namespace="en", sense_key="finance", context_cues=("loan",)
    )
    index.register_concept(
        "river bank", aliases=("bank",), namespace="en", sense_key="geography", context_cues=("river",)
    )

    result = index.resolve_with_context("bank", "loan near river bank", namespace="en")
    assert result.status == "UNRESOLVED"
    assert result.reason == "ambiguous_context"


def test_persistent_context_cues_survive_restart(tmp_path):
    memory = EnterpriseMemoryService(OrganizationIdentity("org-a", "Org A"))
    store = PersistentSemanticConceptStore(memory)
    finance = store.register_concept(
        _scope(),
        "financial bank",
        aliases=("bank",),
        namespace="en",
        sense_key="finance",
        context_cues=("loan", "money"),
    )
    store.register_concept(
        _scope(),
        "river bank",
        aliases=("bank",),
        namespace="en",
        sense_key="geography",
        context_cues=("river", "water"),
    )
    root = tmp_path / "state"
    memory.save(root)

    reloaded = PersistentSemanticConceptStore(EnterpriseMemoryService.load(root))
    result = reloaded.resolve_with_context(
        _scope(), "bank", "money in the bank", namespace="en"
    )
    assert result.status == "HIT"
    assert result.concept_id == finance.concept_id
    assert reloaded.get(_scope(), finance.concept_id, namespace="en").context_cues == ("loan", "money")


def test_concept_aware_resolver_uses_unique_contextual_sense_only_after_miss():
    store = _store()
    finance = store.register_concept(
        _scope(),
        "financial bank",
        aliases=("bank",),
        namespace="en",
        sense_key="finance",
        context_cues=("loan",),
    )
    store.register_concept(
        _scope(),
        "river bank",
        aliases=("bank",),
        namespace="en",
        sense_key="geography",
        context_cues=("river",),
    )
    base = FakeResolver({"financial bank loan status": "HIT"})
    resolver = ConceptAwareConversationResolver(base, store, scope=_scope(), concept_namespace="en")

    result, trace = resolver.resolve_with_trace(query="bank loan status", session_id="s1")

    assert result.status == "HIT"
    assert base.calls == [
        ("bank loan status", "s1"),
        ("financial bank loan status", "s1"),
    ]
    assert trace.retry_attempted is True
    assert len(trace.matches) == 1
    assert trace.matches[0].status == "CONTEXT_HIT"
    assert trace.matches[0].concept_id == finance.concept_id
    assert trace.matches[0].sense_key == "finance"


def test_concept_aware_resolver_refuses_competing_contextual_senses():
    store = _store()
    store.register_concept(
        _scope(), "financial bank", aliases=("bank",), namespace="en", sense_key="finance", context_cues=("loan",)
    )
    store.register_concept(
        _scope(), "river bank", aliases=("bank",), namespace="en", sense_key="geography", context_cues=("river",)
    )
    base = FakeResolver()
    resolver = ConceptAwareConversationResolver(base, store, scope=_scope(), concept_namespace="en")

    query = "loan and river context for bank status"
    result, trace = resolver.resolve_with_trace(query=query, session_id="s1")

    assert result.status == "UNRESOLVED"
    assert trace.retry_attempted is False
    assert trace.reason == "ambiguous_context"
    assert base.calls == [(query, "s1")]
