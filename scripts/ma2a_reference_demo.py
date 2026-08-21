from memoria_resolutiva.a2a import (
    Ed25519Identity,
    Frame,
    InMemoryTrajectoryStore,
    MessageType,
    ReplayGuard,
)


def main() -> None:
    sender = Ed25519Identity.generate()
    receiver_store = InMemoryTrajectoryStore()
    replay_guard = ReplayGuard()
    trajectory = ("shared", "global", "demo", "temperature")

    frame = Frame(
        type=MessageType.DELTA_EMIT,
        node_id=sender.node_id,
        session_id="demo-session",
        sequence=1,
        trajectory=trajectory,
        payload={"celsius": 23.5},
    )
    signed = sender.sign(frame)

    Ed25519Identity.verify(signed, sender.public_key_bytes)
    replay_guard.accept(signed)
    resulting_hash = receiver_store.apply_delta(
        trajectory=signed.trajectory or (),
        delta=signed.payload or {},
        message_id=signed.message_id,
    )

    print("MA2A/0.1 reference demo: PASS")
    print(f"sender={sender.node_id}")
    print(f"trajectory={list(trajectory)}")
    print(f"resolved={receiver_store.resolve(trajectory)}")
    print(f"state_hash={resulting_hash}")


if __name__ == "__main__":
    main()
