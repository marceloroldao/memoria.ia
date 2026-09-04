from memoria_resolutiva.concept_relations import ConceptRelationView
from memoria_resolutiva.evidence_core import EvidenceCore
from memoria_resolutiva.product_identity import MemoryScope, OrganizationIdentity
from memoria_resolutiva.product_service import EnterpriseMemoryService
from memoria_resolutiva.semantic_concept_store import PersistentSemanticConceptStore


def _scope():
    return MemoryScope("org-a", application_id="app", user_id="user", agent_id="agent")


def _store():
    memory = EnterpriseMemoryService(OrganizationIdentity("org-a", "Org A"))
    return PersistentSemanticConceptStore(memory)


def test_two_edges_connect_through_shared_concept_identity():
    concepts = _store()
    concepts.register_concept(
        _scope(),
        "voltage",
        aliases=("DDP", "diferença de potencial"),
        namespace="electronics",
    )
    evidence = EvidenceCore()
    evidence.observe_relation(
        "charger",
        "has_property",
        "diferença de potencial",
        evidence_id="e1",
        source_text="charger has diferença de potencial",
        namespace="session",
        confidence=0.95,
    )
    evidence.observe_relation(
        "voltage",
        "has_value",
        "34V",
        evidence_id="e2",
        source_text="voltage has value 34V",
        namespace="session",
        confidence=0.92,
    )
    view = ConceptRelationView(evidence, concepts, scope=_scope(), concept_namespace="electronics")

    result = view.infer_path("charger", "34V", namespace="session")

    assert result.status == "HIT"
    assert len(result.paths) == 1
    path = result.paths[0]
    assert path.evidence_ids == ("e1", "e2")
    assert path.hops == 2
    assert path.confidence == 0.92
    assert path.nodes[1].concept_id is not None
    assert path.nodes[1].key.startswith("concept:")


def test_alias_query_endpoint_can_start_concept_path():
    concepts = _store()
    concepts.register_concept(
        _scope(), "voltage", aliases=("DDP", "diferença de potencial"), namespace="electronics"
    )
    evidence = EvidenceCore()
    evidence.observe_relation(
        "voltage",
        "has_value",
        "34V",
        evidence_id="e1",
        source_text="voltage has value 34V",
        namespace="session",
    )
    view = ConceptRelationView(evidence, concepts, scope=_scope(), concept_namespace="electronics")

    result = view.infer_path("DDP", "34V", namespace="session")

    assert result.status == "HIT"
    assert result.paths[0].evidence_ids == ("e1",)


def test_ambiguous_path_endpoint_fails_closed():
    concepts = _store()
    concepts.register_concept(
        _scope(), "financial bank", aliases=("bank",), namespace="en", sense_key="finance"
    )
    concepts.register_concept(
        _scope(), "river bank", aliases=("bank",), namespace="en", sense_key="geography"
    )
    evidence = EvidenceCore()
    evidence.observe_relation(
        "financial bank",
        "has_value",
        "open",
        evidence_id="e1",
        source_text="financial bank has value open",
        namespace="session",
    )
    view = ConceptRelationView(evidence, concepts, scope=_scope(), concept_namespace="en")

    result = view.infer_path("bank", "open", namespace="session")

    assert result.status == "UNRESOLVED"
    assert result.reason == "ambiguous_concept"


def test_context_can_select_one_polysemous_path_endpoint():
    concepts = _store()
    concepts.register_concept(
        _scope(),
        "financial bank",
        aliases=("bank",),
        namespace="en",
        sense_key="finance",
        context_cues=("loan",),
    )
    concepts.register_concept(
        _scope(),
        "river bank",
        aliases=("bank",),
        namespace="en",
        sense_key="geography",
        context_cues=("river",),
    )
    evidence = EvidenceCore()
    evidence.observe_relation(
        "financial bank",
        "handles",
        "loan",
        evidence_id="finance",
        source_text="financial bank handles loan",
        namespace="session",
    )
    evidence.observe_relation(
        "river bank",
        "touches",
        "water",
        evidence_id="river",
        source_text="river bank touches water",
        namespace="session",
    )
    view = ConceptRelationView(evidence, concepts, scope=_scope(), concept_namespace="en")

    result = view.infer_path(
        "bank",
        "loan",
        namespace="session",
        context="loan application at bank",
    )

    assert result.status == "HIT"
    assert result.paths[0].evidence_ids == ("finance",)
    assert result.paths[0].nodes[0].sense_key == "finance"


def test_cycle_is_not_revisited_and_max_hops_is_respected():
    concepts = _store()
    evidence = EvidenceCore()
    evidence.observe_relation("A", "to", "B", evidence_id="ab", source_text="A to B", namespace="s")
    evidence.observe_relation("B", "to", "A", evidence_id="ba", source_text="B to A", namespace="s")
    evidence.observe_relation("B", "to", "C", evidence_id="bc", source_text="B to C", namespace="s")
    view = ConceptRelationView(evidence, concepts, scope=_scope())

    result = view.infer_path("A", "C", namespace="s", max_hops=2)

    assert result.status == "HIT"
    assert result.paths[0].evidence_ids == ("ab", "bc")


def test_min_confidence_filters_weak_semantic_bridge():
    concepts = _store()
    concepts.register_concept(_scope(), "voltage", aliases=("DDP",), namespace="electronics")
    evidence = EvidenceCore()
    evidence.observe_relation(
        "charger",
        "has_property",
        "DDP",
        evidence_id="weak",
        source_text="charger has DDP",
        namespace="s",
        confidence=0.7,
    )
    evidence.observe_relation(
        "voltage",
        "has_value",
        "34V",
        evidence_id="strong",
        source_text="voltage has value 34V",
        namespace="s",
        confidence=0.95,
    )
    view = ConceptRelationView(evidence, concepts, scope=_scope(), concept_namespace="electronics")

    result = view.infer_path("charger", "34V", namespace="s", min_confidence=0.9)

    assert result.status == "UNRESOLVED"
    assert result.reason == "no_path"


def test_namespace_isolation_applies_to_concept_paths():
    concepts = _store()
    concepts.register_concept(_scope(), "voltage", aliases=("DDP",), namespace="electronics")
    evidence = EvidenceCore()
    evidence.observe_relation("charger", "has", "DDP", evidence_id="a1", source_text="charger has DDP", namespace="A")
    evidence.observe_relation("voltage", "value", "34V", evidence_id="b1", source_text="voltage value 34V", namespace="B")
    view = ConceptRelationView(evidence, concepts, scope=_scope(), concept_namespace="electronics")

    result = view.infer_path("charger", "34V", namespace="A")

    assert result.status == "UNRESOLVED"
    assert result.reason == "no_path"
