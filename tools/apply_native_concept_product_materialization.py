from pathlib import Path

# NativeConversationService exposes materialization without leaking its runtime lease.
p = Path('src/memoria_resolutiva/native_conversation.py')
s = p.read_text()
old = 'from .conversation_contract import ConversationIngestResult, ConversationResolveResult\nfrom .native_runtime import NativeRuntimeManager, default_native_runtime_manager\n'
new = 'from .conversation_contract import ConversationIngestResult, ConversationResolveResult\nfrom .native_concept_catalog import NativeConceptCatalog, apply_native_concept_catalog\nfrom .native_runtime import NativeRuntimeManager, default_native_runtime_manager\n'
if s.count(old) != 1:
    raise SystemExit('native_conversation import anchor mismatch')
s = s.replace(old, new, 1)
old = '    def flush(self) -> None:\n        if not self._closed:\n            self._runtime_lease.flush()\n\n'
new = '''    def materialize_concept_catalog(self, catalog: NativeConceptCatalog) -> bool:\n        if self._closed:\n            raise RuntimeError("native conversation runtime is closed")\n        return apply_native_concept_catalog(self._runtime_lease, catalog)\n\n    def flush(self) -> None:\n        if not self._closed:\n            self._runtime_lease.flush()\n\n'''
if s.count(old) != 1:
    raise SystemExit('native_conversation flush anchor mismatch')
p.write_text(s.replace(old, new, 1))

# Product startup always constructs concept source once; Native materializes it, Python uses it directly.
p = Path('src/memoria_resolutiva/product_server.py')
s = p.read_text()
old = 'from .native_conversation import NativeConversationService\nfrom .native_episodic import NativeEpisodicService\n'
new = 'from .native_conversation import NativeConversationService\nfrom .native_concept_catalog import build_native_concept_catalog\nfrom .native_episodic import NativeEpisodicService\n'
if s.count(old) != 1:
    raise SystemExit('product_server native import anchor mismatch')
s = s.replace(old, new, 1)
old = 'from .product_service import EnterpriseMemoryService\n'
new = 'from .product_service import EnterpriseMemoryService\nfrom .semantic_concept_store import PersistentSemanticConceptStore\n'
if s.count(old) != 1:
    raise SystemExit('product_server service import anchor mismatch')
s = s.replace(old, new, 1)
old = '''    conversation_is_native = isinstance(conversation_backend, NativeConversationService)\n    episodic_is_native = isinstance(episodic_service, NativeEpisodicService)\n    automatic_episode_formation = conversation_is_native == episodic_is_native\n    conversation_service = AutoEpisodicConversationService(conversation_backend, episodic_service) if automatic_episode_formation else conversation_backend\n\n    automatic_semantic_consolidation = True\n    automatic_concept_resolution = False\n    concept_relation_service = None\n    if not conversation_is_native:\n'''
new = '''    conversation_is_native = isinstance(conversation_backend, NativeConversationService)\n    episodic_is_native = isinstance(episodic_service, NativeEpisodicService)\n    automatic_episode_formation = conversation_is_native == episodic_is_native\n    conversation_service = AutoEpisodicConversationService(conversation_backend, episodic_service) if automatic_episode_formation else conversation_backend\n\n    concept_namespace = os.getenv("MEMORIA_CONCEPT_NAMESPACE", "semantic").strip() or None\n    concept_scope = MemoryScope(organization_id)\n    concept_store = PersistentSemanticConceptStore(service)\n    native_concept_catalog_materialized = False\n    native_concept_catalog_changed = False\n    native_concept_catalog_fingerprint = None\n    native_concept_catalog_count = 0\n    if conversation_is_native:\n        native_catalog = build_native_concept_catalog(concept_store, concept_scope, namespace=concept_namespace)\n        native_concept_catalog_changed = conversation_backend.materialize_concept_catalog(native_catalog)\n        native_concept_catalog_materialized = True\n        native_concept_catalog_fingerprint = native_catalog.fingerprint\n        native_concept_catalog_count = len(native_catalog.concepts)\n\n    automatic_semantic_consolidation = True\n    automatic_concept_resolution = False\n    concept_relation_service = None\n    if not conversation_is_native:\n'''
if s.count(old) != 1:
    raise SystemExit('product_server runtime anchor mismatch')
