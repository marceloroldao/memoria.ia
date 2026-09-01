from __future__ import annotations

import os
from pathlib import Path

import pytest

from memoria_resolutiva.native_conversation import NativeConversationService


def _native_library() -> Path:
    value = os.environ.get("MEMORIA_NATIVE_LIB")
    if not value:
        pytest.skip("MEMORIA_NATIVE_LIB is not set")
    path = Path(value)
    assert path.is_file()
    return path


def _service(root: Path, library: Path) -> NativeConversationService:
    return NativeConversationService(
        library_path=library,
        data_dir=root / "native-lineage-state",
        organization_id="session-lineage-org",
    )


def _turns(service: NativeConversationService) -> list[dict[str, object]]:
    status, snapshot = service._call(
        "memoria_mobile_export_snapshot_json",
        {"turn_offset": 0, "turn_limit": 64, "episode_offset": 0, "episode_limit": 1},
    )
    assert status == 0
    assert snapshot["status"] == "OK"
    rows = snapshot["turns"]
    assert isinstance(rows, list)
    return rows


def _turn(service: NativeConversationService, memory_id: str) -> dict[str, object]:
    for row in _turns(service):
        if row.get("memory_id") == memory_id:
            return row
    raise AssertionError(f"turn not found: {memory_id}")


def test_session_lineage_is_scoped_explicit_and_restart_durable(tmp_path: Path):
    library = _native_library()
    service = _service(tmp_path, library)
    try:
        first = service.ingest(role="user", text="alpha stage is one", session_id="s-alpha", order=1)
        first_id = first.memory_ids[0]
        assert _turn(service, first_id).get("parent_memory_ids") == []

        # Conversational adjacency alone is not evidence for assistant output.
        second = service.ingest(role="assistant", text="alpha stage remains one", session_id="s-alpha", order=2)
        second_id = second.memory_ids[0]
        assert _turn(service, second_id).get("parent_memory_ids") == []

        other = service.ingest(role="user", text="beta stage is one", session_id="s-beta", order=1)
        other_id = other.memory_ids[0]
        assert _turn(service, other_id).get("parent_memory_ids") == []

        # An explicit assistant parent remains available when the caller deliberately
        # establishes an evidential/derivation link.
        explicit = service.ingest(
            role="assistant",
            text="alpha explicit branch",
            session_id="s-alpha",
            order=3,
            parent_memory_ids=[first_id],
        )
        explicit_id = explicit.memory_ids[0]
        assert _turn(service, explicit_id).get("parent_memory_ids") == [first_id]

        correction_root = service.ingest(role="user", text="gamma mode is off", session_id="s-fix", order=1)
        correction_root_id = correction_root.memory_ids[0]
        corrected = service.ingest(
            role="user",
            text="gamma mode is on",
            session_id="s-fix",
            order=2,
            corrects_memory_ids=[correction_root_id],
        )
        corrected_id = corrected.memory_ids[0]
        assert _turn(service, corrected_id).get("parent_memory_ids") == [correction_root_id]

        service.flush()
    finally:
        service.close()

    reopened = _service(tmp_path, library)
    try:
        # User chronology can point to the latest durable turn without borrowing its
        # factual authority, because user_assertion is not a traceable derived source.
        after_restart = reopened.ingest(
            role="user",
            text="alpha continued after restart",
            session_id="s-alpha",
            order=4,
        )
        after_restart_id = after_restart.memory_ids[0]
        assert _turn(reopened, after_restart_id).get("parent_memory_ids") == [explicit_id]
        assert other_id not in _turn(reopened, after_restart_id).get("parent_memory_ids", [])
        assert second_id not in _turn(reopened, after_restart_id).get("parent_memory_ids", [])
    finally:
        reopened.close()
