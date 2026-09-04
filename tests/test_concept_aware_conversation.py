from types import SimpleNamespace

from memoria_resolutiva.concept_aware_conversation import (
    ConceptAwareConversationResolver,
    rewrite_query_with_explicit_concepts,
)
from memoria_resolutiva.product_identity import MemoryScope, OrganizationIdentity
from memoria_resolutiva.product_service import EnterpriseMemoryService
from memoria_resolutiva.semantic_concept_store import PersistentSemanticConceptStore


class FakeResolver:
    def __init__(self, responses: dict[str, str] | None = None):
        self.responses = responses or {}
        self.calls: list[tuple[str, str | None]] = []

    def resolve(self, *, query: str, session_id: str | None = None):
        self.calls.append((query, session_id))
        status = self.responses.get(query, "UNRESOLVED")
        return SimpleNamespace(
            status=status,
            confidence=0.8 if status == "HIT" else 0.0,
            memory_ids=("r1",) if status == "HIT" else (),
            selected_context="charger voltage is 34V" if status == "HIT" else "",
            relations=(),
            provenance=(),
        )


def _scope() -> MemoryScope:
    return MemoryScope("org-a", application_id="app", user_id="user", agent_id="agent")


def _store() -> PersistentSemanticConceptStore:
    memory = EnterpriseMemoryService(OrganizationIdentity("org-a", "Org A"))
    return PersistentSemanticConceptStore(memory)


def test_original_resolver_hit_is_never_rewritten():
    store = _store()
    store.register_concept(_scope(), "voltage", aliases=("DDP",), namespace="electronics")
    base = FakeResolver({"qual a DDP do carregador?": "HIT"})
    resolver = ConceptAwareConversationResolver(
        base, store, scope=_scope(), concept_namespace="electronics"
    )

    result = resolver.resolve(query="qual a DDP do carregador?", session_id="s1")

    assert result.status == "HIT"
    assert base.calls == [("qual a DDP do carregador?", "s1")]


def test_unambiguous_alias_rewrites_only_after_original_miss():
    store = _store()
    concept = store.register_concept(
        _scope(), "voltage", aliases=("DDP", "potential difference"), namespace="electronics"
    )
    base = FakeResolver({"qual a voltage do carregador": "HIT"})
    resolver = ConceptAwareConversationResolver(
        base, store, scope=_scope(), concept_namespace="electronics"
    )

    result = resolver.resolve(query="Qual a DDP do carregador?", session_id="s1")

    assert result.status == "HIT"
    assert base.calls == [
        ("Qual a DDP do carregador?", "s1"),
        ("qual a voltage do carregador", "s1"),
    ]
    rewrite = rewrite_query_with_explicit_concepts(
        store, _scope(), "Qual a DDP do carregador?", namespace="electronics"
    )
    assert rewrite.status == "REWRITTEN"
    assert rewrite.concept_ids == (concept.concept_id,)


def test_longest_registered_alias_wins_over_shorter_span():
    store = _store()
    store.register_concept(
        _scope(), "voltage", aliases=("potential difference",), namespace="electronics"
    )
    rewrite = rewrite_query_with_explicit_concepts(
        store,
        _scope(),
        "measure the potential difference now",
        namespace="electronics",
    )
    assert rewrite.status == "REWRITTEN"
    assert rewrite.rewritten_query == "measure the voltage now"


def test_ambiguous_alias_fails_closed_without_second_resolve():
    store = _store()
    finance = store.register_concept(
        _scope(), "financial bank", aliases=("bank",), namespace="english", sense_key="finance"
    )
    river = store.register_concept(
        _scope(), "river bank", aliases=("bank",), namespace="english", sense_key="geography"
    )
    base = FakeResolver()
    resolver = ConceptAwareConversationResolver(
        base, store, scope=_scope(), concept_namespace="english"
    )

    result = resolver.resolve(query="bank status", session_id="s1")
    rewrite = rewrite_query_with_explicit_concepts(
        store, _scope(), "bank status", namespace="english"
    )

    assert result.status == "UNRESOLVED"
    assert base.calls == [("bank status", "s1")]
    assert rewrite.status == "UNRESOLVED"
    assert rewrite.reason == "ambiguous_concept"
    assert set(rewrite.concept_ids) == {finance.concept_id, river.concept_id}


def test_unknown_words_are_left_untouched_and_do_not_trigger_retry():
    store = _store()
    store.register_concept(_scope(), "voltage", aliases=("DDP",), namespace="electronics")
    base = FakeResolver()
    resolver = ConceptAwareConversationResolver(
        base, store, scope=_scope(), concept_namespace="electronics"
    )

    result = resolver.resolve(query="temperatura externa", session_id="s1")

    assert result.status == "UNRESOLVED"
    assert base.calls == [("temperatura externa", "s1")]


