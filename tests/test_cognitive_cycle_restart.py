from __future__ import annotations

import os

import pytest

from memoria_resolutiva.bdr_store import native_bdr_available
from memoria_resolutiva.context_compiler import ContextCompiler
from memoria_resolutiva.epistemic_bdr_persistence import (
    load_epistemic_audit_bdr,
    load_epistemic_audit_from_backend,
    save_epistemic_audit_bdr,
    save_epistemic_audit_to_backend,
)
from memoria_resolutiva.evidence_core import EvidenceCore
from memoria_resolutiva.evidence_state import EvidenceCorePersistence
from memoria_resolutiva.evidence_temporal_bridge import (
    EpistemicSource,
    EvidenceTemporalBridge,
)
from memoria_resolutiva.learning_gate import EpistemicLearningGate
from memoria_resolutiva.response_validator import ResponseClaim, ResponseValidator
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


def _build_confirmed_model_cycle(namespace: str = "default"):
    evidence = EvidenceCore()
    user_alt = evidence.observe_relation(
        "meu gato",
        "nome",
        "Alt",
        evidence_id="user-alt",
        source_text="Meu gato se chama Alt.",
        provenance="USER_CONFIRMED",
        origin="user",
        namespace=namespace,
    )
    addresses = AddressSpace()
    store = TemporalEventStore(addresses)
    bridge = EvidenceTemporalBridge(addresses, store)
    bridge.project_edge(user_alt)
    packet = ContextCompiler(store, projections=bridge.iter_projections()).compile(
        "Qual é o nome do meu gato?"
    )
    validator = ResponseValidator(evidence)
    validation = validator.validate(
        packet=packet,
        response_id="response-1",
        response_text="Seu gato se chama Bob.",
        claims=(ResponseClaim("meu gato", "nome", "Bob", 0.95),),
        model_id="cloud-llm",
        namespace=namespace,
    )
    candidate = validation.claims[0].evidence
    assert bridge.project_edge(candidate).promoted is False
    gate = EpistemicLearningGate(evidence)
    decision = gate.decide(
        candidate,
        decision_id="confirm-response-1",
        accepted=True,
        validator_source=EpistemicSource.USER_CONFIRMED,
        validator_id="user",
        reason="Usuário confirmou Bob.",
    )
    promoted = next(
        edge for edge in evidence.evidence_history(namespace=namespace)
        if edge.evidence_id == decision.promoted_evidence_id
    )
    assert bridge.project_edge(promoted).promoted is True
    return evidence, addresses, store, bridge, gate, validator, candidate


def _assert_restarted_cycle(
    restored_evidence: EvidenceCore,
    restored_addresses: AddressSpace,
    restored_store: TemporalEventStore,
    restored_bridge: EvidenceTemporalBridge,
    restored_gate: EpistemicLearningGate,
    restored_validator: ResponseValidator,
) -> None:
    assert restored_validator.iter_response_ids() == ("response-1",)
    assert tuple(edge.evidence_id for edge in restored_evidence.iter_evidence()) == (
        "user-alt",
        "response:response-1:claim:1",
        "learning:confirm-response-1",
    )
    restored_candidate = next(
        edge for edge in restored_evidence.iter_evidence()
        if edge.evidence_id == "response:response-1:claim:1"
    )
    assert restored_candidate.provenance == EpistemicSource.LLM_GENERATED.value
    current = restored_store.resolve("meu gato", "nome", TemporalOperator.CURRENT)
    assert restored_store.value_text(current.value_address) == "bob"
    packet = ContextCompiler(
        restored_store,
        projections=restored_bridge.iter_projections(),
    ).compile("Qual é o nome do meu gato?")
    assert packet.facts[-1].value == "bob"

    with pytest.raises(ValueError, match="already been validated"):
        restored_validator.validate(
            packet=packet,
            response_id="response-1",
            response_text="Seu gato se chama Bob.",
            claims=(ResponseClaim("meu gato", "nome", "Bob"),),
            model_id="cloud-llm",
            namespace="default",
        )

    before_events = len(restored_store.iter_events())
    assert restored_bridge.project_edge(restored_candidate).promoted is False
    assert len(restored_store.iter_events()) == before_events
    with pytest.raises(ValueError, match="already been applied"):
        restored_gate.decide(
            restored_candidate,
            decision_id="confirm-response-1",
            accepted=False,
            validator_source=EpistemicSource.USER_CONFIRMED,
            validator_id="user",
            reason="duplicate",
        )

    continued = restored_evidence.observe_relation(
        "meu gato",
        "nome",
        "Bob",
        evidence_id="user-after-restart",
        source_text="Bob continua sendo o nome.",
        provenance="USER_CONFIRMED",
        origin="user",
        namespace="default",
    )
    assert continued.epoch == 3


