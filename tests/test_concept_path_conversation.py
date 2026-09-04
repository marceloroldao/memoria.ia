from memoria_resolutiva.concept_aware_conversation import ConceptAwareConversationResolver
from memoria_resolutiva.concept_path_conversation import ConceptPathConversationResolver
from memoria_resolutiva.concept_relations import ConceptRelationView
from memoria_resolutiva.product_conversation import ConversationSemanticService
from memoria_resolutiva.product_evidence import ProductEvidenceService
from memoria_resolutiva.product_identity import MemoryScope, OrganizationIdentity
from memoria_resolutiva.product_service import EnterpriseMemoryService
from memoria_resolutiva.semantic_concept_store import PersistentSemanticConceptStore


def _scope():
    return MemoryScope("org-a", application_id="app", user_id="user", agent_id="agent")


def _build(tmp_path):
    evidence = ProductEvidenceService.open(tmp_path / "evidence", backend="sqlite", allow_fallback=False)
    conversation = ConversationSemanticService(evidence)
    memory = EnterpriseMemoryService(OrganizationIdentity("org-a", "Org A"))
    concepts = PersistentSemanticConceptStore(memory)
    concepts.register_concept(
        _scope(),
        "voltage",
        aliases=("voltage", "ddp", "diferença de potencial"),
        namespace="semantic",
    )
    view = ConceptRelationView(evidence.core, concepts, scope=_scope(), concept_namespace="semantic")
    aware = ConceptAwareConversationResolver(conversation, concepts, scope=_scope(), concept_namespace="semantic")
    resolver = ConceptPathConversationResolver(aware, conversation, view, min_confidence=0.9)
    return evidence, conversation, resolver


def _observe(evidence, conversation, subject, predicate, obj, evidence_id, source_text, *, namespace="s1"):
    evidence.core.observe_relation(
        subject, predicate, obj,
        evidence_id=evidence_id,
        source_text=source_text,
        provenance="conversation",
        origin="conversation-user",
        confidence=0.95,
        namespace=namespace,
    )
    conversation.provenance.register(evidence_id, source_type="user_assertion", namespace=namespace)
    evidence.save()


def test_third_chance_uses_unique_directed_concept_path(tmp_path):
    evidence, conversation, resolver = _build(tmp_path)
    _observe(evidence, conversation, "charger", "has_property", "diferença de potencial", "e1", "charger has diferença de potencial")
    _observe(evidence, conversation, "voltage", "has_value", "34V", "e2", "voltage has value 34V")

    result, trace = resolver.resolve_with_trace(query="relação charger 34V", session_id="s1")

    assert result.status == "HIT"
    assert result.memory_ids == ("e1", "e2")
    assert result.selected_context == "charger has diferença de potencial\nvoltage has value 34V"
    assert {row["ultimate_source_memory_id"] for row in result.provenance} == {"e1", "e2"}
    assert trace.path_attempted is True
    assert trace.reason == "concept_path"
    assert trace.evidence_ids == ("e1", "e2")


def test_path_fallback_does_not_run_with_only_one_anchor(tmp_path):
    evidence, conversation, resolver = _build(tmp_path)
    _observe(evidence, conversation, "charger", "has_property", "diferença de potencial", "e1", "charger has diferença de potencial")

    result, trace = resolver.resolve_with_trace(query="DDP desconhecido", session_id="s1")

    assert result.status == "UNRESOLVED"
    assert trace.path_attempted is False
    assert trace.reason == "anchor_count"
    assert len(trace.anchors) == 1
    assert trace.anchors[0].status == "CONCEPT"


def test_path_fallback_refuses_two_valid_directions(tmp_path):
    evidence, conversation, resolver = _build(tmp_path)
    _observe(evidence, conversation, "alpha", "to", "beta", "e1", "alpha to beta")
    _observe(evidence, conversation, "beta", "to", "alpha", "e2", "beta to alpha")

    result, trace = resolver.resolve_with_trace(query="alpha beta", session_id="s1")

    assert result.status == "UNRESOLVED"
    assert trace.path_attempted is True
    assert trace.reason == "no_unique_direction"


def test_existing_hit_wins_before_path_fallback(tmp_path):
    evidence, conversation, resolver = _build(tmp_path)
    conversation.ingest(role="user", text="meu charger é azul", session_id="s1", order=1)
    _observe(evidence, conversation, "charger", "has_property", "diferença de potencial", "e1", "charger has diferença de potencial")
    _observe(evidence, conversation, "voltage", "has_value", "34V", "e2", "voltage has value 34V")

    result, trace = resolver.resolve_with_trace(query="charger azul", session_id="s1")

    assert result.status == "HIT"
    assert trace.path_attempted is False
    assert trace.reason in {"original_hit", "concept_retry"}