s = s.replace(old, new, 1)
old = '''        from .product_concept_relations import ProductConceptRelationService\n        from .semantic_concept_store import PersistentSemanticConceptStore\n\n        conversation_service = AutoSemanticConsolidationConversationService(conversation_service, evidence_service)\n        concept_namespace = os.getenv("MEMORIA_CONCEPT_NAMESPACE", "semantic").strip() or None\n        concept_scope = MemoryScope(organization_id)\n        concept_store = PersistentSemanticConceptStore(service)\n'''
new = '''        from .product_concept_relations import ProductConceptRelationService\n\n        conversation_service = AutoSemanticConsolidationConversationService(conversation_service, evidence_service)\n'''
if s.count(old) != 1:
    raise SystemExit('product_server python concept anchor mismatch')
s = s.replace(old, new, 1)
old = '''            "automatic_concept_resolution": automatic_concept_resolution,\n            "concept_relation_traversal": concept_relation_service is not None,\n'''
new = '''            "automatic_concept_resolution": automatic_concept_resolution,\n            "native_concept_catalog_materialized": native_concept_catalog_materialized,\n            "native_concept_catalog_changed": native_concept_catalog_changed,\n            "native_concept_catalog_fingerprint": native_concept_catalog_fingerprint,\n            "native_concept_catalog_count": native_concept_catalog_count,\n            "concept_namespace": concept_namespace,\n            "concept_relation_traversal": concept_relation_service is not None,\n'''
if s.count(old) != 1:
    raise SystemExit('product_server health anchor mismatch')
p.write_text(s.replace(old, new, 1))

# Isolated contract test for service materialization boundary.
Path('tests/test_native_conversation_concept_materialization.py').write_text('''from __future__ import annotations\n\nfrom memoria_resolutiva.native_concept_catalog import NativeConceptCatalog\nfrom memoria_resolutiva.native_conversation import NativeConversationService\n\n\nclass _Lease:\n    def __init__(self, *, changed: bool):\n        self.changed = changed\n        self.calls = []\n        self.released = False\n\n    def supports(self, name: str) -> bool:\n        return name == "memoria_mobile_apply_concept_catalog_json"\n\n    def call(self, name: str, payload: dict[str, object]):\n        self.calls.append((name, payload))\n        return 0, {\n            "status": "OK",\n            "changed": self.changed,\n            "concept_count": payload["concept_count"],\n            "fingerprint": payload["fingerprint"],\n        }\n\n    def release(self):\n        self.released = True\n\n\nclass _Manager:\n    def __init__(self, lease: _Lease):\n        self.lease = lease\n\n    def acquire(self, **_kwargs):\n        return self.lease\n\n\ndef _catalog() -> NativeConceptCatalog:\n    return NativeConceptCatalog(\n        schema=1,\n        namespace="semantic",\n        concepts=(),\n        fingerprint="sha256:" + "b" * 64,\n    )\n\n\ndef test_native_conversation_materializes_catalog_through_owned_lease(tmp_path):\n    lease = _Lease(changed=True)\n    service = NativeConversationService(\n        library_path=tmp_path / "unused.so",\n        data_dir=tmp_path / "native",\n        organization_id="org-a",\n        runtime_manager=_Manager(lease),\n    )\n    assert service.materialize_concept_catalog(_catalog()) is True\n    assert lease.calls[0][0] == "memoria_mobile_apply_concept_catalog_json"\n    assert lease.calls[0][1]["concept_count"] == 0\n    service.close()\n    assert lease.released is True\n\n\ndef test_native_conversation_materialization_preserves_idempotent_noop(tmp_path):\n    lease = _Lease(changed=False)\n    service = NativeConversationService(\n        library_path=tmp_path / "unused.so",\n        data_dir=tmp_path / "native",\n        organization_id="org-a",\n        runtime_manager=_Manager(lease),\n    )\n    assert service.materialize_concept_catalog(_catalog()) is False\n''')
