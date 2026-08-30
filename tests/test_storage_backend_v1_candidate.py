from __future__ import annotations

import pytest

import memoria_resolutiva.storage_backend as storage_backend
from memoria_resolutiva.sqlite_store import SQLiteResolutiveMemory


def test_explicit_sqlite_backend_opens_sqlite(tmp_path):
    memory = storage_backend.open_resolutive_memory(
        tmp_path / "state",
        backend="sqlite",
    )
    try:
        assert isinstance(memory, SQLiteResolutiveMemory)
        memory.add("m1", b"candidate")
        assert memory.reconstruct("m1") == b"candidate"
    finally:
        memory.close()


def test_linux_prefers_bdr_by_default(monkeypatch):
    monkeypatch.delenv("MEMORIA_STORAGE_BACKEND", raising=False)
    monkeypatch.setattr(storage_backend.platform, "system", lambda: "Linux")
    assert storage_backend.preferred_backend() == "bdr"


def test_non_linux_prefers_sqlite_by_default(monkeypatch):
    monkeypatch.delenv("MEMORIA_STORAGE_BACKEND", raising=False)
    monkeypatch.setattr(storage_backend.platform, "system", lambda: "Windows")
    assert storage_backend.preferred_backend() == "sqlite"


def test_environment_override_is_respected(monkeypatch):
    monkeypatch.setenv("MEMORIA_STORAGE_BACKEND", "SQLite")
    monkeypatch.setattr(storage_backend.platform, "system", lambda: "Linux")
    assert storage_backend.preferred_backend() == "sqlite"


def test_missing_linux_native_bdr_falls_back_to_sqlite(monkeypatch, tmp_path):
    monkeypatch.setattr(storage_backend.platform, "system", lambda: "Linux")
    monkeypatch.setattr(storage_backend, "native_bdr_available", lambda: False)

    with pytest.warns(RuntimeWarning, match="falling back to SQLite"):
        memory = storage_backend.open_resolutive_memory(
            tmp_path / "state",
            backend="bdr",
            allow_fallback=True,
        )
    try:
        assert isinstance(memory, SQLiteResolutiveMemory)
    finally:
        memory.close()


def test_explicit_bdr_without_fallback_fails_closed(monkeypatch, tmp_path):
    monkeypatch.setattr(storage_backend.platform, "system", lambda: "Linux")
    monkeypatch.setattr(storage_backend, "native_bdr_available", lambda: False)

    with pytest.raises(RuntimeError, match="BDR requested"):
        storage_backend.open_resolutive_memory(
            tmp_path / "state",
            backend="bdr",
            allow_fallback=False,
        )


def test_unknown_backend_is_rejected(tmp_path):
    with pytest.raises(ValueError, match="unsupported storage backend"):
        storage_backend.open_resolutive_memory(
            tmp_path / "state",
            backend="unknown",
        )
