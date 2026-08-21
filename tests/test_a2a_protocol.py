import pytest

from memoria_resolutiva.a2a import (
    Ed25519Identity,
    Frame,
    InMemoryTrajectoryStore,
    MessageType,
    NamespaceForbidden,
    ReplayDetected,
    ReplayGuard,
    SignatureError,
    canonical_trajectory_bytes,
    deterministic_conflict_key,
    enforce_transport_namespace,
    state_hash,
    trajectory_id,
)


def test_trajectory_encoding_is_unambiguous_and_stable():
    a = canonical_trajectory_bytes(["shared", "global", "x"])
    b = canonical_trajectory_bytes(["sharedglobal", "x"])
    assert a != b
    assert trajectory_id(["shared", "global", "x"]) == trajectory_id(
        ["shared", "global", "x"]
    )


def test_private_namespace_is_rejected_before_transport():
    with pytest.raises(NamespaceForbidden):
        enforce_transport_namespace(["user", "private", "secret"])

    frame = Frame(
        type=MessageType.DELTA_EMIT,
        node_id="agent:test",
        session_id="s1",
        sequence=1,
        trajectory=("user", "private", "secret"),
        payload={"value": 1},
    )
    with pytest.raises(NamespaceForbidden):
        frame.signing_bytes()


def test_only_explicit_sync_namespaces_are_allowed():
    assert enforce_transport_namespace(["shared", "global", "x"])
    assert enforce_transport_namespace(["agent", "peer", "x"])
    with pytest.raises(NamespaceForbidden):
        enforce_transport_namespace(["unknown", "x"])


def test_delta_application_is_idempotent():
    store = InMemoryTrajectoryStore()
    path = ["shared", "global", "workflow", "step_01"]

    first_hash = store.apply_delta(
        trajectory=path,
        delta={"status": "complete", "revision": 1},
        message_id="delta-1",
    )
    second_hash = store.apply_delta(
        trajectory=path,
        delta={"status": "corrupted-attempt"},
        message_id="delta-1",
    )

    assert first_hash == second_hash
    assert store.resolve(path) == {"status": "complete", "revision": 1}


def test_resolve_returns_copy_not_mutable_internal_state():
    store = InMemoryTrajectoryStore()
    path = ["shared", "global", "machine", "motor"]
    store.apply_delta(trajectory=path, delta={"rpm": 1700}, message_id="d1")
    resolved = store.resolve(path)
    assert resolved is not None
    resolved["rpm"] = 1
    assert store.resolve(path) == {"rpm": 1700}


def test_state_hash_is_canonical_across_key_order():
    assert state_hash({"a": 1, "b": 2}) == state_hash({"b": 2, "a": 1})


def test_replay_guard_rejects_duplicate_and_non_monotonic_sequence():
    guard = ReplayGuard()
    frame1 = Frame(
        type=MessageType.HEARTBEAT,
        node_id="agent:A",
        session_id="s1",
        sequence=1,
        message_id="m1",
    )
    guard.accept(frame1)

    with pytest.raises(ReplayDetected):
        guard.accept(frame1)

    with pytest.raises(ReplayDetected):
        guard.accept(
            Frame(
                type=MessageType.HEARTBEAT,
                node_id="agent:A",
                session_id="s1",
                sequence=1,
                message_id="m2",
            )
        )


def test_ed25519_sign_verify_and_tamper_detection():
    identity = Ed25519Identity.generate()
    frame = Frame(
        type=MessageType.DELTA_EMIT,
        node_id=identity.node_id,
        session_id="session-1",
        sequence=7,
        trajectory=("shared", "global", "machine", "motor_01"),
        payload={"rpm": 1750},
    )
    signed = identity.sign(frame)
    Ed25519Identity.verify(signed, identity.public_key_bytes)

    tampered = Frame(
        type=signed.type,
        node_id=signed.node_id,
        session_id=signed.session_id,
        sequence=signed.sequence,
        timestamp_ms=signed.timestamp_ms,
        message_id=signed.message_id,
        trajectory=signed.trajectory,
        payload={"rpm": 9999},
        signature=signed.signature,
    )
    with pytest.raises(SignatureError):
        Ed25519Identity.verify(tampered, identity.public_key_bytes)


def test_deterministic_conflict_tie_break_is_total_order():
    a = deterministic_conflict_key(
        logical_counter=3,
        timestamp_ms=100,
        node_id="agent:A",
        message_id="m1",
    )
    b = deterministic_conflict_key(
        logical_counter=3,
        timestamp_ms=100,
        node_id="agent:B",
        message_id="m2",
    )
    assert a < b
