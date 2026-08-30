import ctypes
import json
import os
from pathlib import Path

import pytest

from memoria_resolutiva.product_conversation import ConversationSemanticService
from memoria_resolutiva.product_evidence import ProductEvidenceService


FIXTURES = (
    Path(__file__).parent / "fixtures" / "native_semantic_slice1.json",
    Path(__file__).parent / "fixtures" / "native_semantic_slice2.json",
)


class NativeBuffer(ctypes.Structure):
    _fields_ = [
        ("data", ctypes.POINTER(ctypes.c_uint8)),
        ("size", ctypes.c_size_t),
    ]


def _load_native():
    lib_path = os.environ.get("MEMORIA_NATIVE_LIB")
    if not lib_path:
        pytest.skip("MEMORIA_NATIVE_LIB is not set; native parity is exercised by the host ABI workflow")
    lib = ctypes.CDLL(lib_path)
    lib.memoria_mobile_abi_version.restype = ctypes.c_uint32
    lib.memoria_mobile_open.argtypes = [ctypes.c_char_p, ctypes.c_char_p, ctypes.POINTER(ctypes.c_void_p)]
    lib.memoria_mobile_open.restype = ctypes.c_int
    lib.memoria_mobile_learn_turn_json.argtypes = [ctypes.c_void_p, NativeBuffer, ctypes.POINTER(NativeBuffer)]
    lib.memoria_mobile_learn_turn_json.restype = ctypes.c_int
    lib.memoria_mobile_resolve_context_json.argtypes = [ctypes.c_void_p, NativeBuffer, ctypes.POINTER(NativeBuffer)]
    lib.memoria_mobile_resolve_context_json.restype = ctypes.c_int
    lib.memoria_mobile_flush.argtypes = [ctypes.c_void_p]
    lib.memoria_mobile_flush.restype = ctypes.c_int
    lib.memoria_mobile_free_buffer.argtypes = [NativeBuffer]
    lib.memoria_mobile_close.argtypes = [ctypes.c_void_p]
    return lib


def _request(lib, fn_name, handle, payload):
    raw = json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    backing = ctypes.create_string_buffer(raw)
    request = NativeBuffer(ctypes.cast(backing, ctypes.POINTER(ctypes.c_uint8)), len(raw))
    response = NativeBuffer()
    status = getattr(lib, fn_name)(handle, request, ctypes.byref(response))
    try:
        body = ctypes.string_at(response.data, response.size).decode("utf-8") if response.data else ""
        return status, json.loads(body) if body else {}
    finally:
        if response.data:
            lib.memoria_mobile_free_buffer(response)


def _normalize_native(status, body):
    normalized_status = "HIT" if status == 0 else "UNRESOLVED" if status == 2 else f"STATUS_{status}"
    return {
        "status": body.get("status", normalized_status),
        "selected_context": body.get("selected_context", ""),
    }


def _python_result(case, root):
    evidence = ProductEvidenceService.open(root / "python")
    service = ConversationSemanticService(evidence)
    ids = {}
    for source in case["sources"]:
        parents = [ids[p] for p in source.get("parent_memory_ids", [])]
        corrections = [ids[p] for p in source.get("corrects_memory_ids", [])]
        result = service.ingest(
            role=source["role"],
            text=source["text"],
            session_id=case["name"],
            order=source["order"],
            parent_memory_ids=parents,
            corrects_memory_ids=corrections,
        )
        ids[source["memory_id"]] = result.memory_ids[0]
    resolved = service.resolve(query=case["query"], session_id=case["name"])
    return {"status": resolved.status, "selected_context": resolved.selected_context}


def _native_result(lib, case, root):
    handle = ctypes.c_void_p()
    native_dir = root / "native"
    native_dir.mkdir(parents=True, exist_ok=True)
    assert lib.memoria_mobile_open(str(native_dir).encode(), case["name"].encode(), ctypes.byref(handle)) == 0
    try:
        for source in case["sources"]:
            parents = source.get("parent_memory_ids", [])
            corrections = source.get("corrects_memory_ids", [])
            payload = {
                "role": source["role"],
                "text": source["text"],
                "memory_id": source["memory_id"],
                "order": source["order"],
            }
            if source["role"] == "assistant":
                payload["source_type"] = "assistant_generated"
                payload["source_authority"] = 0.25
            elif corrections:
                payload["source_type"] = "user_correction"
                payload["source_authority"] = 1.0
                payload["corrects_memory_ids"] = corrections
            else:
                payload["source_type"] = "user_assertion"
                payload["source_authority"] = 0.95
            if parents:
                # Same explicit lineage contract as Python: the native core must derive
                # the active ultimate source rather than receiving a precomputed root.
                payload["parent_memory_ids"] = parents
            status, _ = _request(lib, "memoria_mobile_learn_turn_json", handle, payload)
            assert status == 0, case["name"]

        status, body = _request(
            lib,
            "memoria_mobile_resolve_context_json",
            handle,
            {"query": case["query"]},
        )
        first = _normalize_native(status, body)
        assert lib.memoria_mobile_flush(handle) == 0
    finally:
        lib.memoria_mobile_close(handle)

    # The same normalized result must survive the native BDR-backed reopen.
    reopened = ctypes.c_void_p()
    assert lib.memoria_mobile_open(str(native_dir).encode(), case["name"].encode(), ctypes.byref(reopened)) == 0
    try:
        status, body = _request(
            lib,
            "memoria_mobile_resolve_context_json",
            reopened,
            {"query": case["query"]},
        )
        after_restart = _normalize_native(status, body)
    finally:
        lib.memoria_mobile_close(reopened)
    assert after_restart == first, f"native-restart:{case['name']}"
    return first


def test_python_and_native_share_semantic_reference_vectors(tmp_path):
    lib = _load_native()
    assert lib.memoria_mobile_abi_version() == 1

    for fixture in FIXTURES:
        data = json.loads(fixture.read_text("utf-8"))
        for case in data["cases"]:
            case_root = tmp_path / f"v{data['version']}-{case['name']}"
            expected = {
                "status": case["expected_status"],
                "selected_context": case["expected_context"],
            }
            python_result = _python_result(case, case_root)
            native_result = _native_result(lib, case, case_root)

            assert python_result == expected, f"python:{case['name']}"
            assert native_result == expected, f"native:{case['name']}"
            assert native_result == python_result, f"parity:{case['name']}"
