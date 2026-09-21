from pathlib import Path

import pytest

from memoria_resolutiva.bdr_store import native_bdr_available
from memoria_resolutiva.native_resolve import NativeResolveService
from memoria_resolutiva.persistent_address_trajectory_v2 import (
    PersistentAddressTrajectoryStoreV2,
)
from memoria_resolutiva.product_identity import MemoryScope


def _scope(agent_id: str) -> MemoryScope:
    return MemoryScope("org-v2", application_id="server", agent_id=agent_id)


def _seed(store: PersistentAddressTrajectoryStoreV2, session_id: str, shirt: str):
    store.ingest("meu gato e da cor verde", session_id=session_id)
    store.ingest("meu carro e da cor azul", session_id=session_id)
    store.ingest(f"minha camisa e da cor {shirt}", session_id=session_id)


def test_namespaces_are_isolated_and_survive_cold_restart(tmp_path: Path):
    root = tmp_path / "v2"
    first = PersistentAddressTrajectoryStoreV2(
        root,
        backend="sqlite",
        allow_fallback=False,
    )
    _seed(first, "s1", "preta")
    _seed(first, "s2", "branca")

    native_first = NativeResolveService(first)
    assert native_first.resolve(
        scope=_scope("s1"),
        message="qual a cor da minha camisa?",
    ).text == "preta"
    assert native_first.resolve(
        scope=_scope("s2"),
        message="qual a cor da minha camisa?",
    ).text == "branca"

    restarted = PersistentAddressTrajectoryStoreV2(
        root,
        backend="sqlite",
        allow_fallback=False,
    )
    native_restarted = NativeResolveService(restarted)

    result_s1 = native_restarted.resolve(
        scope=_scope("s1"),
        message="qual a cor da minha camisa?",
    )
    result_s2 = native_restarted.resolve(
        scope=_scope("s2"),
        message="qual a cor da minha camisa?",
    )

    assert result_s1.status == "RESOLVED"
    assert result_s1.text == "preta"
    assert result_s1.external_calls == 0
    assert result_s2.status == "RESOLVED"
    assert result_s2.text == "branca"
    assert result_s2.external_calls == 0


def test_durable_backend_is_preferred_over_corrupted_portable_copy(tmp_path: Path):
    root = tmp_path / "v2"
    store = PersistentAddressTrajectoryStoreV2(
        root,
        backend="sqlite",
        allow_fallback=False,
    )
    _seed(store, "s1", "preta")
    snapshot_path, _receipt_path = store._paths("s1")
    snapshot_path.write_bytes(b"corrupted-portable-copy")

    restarted = PersistentAddressTrajectoryStoreV2(
        root,
        backend="sqlite",
        allow_fallback=False,
    )
    result = NativeResolveService(restarted).resolve(
        scope=_scope("s1"),
        message="qual a cor da minha camisa?",
    )

    assert result.status == "RESOLVED"
    assert result.text == "preta"
    assert restarted.persistence.portable_fallback_used is False


def test_unknown_query_does_not_mutate_durable_snapshot(tmp_path: Path):
    store = PersistentAddressTrajectoryStoreV2(
        tmp_path / "v2",
        backend="sqlite",
        allow_fallback=False,
    )
    _seed(store, "s1", "preta")
    before = store.snapshot_bytes("s1")

    result = NativeResolveService(store).resolve(
        scope=_scope("s1"),
        message="token inexistente completamente fora",
    )

    after = store.snapshot_bytes("s1")
    assert result.status == "UNRESOLVED"
    assert result.external_calls == 0
    assert before == after


def test_same_state_serializes_deterministically_after_restart(tmp_path: Path):
    root = tmp_path / "v2"
    store = PersistentAddressTrajectoryStoreV2(
        root,
        backend="sqlite",
        allow_fallback=False,
    )
    _seed(store, "s1", "preta")
    before = store.snapshot_bytes("s1")

    restarted = PersistentAddressTrajectoryStoreV2(
        root,
        backend="sqlite",
        allow_fallback=False,
    )
    after = restarted.snapshot_bytes("s1")
    assert before == after


@pytest.mark.skipif(not native_bdr_available(), reason="native BDR extension not built")
def test_v2_namespaced_restart_on_native_bdr(tmp_path: Path):
    root = tmp_path / "v2-bdr"
    store = PersistentAddressTrajectoryStoreV2(
        root,
        backend="bdr",
        allow_fallback=False,
    )
    _seed(store, "s1", "preta")

    restarted = PersistentAddressTrajectoryStoreV2(
        root,
        backend="bdr",
        allow_fallback=False,
    )
    result = NativeResolveService(restarted).resolve(
        scope=_scope("s1"),
        message="qual a cor da minha camisa?",
    )
    assert result.status == "RESOLVED"
    assert result.text == "preta"
    assert restarted.backend == "bdr"
