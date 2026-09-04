from pathlib import Path

from memoria_resolutiva.product_identity import MemoryScope, OrganizationIdentity
from memoria_resolutiva.product_service import EnterpriseMemoryService
from memoria_resolutiva.semantic_concept_store import PersistentSemanticConceptStore


def _service() -> EnterpriseMemoryService:
    return EnterpriseMemoryService(OrganizationIdentity("org-a", "Org A"))


def _scope(agent_id: str = "agent-a") -> MemoryScope:
    return MemoryScope("org-a", application_id="app", user_id="user", agent_id=agent_id)


def test_registered_alias_survives_product_save_and_load(tmp_path: Path):
    memory = _service()
    store = PersistentSemanticConceptStore(memory)
    concept = store.register_concept(
        _scope(),
        "voltage",
        aliases=("DDP", "potential difference"),
        namespace="electronics",
    )

    root = tmp_path / "state"
    memory.save(root)
    loaded = EnterpriseMemoryService.load(root)
    reloaded = PersistentSemanticConceptStore(loaded)

    resolved = reloaded.resolve(_scope(), "ddp", namespace="electronics")
    assert resolved.status == "HIT"
    assert resolved.concept_id == concept.concept_id
    restored = reloaded.get(_scope(), concept.concept_id, namespace="electronics")
    assert restored is not None
    assert restored.concept_id == concept.concept_id
    assert "potential difference" in restored.aliases


def test_alias_collision_remains_ambiguous_after_restart(tmp_path: Path):
    memory = _service()
    store = PersistentSemanticConceptStore(memory)
    finance = store.register_concept(
        _scope(),
        "financial bank",
        aliases=("bank",),
        namespace="english",
        sense_key="finance",
    )
    geography = store.register_concept(
        _scope(),
        "river bank",
        aliases=("bank",),
        namespace="english",
        sense_key="geography",
    )

    root = tmp_path / "state"
    memory.save(root)
    reloaded = PersistentSemanticConceptStore(EnterpriseMemoryService.load(root))
    resolved = reloaded.resolve(_scope(), "bank", namespace="english")

    assert resolved.status == "UNRESOLVED"
    assert resolved.reason == "ambiguous"
    assert set(resolved.candidate_ids) == {finance.concept_id, geography.concept_id}


def test_semantic_namespace_isolation_is_preserved():
    store = PersistentSemanticConceptStore(_service())
    concept = store.register_concept(
        _scope(), "voltage", aliases=("DDP",), namespace="private:a"
    )

    assert store.resolve(_scope(), "DDP", namespace="private:a").concept_id == concept.concept_id
    other = store.resolve(_scope(), "DDP", namespace="private:b")
    assert other.status == "UNRESOLVED"
    assert other.reason == "unknown"


def test_memory_scope_isolation_prevents_cross_agent_alias_recall():
    store = PersistentSemanticConceptStore(_service())
    concept = store.register_concept(
        _scope("agent-a"), "voltage", aliases=("DDP",), namespace="electronics"
    )

    assert store.resolve(_scope("agent-a"), "DDP", namespace="electronics").concept_id == concept.concept_id
    other = store.resolve(_scope("agent-b"), "DDP", namespace="electronics")
    assert other.status == "UNRESOLVED"
    assert other.reason == "unknown"


def test_re_registering_concept_adds_alias_using_versioned_product_update():
    memory = _service()
    store = PersistentSemanticConceptStore(memory)
    first = store.register_concept(
        _scope(), "voltage", aliases=("DDP",), namespace="electronics"
    )
    second = store.register_concept(
        _scope(), "voltage", aliases=("potential difference",), namespace="electronics"
    )

    assert first.concept_id == second.concept_id
    assert store.resolve(_scope(), "DDP", namespace="electronics").concept_id == first.concept_id
    assert store.resolve(_scope(), "potential difference", namespace="electronics").concept_id == first.concept_id

    route = store._concept_route("electronics", first.concept_id)
    record = memory.recall(_scope(), route)
    assert record is not None
    assert record.version == 2
    assert "semantic-concept" in record.provenance


def test_unknown_and_empty_surfaces_remain_unresolved():
    store = PersistentSemanticConceptStore(_service())
    store.register_concept(_scope(), "voltage", aliases=("DDP",), namespace="electronics")

    unknown = store.resolve(_scope(), "electric tension", namespace="electronics")
    empty = store.resolve(_scope(), "---", namespace="electronics")
    assert unknown.status == "UNRESOLVED" and unknown.reason == "unknown"
    assert empty.status == "UNRESOLVED" and empty.reason == "empty"
