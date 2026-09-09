from __future__ import annotations

import os

import pytest

from memoria_resolutiva.epistemic_bdr_persistence import (
    load_epistemic_audit_bdr,
    load_epistemic_audit_from_backend,
    save_epistemic_audit_bdr,
    save_epistemic_audit_to_backend,
)
from memoria_resolutiva.evidence_core import EvidenceCore
from memoria_resolutiva.evidence_temporal_bridge import (
    EpistemicSource,
    EvidenceTemporalBridge,
)
from memoria_resolutiva.learning_gate import EpistemicLearningGate
from memoria_resolutiva.topological_bdr_persistence import (
    load_snapshot_bdr,
    load_snapshot_from_backend,
    save_snapshot_bdr,
    save_snapshot_to_backend,
)
from memoria_resolutiva.topological_memory import AddressSpace, TemporalEventStore, TemporalOperator


class FakeAtomicBackend:
    def __init__(self) -> None:
        self.state: dict[str, bytes] = {}
        self.sequence = 0

    def write_batch(self, puts: list[tuple[str, bytes]]) -> int:
        candidate = dict(self.state)
        for key, value in puts:
            candidate[key] = bytes(value)
        self.state = candidate
        self.sequence += 1
        return self.sequence

    def get(self, key: str) -> bytes | None:
        return self.state.get(key)


def _build_runtime():
    evidence = EvidenceCore()
    user = evidence.observe_relation(
        "minha camisa",
        "cor",
        "azul",
        evidence_id="user-blue",
        source_text="Minha camisa é azul.",
        provenance="USER_CONFIRMED",
        origin="user",
    )
    llm_red = evidence.observe_relation(
        "minha camisa",
        "cor",
        "vermelha",
        evidence_id="llm-red",
        source_text="Sua camisa provavelmente é vermelha.",
        provenance="LLM_GENERATED",
        origin="assistant",
        confidence=0.99,
    )
    llm_green = evidence.observe_relation(
        "minha camisa",
        "cor",
        "verde",
        evidence_id="llm-green",
        source_text="Talvez sua camisa seja verde.",
        provenance="LLM_GENERATED",
        origin="assistant",
        confidence=0.75,
    )

    addresses = AddressSpace()
    store = TemporalEventStore(addresses)
    bridge = EvidenceTemporalBridge(addresses, store)
    gate = EpistemicLearningGate(evidence)

    bridge.project_edge(user)
    bridge.project_edge(llm_red)
    bridge.project_edge(llm_green)

    accepted = gate.decide(
        llm_red,
        decision_id="accept-red",
        accepted=True,
        validator_source=EpistemicSource.USER_CONFIRMED,
        validator_id="user",
        reason="Usuário confirmou a nova cor.",
    )
    gate.decide(
        llm_green,
        decision_id="reject-green",
        accepted=False,
        validator_source=EpistemicSource.USER_CONFIRMED,
        validator_id="user",
        reason="Usuário rejeitou a hipótese verde.",
    )
    promoted = next(edge for edge in evidence.evidence_history() if edge.evidence_id == accepted.promoted_evidence_id)
    bridge.project_edge(promoted)
    return evidence, addresses, store, bridge, gate


def _clone_evidence(source: EvidenceCore) -> EvidenceCore:
    clone = EvidenceCore()
    for edge in source.evidence_history():
        clone.observe_relation(
            edge.subject,
            edge.predicate,
            edge.object,
            evidence_id=edge.evidence_id,
            source_text=edge.source_text,
            provenance=edge.provenance,
            origin=edge.origin,
            confidence=edge.confidence,
            namespace=edge.namespace,
            epoch=edge.epoch,
        )
    return clone


def _current_value(store: TemporalEventStore) -> str | None:
    result = store.resolve("minha camisa", "cor", TemporalOperator.CURRENT)
    return store.value_text(result.value_address)


def test_epistemic_audit_round_trip_preserves_projection_and_learning_history():
    evidence, addresses, store, bridge, gate = _build_runtime()
    backend = FakeAtomicBackend()
    topology_stats = save_snapshot_to_backend(backend, addresses, store)
    audit_stats = save_epistemic_audit_to_backend(backend, bridge, gate)

    restored_addresses, restored_store = load_snapshot_from_backend(backend)
    restored_evidence = _clone_evidence(evidence)
    restored_bridge = EvidenceTemporalBridge(restored_addresses, restored_store)
    restored_gate = EpistemicLearningGate(restored_evidence)
    loaded = load_epistemic_audit_from_backend(backend, restored_bridge, restored_gate)

    assert topology_stats.bdr_sequence == 1
    assert audit_stats.bdr_sequence == 2
    assert loaded.projections == 4
    assert loaded.decisions == 2
    assert restored_bridge.iter_projections() == bridge.iter_projections()
    assert restored_gate.iter_decisions() == gate.iter_decisions()
    assert _current_value(restored_store) == "vermelha"


