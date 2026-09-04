from memoria_resolutiva.concept_relations import ConceptRelationView
from memoria_resolutiva.evidence_core import EvidenceCore
from memoria_resolutiva.product_identity import MemoryScope, OrganizationIdentity
from memoria_resolutiva.product_service import EnterpriseMemoryService
from memoria_resolutiva.semantic_concept_store import PersistentSemanticConceptStore


def _scope():
    return MemoryScope("org-a", application_id="app", user_id="user", agent_id="agent")


def _store():
    memory = EnterpriseMemoryService(OrganizationIdentity("org-a", "Org A"))
    return memory, PersistentSemanticConceptStore(memory)


def test_aliases_converge_to_same_relation_identity():
    _memory, concepts = _store()
    concepts.register_concept(
        _scope(),
        "voltage",
        aliases=("DDP", "diferença de potencial"),
        namespace="electronics",
    )
    evidence = EvidenceCore()
    evidence.observe_relation(
        "diferença de potencial",
        "is",
        "34V",
        evidence_id="e1",
        source_text="A diferença de potencial é 34V",
        namespace="session",
    )
    view = ConceptRelationView(
        evidence,
        concepts,
        scope=_scope(),
        concept_namespace="electronics",
    )

    by_ddp = view.find(subject="DDP", predicate="is", namespace="session")
    by_voltage = view.find(subject="voltage", predicate="is", namespace="session")

    assert by_ddp.status == "HIT"
    assert by_voltage.status == "HIT"
    assert by_ddp.relations[0].evidence_id == "e1"
    assert by_voltage.relations[0].evidence_id == "e1"
    assert by_ddp.relations[0].subject.key == by_voltage.relations[0].subject.key


def test_unknown_object_remains_lexical_without_losing_evidence():
    _memory, concepts = _store()
    concepts.register_concept(_scope(), "voltage", aliases=("DDP",), namespace="electronics")
    evidence = EvidenceCore()
    evidence.observe_relation(
        "voltage",
        "is",
        "34V",
        evidence_id="e1",
        source_text="voltage is 34V",
        namespace="session",
    )
    view = ConceptRelationView(evidence, concepts, scope=_scope(), concept_namespace="electronics")

    result = view.find(subject="DDP", object="34V", namespace="session")

    assert result.status == "HIT"
    assert result.relations[0].subject.status == "CONCEPT"
    assert result.relations[0].object.status == "LEXICAL"
    assert result.relations[0].object.surface == "34V"


def test_ambiguous_alias_fails_closed_without_relation_match():
    _memory, concepts = _store()
    concepts.register_concept(
        _scope(), "financial bank", aliases=("bank",), namespace="en", sense_key="finance"
    )
    concepts.register_concept(
        _scope(), "river bank", aliases=("bank",), namespace="en", sense_key="geography"
    )
    evidence = EvidenceCore()
    evidence.observe_relation(
        "financial bank",
        "is",
        "open",
        evidence_id="e1",
        source_text="financial bank is open",
        namespace="session",
    )
    view = ConceptRelationView(evidence, concepts, scope=_scope(), concept_namespace="en")

    result = view.find(subject="bank", predicate="is", namespace="session")

    assert result.status == "UNRESOLVED"
    assert result.reason == "ambiguous_concept"
    assert result.relations == ()


def test_context_can_select_one_ambiguous_relation_sense():
    _memory, concepts = _store()
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
        evidence_id="finance-edge",
        source_text="financial bank handles loan",
        namespace="session",
    )
    evidence.observe_relation(
        "river bank",
        "has",
        "water",
        evidence_id="river-edge",
        source_text="river bank has water",
        namespace="session",
    )
    view = ConceptRelationView(evidence, concepts, scope=_scope(), concept_namespace="en")

    result = view.find(subject="bank", namespace="session", context="loan application at bank")

    assert result.status == "HIT"
    assert [row.evidence_id for row in result.relations] == ["finance-edge"]
    assert result.relations[0].subject.sense_key == "finance"


def test_concept_relation_identity_survives_concept_store_restart(tmp_path):
    memory, concepts = _store()
    concepts.register_concept(
        _scope(),
        "voltage",
        aliases=("DDP", "diferença de potencial"),
        namespace="electronics",
    )
    root = tmp_path / "state"
    memory.save(root)
    reloaded = PersistentSemanticConceptStore(EnterpriseMemoryService.load(root))

    evidence = EvidenceCore()
    evidence.observe_relation(
        "diferença de potencial",
        "is",
        "34V",
        evidence_id="e1",
        source_text="A diferença de potencial é 34V",
        namespace="session",
    )
    view = ConceptRelationView(evidence, reloaded, scope=_scope(), concept_namespace="electronics")

    result = view.find(subject="DDP", namespace="session")

    assert result.status == "HIT"
    assert result.relations[0].evidence_id == "e1"


def test_relation_namespaces_remain_isolated():
    _memory, concepts = _store()
    concepts.register_concept(_scope(), "voltage", aliases=("DDP",), namespace="electronics")
    evidence = EvidenceCore()
    evidence.observe_relation(
        "voltage", "is", "34V", evidence_id="a", source_text="voltage is 34V", namespace="A"
    )
    evidence.observe_relation(
        "voltage", "is", "12V", evidence_id="b", source_text="voltage is 12V", namespace="B"
    )
    view = ConceptRelationView(evidence, concepts, scope=_scope(), concept_namespace="electronics")

    result = view.find(subject="DDP", namespace="A")

    assert result.status == "HIT"
    assert [row.evidence_id for row in result.relations] == ["a"]
