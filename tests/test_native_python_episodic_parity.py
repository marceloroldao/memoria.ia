import ctypes
import json
import os
from pathlib import Path

import pytest

from memoria_resolutiva.product_episodic import (
    EpisodeRecallRequest,
    EpisodeStoreRequest,
    ProductEpisodicService,
)
from memoria_resolutiva.product_evidence import ProductEvidenceService


FIXTURE = Path(__file__).parent / "fixtures" / "native_episodic_slice3.json"


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
    lib.memoria_mobile_store_episode_json.argtypes = [ctypes.c_void_p, NativeBuffer, ctypes.POINTER(NativeBuffer)]
    lib.memoria_mobile_store_episode_json.restype = ctypes.c_int
    lib.memoria_mobile_recall_episode_json.argtypes = [ctypes.c_void_p, NativeBuffer, ctypes.POINTER(NativeBuffer)]
    lib.memoria_mobile_recall_episode_json.restype = ctypes.c_int
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


def _normalized(status, context):
    return {"status": status, "selected_context": context}


def _python_result(case, root):
    evidence_root = root / "python"
    service = ProductEpisodicService(ProductEvidenceService.open(evidence_root))
    for episode in case["episodes"]:
        service.store(EpisodeStoreRequest(
            episode_id=episode["episode_id"],
            role=episode["role"],
            text=episode["text"],
            session_id=case["name"],
            order=episode["order"],
            timestamp=episode.get("timestamp"),
            event_type=episode.get("event_type"),
            topics=episode.get("topics", []),
        ))
    request = EpisodeRecallRequest(
        query=case["query"],
        session_id=case["name"],
        role=case.get("role"),
        event_type=case.get("event_type"),
        topics=case.get("topics", []),
    )
    first = service.resolve(request)
    normalized = _normalized(first.status, first.selected_context)

    restarted = ProductEpisodicService(ProductEvidenceService.open(evidence_root))
    after = restarted.resolve(request)
    after_restart = _normalized(after.status, after.selected_context)
    assert after_restart == normalized, f"python-restart:{case['name']}"
    return normalized


def _native_recall(lib, handle, case):
    payload = {"query": case["query"], "session_id": case["name"]}
    if case.get("role"):
        payload["role"] = case["role"]
    if case.get("event_type"):
        payload["event_type"] = case["event_type"]
    if case.get("topics"):
        payload["topics_csv"] = ",".join(case["topics"])
    status, body = _request(lib, "memoria_mobile_recall_episode_json", handle, payload)
    normalized_status = "HIT" if status == 0 else "UNRESOLVED" if status == 2 else f"STATUS_{status}"
    return _normalized(body.get("status", normalized_status), body.get("selected_context", ""))


def _native_result(lib, case, root):
    handle = ctypes.c_void_p()
    native_dir = root / "native"
    native_dir.mkdir(parents=True, exist_ok=True)
    assert lib.memoria_mobile_open(str(native_dir).encode(), case["name"].encode(), ctypes.byref(handle)) == 0
    try:
        for episode in case["episodes"]:
            payload = {
                "episode_id": episode["episode_id"],
                "session_id": case["name"],
                "role": episode["role"],
                "text": episode["text"],
                "order": episode["order"],
                "timestamp": episode.get("timestamp", ""),
                "event_type": episode.get("event_type", ""),
                "topics_csv": ",".join(episode.get("topics", [])),
            }
            status, _ = _request(lib, "memoria_mobile_store_episode_json", handle, payload)
            assert status == 0, case["name"]
        first = _native_recall(lib, handle, case)
        assert lib.memoria_mobile_flush(handle) == 0
    finally:
        lib.memoria_mobile_close(handle)

    reopened = ctypes.c_void_p()
    assert lib.memoria_mobile_open(str(native_dir).encode(), case["name"].encode(), ctypes.byref(reopened)) == 0
    try:
        after_restart = _native_recall(lib, reopened, case)
    finally:
        lib.memoria_mobile_close(reopened)
    assert after_restart == first, f"native-restart:{case['name']}"
    return first