def test_restart_preserves_projection_and_learning_idempotency_boundaries():
    evidence, addresses, store, bridge, gate = _build_runtime()
    backend = FakeAtomicBackend()
    save_snapshot_to_backend(backend, addresses, store)
    save_epistemic_audit_to_backend(backend, bridge, gate)

    restored_addresses, restored_store = load_snapshot_from_backend(backend)
    restored_evidence = _clone_evidence(evidence)
    restored_bridge = EvidenceTemporalBridge(restored_addresses, restored_store)
    restored_gate = EpistemicLearningGate(restored_evidence)
    load_epistemic_audit_from_backend(backend, restored_bridge, restored_gate)

    llm_red = next(edge for edge in restored_evidence.evidence_history() if edge.evidence_id == "llm-red")
    before_events = len(restored_store.iter_events())
    duplicate_projection = restored_bridge.project_edge(llm_red)
    assert duplicate_projection.promoted is False
    assert len(restored_store.iter_events()) == before_events

    with pytest.raises(ValueError, match="already been applied"):
        restored_gate.decide(
            llm_red,
            decision_id="accept-red",
            accepted=False,
            validator_source=EpistemicSource.USER_CONFIRMED,
            validator_id="user",
            reason="duplicate",
        )


def test_epistemic_audit_fails_closed_when_record_or_temporal_reference_is_missing():
    evidence, addresses, store, bridge, gate = _build_runtime()
    backend = FakeAtomicBackend()
    save_snapshot_to_backend(backend, addresses, store)
    save_epistemic_audit_to_backend(backend, bridge, gate)

    projection_key = next(key for key in backend.state if "/projection/" in key)
    saved = backend.state.pop(projection_key)
    fresh_bridge = EvidenceTemporalBridge(addresses, store)
    fresh_gate = EpistemicLearningGate(evidence)
    with pytest.raises(ValueError, match="missing BDR epistemic record"):
        load_epistemic_audit_from_backend(backend, fresh_bridge, fresh_gate)
    assert fresh_bridge.iter_projections() == ()
    assert fresh_gate.iter_decisions() == ()

    backend.state[projection_key] = saved
    promoted_event = next(item.temporal_event for item in bridge.iter_projections() if item.promoted)
    assert promoted_event is not None
    event_key = f"memoria.topology.v1/event/{promoted_event.sequence:020d}"
    backend.state.pop(event_key)
    with pytest.raises(ValueError, match="missing BDR record"):
        load_snapshot_from_backend(backend)


def test_real_bdr_persists_topology_and_epistemic_audit_when_library_is_available(tmp_path):
    library_path = os.environ.get("BDR_ATOMIC_LIB")
    if not library_path:
        pytest.skip("BDR_ATOMIC_LIB is not configured for this test environment")

    evidence, addresses, store, bridge, gate = _build_runtime()
    bdr_root = tmp_path / "bdr"
    topology_stats = save_snapshot_bdr(bdr_root, library_path, addresses, store)
    audit_stats = save_epistemic_audit_bdr(bdr_root, library_path, bridge, gate)

    restored_addresses, restored_store = load_snapshot_bdr(bdr_root, library_path)
    restored_evidence = _clone_evidence(evidence)
    restored_bridge = EvidenceTemporalBridge(restored_addresses, restored_store)
    restored_gate = EpistemicLearningGate(restored_evidence)
    loaded = load_epistemic_audit_bdr(
        bdr_root,
        library_path,
        restored_bridge,
        restored_gate,
    )

    assert topology_stats.bdr_sequence >= 1
    assert audit_stats.bdr_sequence > topology_stats.bdr_sequence
    assert loaded.bdr_sequence == audit_stats.bdr_sequence
    assert restored_bridge.iter_projections() == bridge.iter_projections()
    assert restored_gate.iter_decisions() == gate.iter_decisions()
    assert _current_value(restored_store) == "vermelha"
