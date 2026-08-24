from __future__ import annotations

from typing import Protocol, runtime_checkable


@runtime_checkable
class BinaryKV(Protocol):
    """Minimal durable binary key/value contract required by Memoria.ia storage.

    The adapter intentionally depends on this small protocol rather than importing
    BDR directly, preserving core/storage decoupling and allowing deterministic
    tests with an in-memory fake backend.
    """

    def put_sync(self, key: bytes | str, value: bytes | str) -> None: ...

    def get(self, key: bytes | str) -> bytes | None: ...

    def delete_sync(self, key: bytes | str) -> None: ...

    def sync(self) -> None: ...

    def checkpoint(self) -> None: ...