def test_canonical_term_does_not_trigger_redundant_retry():
    store = _store()
    store.register_concept(_scope(), "voltage", aliases=("DDP",), namespace="electronics")
    base = FakeResolver()
    resolver = ConceptAwareConversationResolver(
        base, store, scope=_scope(), concept_namespace="electronics"
    )

    result = resolver.resolve(query="voltage", session_id="s1")

    assert result.status == "UNRESOLVED"
    assert base.calls == [("voltage", "s1")]


def test_multiword_alias_survives_store_restart_and_still_rewrites(tmp_path):
    memory = EnterpriseMemoryService(OrganizationIdentity("org-a", "Org A"))
    store = PersistentSemanticConceptStore(memory)
    store.register_concept(
        _scope(), "voltage", aliases=("diferença de potencial",), namespace="electronics"
    )
    root = tmp_path / "state"
    memory.save(root)

    reloaded = PersistentSemanticConceptStore(EnterpriseMemoryService.load(root))
    base = FakeResolver({"qual a voltage": "HIT"})
    resolver = ConceptAwareConversationResolver(
        base, reloaded, scope=_scope(), concept_namespace="electronics"
    )

    result = resolver.resolve(query="qual a diferença de potencial", session_id="s1")

    assert result.status == "HIT"
    assert base.calls == [
        ("qual a diferença de potencial", "s1"),
        ("qual a voltage", "s1"),
    ]


def test_trace_records_alias_concept_and_sense_used_for_retry():
    store = _store()
    concept = store.register_concept(
        _scope(),
        "voltage",
        aliases=("DDP",),
        namespace="electronics",
        sense_key="electric potential",
    )
    base = FakeResolver({"qual a voltage": "HIT"})
    resolver = ConceptAwareConversationResolver(
        base, store, scope=_scope(), concept_namespace="electronics"
    )

    result, trace = resolver.resolve_with_trace(query="qual a DDP", session_id="s1")

    assert result.status == "HIT"
    assert trace.original_status == "UNRESOLVED"
    assert trace.rewrite_status == "REWRITTEN"
    assert trace.retry_attempted is True
    assert trace.final_status == "HIT"
    assert trace.reason == "concept_retry"
    assert trace.rewritten_query == "qual a voltage"
    assert len(trace.matches) == 1
    match = trace.matches[0]
    assert match.surface == "ddp"
    assert match.canonical == "voltage"
    assert match.concept_id == concept.concept_id
    assert match.sense_key == "electric potential"
    assert resolver.last_trace == trace


def test_trace_preserves_ambiguous_candidate_senses_without_retry():
    store = _store()
    finance = store.register_concept(
        _scope(), "financial bank", aliases=("bank",), namespace="english", sense_key="finance"
    )
    geography = store.register_concept(
        _scope(), "river bank", aliases=("bank",), namespace="english", sense_key="geography"
    )
    base = FakeResolver()
    resolver = ConceptAwareConversationResolver(
        base, store, scope=_scope(), concept_namespace="english"
    )

    result, trace = resolver.resolve_with_trace(query="bank status", session_id="s1")

    assert result.status == "UNRESOLVED"
    assert trace.rewrite_status == "UNRESOLVED"
    assert trace.retry_attempted is False
    assert trace.reason == "ambiguous_concept"
    assert {match.concept_id for match in trace.matches} == {finance.concept_id, geography.concept_id}
    assert {match.sense_key for match in trace.matches} == {"finance", "geography"}
    assert all(match.status == "AMBIGUOUS" for match in trace.matches)
    assert base.calls == [("bank status", "s1")]


def test_original_hit_trace_does_not_claim_concept_participation():
    store = _store()
    store.register_concept(
        _scope(), "voltage", aliases=("DDP",), namespace="electronics", sense_key="electric potential"
    )
    base = FakeResolver({"qual a DDP": "HIT"})
    resolver = ConceptAwareConversationResolver(
        base, store, scope=_scope(), concept_namespace="electronics"
    )

    result, trace = resolver.resolve_with_trace(query="qual a DDP", session_id="s1")

    assert result.status == "HIT"
    assert trace.original_status == "HIT"
    assert trace.rewrite_status == "SKIPPED"
    assert trace.retry_attempted is False
    assert trace.reason == "original_hit"
    assert trace.matches == ()
    assert base.calls == [("qual a DDP", "s1")]