def _python_cross_session(root: Path):
    evidence_root = root / "python-cross-session"
    service = ProductEpisodicService(ProductEvidenceService.open(evidence_root))
    rows = (
        ("s1-old", "s1", "atlas status report session one old", 10),
        ("s2", "s2", "atlas status report session two", 20),
        ("s1-new", "s1", "atlas status report session one new", 15),
    )
    for episode_id, session_id, text, order in rows:
        service.store(EpisodeStoreRequest(
            episode_id=episode_id,
            role="assistant",
            text=text,
            session_id=session_id,
            order=order,
            event_type="report",
            topics=["atlas", "status"],
        ))

    def recall(session_id):
        result = service.resolve(EpisodeRecallRequest(
            query="latest atlas status report",
            session_id=session_id,
            role="assistant",
            event_type="report",
            topics=["atlas", "status"],
        ))
        return _normalized(result.status, result.selected_context)

    before = {
        "s1": recall("s1"),
        "s2": recall("s2"),
        "default": recall(None),
    }
    restarted = ProductEpisodicService(ProductEvidenceService.open(evidence_root))

    def recall_after(session_id):
        result = restarted.resolve(EpisodeRecallRequest(
            query="latest atlas status report",
            session_id=session_id,
            role="assistant",
            event_type="report",
            topics=["atlas", "status"],
        ))
        return _normalized(result.status, result.selected_context)

    after = {
        "s1": recall_after("s1"),
        "s2": recall_after("s2"),
        "default": recall_after(None),
    }
    assert after == before
    return before


def _native_cross_session(lib, root: Path):
    native_dir = root / "native-cross-session"
    native_dir.mkdir(parents=True, exist_ok=True)
    handle = ctypes.c_void_p()
    assert lib.memoria_mobile_open(str(native_dir).encode(), b"cross-session-org", ctypes.byref(handle)) == 0
    rows = (
        ("s1-old", "s1", "atlas status report session one old", 10),
        ("s2", "s2", "atlas status report session two", 20),
        ("s1-new", "s1", "atlas status report session one new", 15),
    )
    try:
        for episode_id, session_id, text, order in rows:
            status, _ = _request(lib, "memoria_mobile_store_episode_json", handle, {
                "episode_id": episode_id,
                "session_id": session_id,
                "role": "assistant",
                "text": text,
                "order": order,
                "event_type": "report",
                "topics_csv": "atlas,status",
            })
            assert status == 0

        def recall(session_id):
            payload = {
                "query": "latest atlas status report",
                "role": "assistant",
                "event_type": "report",
                "topics_csv": "atlas,status",
            }
            if session_id is not None:
                payload["session_id"] = session_id
            status, body = _request(lib, "memoria_mobile_recall_episode_json", handle, payload)
            normalized_status = "HIT" if status == 0 else "UNRESOLVED" if status == 2 else f"STATUS_{status}"
            return _normalized(body.get("status", normalized_status), body.get("selected_context", ""))

        before = {
            "s1": recall("s1"),
            "s2": recall("s2"),
            "default": recall(None),
        }
        assert lib.memoria_mobile_flush(handle) == 0
    finally:
        lib.memoria_mobile_close(handle)

    reopened = ctypes.c_void_p()
    assert lib.memoria_mobile_open(str(native_dir).encode(), b"cross-session-org", ctypes.byref(reopened)) == 0
    try:
        def recall_after(session_id):
            payload = {
                "query": "latest atlas status report",
                "role": "assistant",
                "event_type": "report",
                "topics_csv": "atlas,status",
            }
            if session_id is not None:
                payload["session_id"] = session_id
            status, body = _request(lib, "memoria_mobile_recall_episode_json", reopened, payload)
            normalized_status = "HIT" if status == 0 else "UNRESOLVED" if status == 2 else f"STATUS_{status}"
            return _normalized(body.get("status", normalized_status), body.get("selected_context", ""))

        after = {
            "s1": recall_after("s1"),
            "s2": recall_after("s2"),
            "default": recall_after(None),
        }
    finally:
        lib.memoria_mobile_close(reopened)
    assert after == before
    return before


def test_python_and_native_share_episodic_reference_vectors(tmp_path):
    lib = _load_native()
    assert lib.memoria_mobile_abi_version() == 1
    data = json.loads(FIXTURE.read_text("utf-8"))

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


def test_python_and_native_isolate_episodes_by_session(tmp_path):
    lib = _load_native()
    expected = {
        "s1": {"status": "HIT", "selected_context": "atlas status report session one new"},
        "s2": {"status": "HIT", "selected_context": "atlas status report session two"},
        "default": {"status": "UNRESOLVED", "selected_context": ""},
    }
    python_result = _python_cross_session(tmp_path)
    native_result = _native_cross_session(lib, tmp_path)
    assert python_result == expected
    assert native_result == expected
    assert native_result == python_result
