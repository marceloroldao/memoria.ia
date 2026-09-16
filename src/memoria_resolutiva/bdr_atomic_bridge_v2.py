from __future__ import annotations

import ctypes
from pathlib import Path
from typing import Iterable


class BDRAtomicError(RuntimeError):
    pass


class _Operation(ctypes.Structure):
    _fields_ = [("type", ctypes.c_int), ("key", ctypes.c_void_p), ("key_size", ctypes.c_size_t), ("value", ctypes.c_void_p), ("value_size", ctypes.c_size_t)]


class _Buffer(ctypes.Structure):
    _fields_ = [("data", ctypes.POINTER(ctypes.c_uint8)), ("size", ctypes.c_size_t)]


class _BatchResult(ctypes.Structure):
    _fields_ = [("sequence", ctypes.c_uint64), ("operations", ctypes.c_size_t), ("durable", ctypes.c_int)]


class BDRAtomicV2:
    PUT = 1
    ASYNC = 0
    BATCH_SYNC = 1
    PER_OPERATION_SYNC = 2

    def __init__(self, library_path: str | Path, directory: str | Path, durability: int = BATCH_SYNC) -> None:
        self._lib = ctypes.CDLL(str(library_path))
        self._handle = ctypes.c_void_p()
        self._durability = int(durability)
        self._configure()
        if int(self._lib.bdr_atomic_c_abi_version()) != 2:
            raise BDRAtomicError("published validation bridge requires Atomic C ABI v2")
        self._check(self._lib.bdr_atomic_c_open(str(directory).encode(), ctypes.byref(self._handle)), "open")

    def _configure(self) -> None:
        lib = self._lib
        lib.bdr_atomic_c_abi_version.restype = ctypes.c_uint32
        lib.bdr_atomic_c_open.argtypes = [ctypes.c_char_p, ctypes.POINTER(ctypes.c_void_p)]
        lib.bdr_atomic_c_open.restype = ctypes.c_int
        lib.bdr_atomic_c_write_batch_with_durability.argtypes = [ctypes.c_void_p, ctypes.POINTER(_Operation), ctypes.c_size_t, ctypes.c_int, ctypes.POINTER(_BatchResult)]
        lib.bdr_atomic_c_write_batch_with_durability.restype = ctypes.c_int
        lib.bdr_atomic_c_get.argtypes = [ctypes.c_void_p, ctypes.c_void_p, ctypes.c_size_t, ctypes.POINTER(_Buffer)]
        lib.bdr_atomic_c_get.restype = ctypes.c_int
        lib.bdr_atomic_c_free_buffer.argtypes = [_Buffer]
        lib.bdr_atomic_c_sync.argtypes = [ctypes.c_void_p]
        lib.bdr_atomic_c_sync.restype = ctypes.c_int
        lib.bdr_atomic_c_last_sequence.argtypes = [ctypes.c_void_p, ctypes.POINTER(ctypes.c_uint64)]
        lib.bdr_atomic_c_last_sequence.restype = ctypes.c_int
        lib.bdr_atomic_c_durable_sequence.argtypes = [ctypes.c_void_p, ctypes.POINTER(ctypes.c_uint64)]
        lib.bdr_atomic_c_durable_sequence.restype = ctypes.c_int
        lib.bdr_atomic_c_close.argtypes = [ctypes.c_void_p]

    @staticmethod
    def _check(status: int, operation: str) -> None:
        if int(status) != 0:
            raise BDRAtomicError(f"BDR {operation} failed with status={int(status)}")

    def write_batch(self, puts: list[tuple[bytes, bytes]]) -> int:
        if not puts:
            raise ValueError("empty logical BDR batch")
        operations = (_Operation * len(puts))()
        keepalive: list[ctypes.Array[ctypes.c_char]] = []
        for index, (key, value) in enumerate(puts):
            key_buf = ctypes.create_string_buffer(bytes(key))
            value_buf = ctypes.create_string_buffer(bytes(value))
            keepalive.extend((key_buf, value_buf))
            operations[index] = _Operation(self.PUT, ctypes.cast(key_buf, ctypes.c_void_p), len(key), ctypes.cast(value_buf, ctypes.c_void_p), len(value))
        result = _BatchResult()
        self._check(self._lib.bdr_atomic_c_write_batch_with_durability(self._handle, operations, len(puts), self._durability, ctypes.byref(result)), "write_batch")
        return int(result.sequence)

    def get(self, key: bytes) -> bytes | None:
        key_buf = ctypes.create_string_buffer(bytes(key))
        out = _Buffer()
        status = int(self._lib.bdr_atomic_c_get(self._handle, ctypes.cast(key_buf, ctypes.c_void_p), len(key), ctypes.byref(out)))
        if status == 2:
            return None
        self._check(status, "get")
        try:
            return ctypes.string_at(out.data, out.size) if out.size else b""
        finally:
            self._lib.bdr_atomic_c_free_buffer(out)

    def sync(self) -> None:
        self._check(self._lib.bdr_atomic_c_sync(self._handle), "sync")

    def last_sequence(self) -> int:
        value = ctypes.c_uint64()
        self._check(self._lib.bdr_atomic_c_last_sequence(self._handle, ctypes.byref(value)), "last_sequence")
        return int(value.value)

    def durable_sequence(self) -> int:
        value = ctypes.c_uint64()
        self._check(self._lib.bdr_atomic_c_durable_sequence(self._handle, ctypes.byref(value)), "durable_sequence")
        return int(value.value)

    def close(self) -> None:
        if self._handle:
            self._lib.bdr_atomic_c_close(self._handle)
            self._handle = ctypes.c_void_p()

    def __enter__(self) -> "BDRAtomicV2":
        return self

    def __exit__(self, exc_type: object, exc: object, tb: object) -> None:
        self.close()