def test_compile_response_validate_explicit_learn_and_cold_restart_preserves_full_boundary(tmp_path):
    evidence, addresses, store, bridge, gate, validator, candidate = _build_confirmed_model_cycle()
    assert candidate.provenance == EpistemicSource.LLM_GENERATED.value

    backend = FakeAtomicBackend()
    topology_stats = save_snapshot_to_backend(backend, addresses, store)
    audit_stats = save_epistemic_audit_to_backend(backend, bridge, gate, validator)
    persistence = EvidenceCorePersistence(
        tmp_path / "evidence-state",
        backend="sqlite",
        allow_fallback=False,
    )
    receipt = persistence.store(evidence)
    assert topology_stats.bdr_sequence == 1
    assert audit_stats.bdr_sequence == 2
    assert receipt.backend == "sqlite"

    restored_addresses, restored_store = load_snapshot_from_backend(backend)
    restored_evidence = EvidenceCorePersistence(
        tmp_path / "evidence-state",
        backend="sqlite",
        allow_fallback=False,
    ).load(receipt)
    restored_bridge = EvidenceTemporalBridge(restored_addresses, restored_store)
    restored_gate = EpistemicLearningGate(restored_evidence)
    restored_validator = ResponseValidator(restored_evidence)
    loaded = load_epistemic_audit_from_backend(
        backend,
        restored_bridge,
        restored_gate,
        restored_validator,
    )
    assert loaded.response_ids == 1
    _assert_restarted_cycle(
        restored_evidence,
        restored_addresses,
        restored_store,
        restored_bridge,
        restored_gate,
        restored_validator,
    )


def test_real_bdr_cold_restart_preserves_topology_evidence_and_epistemic_state(tmp_path):
    library_path = os.environ.get("BDR_ATOMIC_LIB")
    if not library_path or not native_bdr_available():
        pytest.skip("real BDR atomic ABI and native EvidenceCore BDR extension are required")

    evidence, addresses, store, bridge, gate, validator, candidate = _build_confirmed_model_cycle()
    assert candidate.provenance == EpistemicSource.LLM_GENERATED.value

    topology_root = tmp_path / "topology-audit-bdr"
    evidence_root = tmp_path / "evidence-bdr"
    topology_stats = save_snapshot_bdr(topology_root, library_path, addresses, store)
    audit_stats = save_epistemic_audit_bdr(
        topology_root,
        library_path,
        bridge,
        gate,
        validator,
    )
    evidence_persistence = EvidenceCorePersistence(
        evidence_root,
        backend="bdr",
        allow_fallback=False,
    )
    evidence_receipt = evidence_persistence.store(evidence)

    assert topology_stats.bdr_sequence >= 1
    assert audit_stats.bdr_sequence > topology_stats.bdr_sequence
    assert evidence_receipt.backend == "bdr"

    restored_addresses, restored_store = load_snapshot_bdr(topology_root, library_path)
    restored_evidence = EvidenceCorePersistence(
        evidence_root,
        backend="bdr",
        allow_fallback=False,
    ).load(evidence_receipt)
    restored_bridge = EvidenceTemporalBridge(restored_addresses, restored_store)
    restored_gate = EpistemicLearningGate(restored_evidence)
    restored_validator = ResponseValidator(restored_evidence)
    loaded = load_epistemic_audit_bdr(
        topology_root,
        library_path,
        restored_bridge,
        restored_gate,
        restored_validator,
    )
    assert loaded.response_ids == 1
    _assert_restarted_cycle(
        restored_evidence,
        restored_addresses,
        restored_store,
        restored_bridge,
        restored_gate,
        restored_validator,
    )
