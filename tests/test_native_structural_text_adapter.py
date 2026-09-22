from __future__ import annotations

import os
from pathlib import Path

import pytest

from memoria_resolutiva.native_conversation import NativeConversationService
from memoria_resolutiva.native_runtime import NativeRuntimeManager
from memoria_resolutiva.native_structural_text import NativeStructuralTextService


def _native_library() -> Path:
    value = os.environ.get("MEMORIA_NATIVE_LIB")
    if not value:
        pytest.skip("MEMORIA_NATIVE_LIB is not set; native structural adapter runs in the host ABI workflow")
    path = Path(value)
    assert path.is_file()
    return path


def test_native_structural_text_service_shares_runtime_and_survives_restart(tmp_path: Path) -> None:
    library = _native_library()
    data_dir = tmp_path / "state"
    organization_id = "structural-adapter-org"
    manager = NativeRuntimeManager()

    conversation = NativeConversationService(
        library_path=library,
        data_dir=data_dir,
        organization_id=organization_id,
        runtime_manager=manager,
    )
    structural = NativeStructuralTextService(
        library_path=library,
        data_dir=data_dir,
        organization_id=organization_id,
        runtime_manager=manager,
    )
    try:
        assert manager.active_runtime_count() == 1

        # Assistant/LLM output stored by the normal conversation service is not
        # silently injected into the structural trail.
        conversation.ingest(
            role="assistant",
            text="Meu cachorro se chama Bolt.",
            session_id="s1",
            order=1,
        )
        unresolved = structural.resolve(
            "Qual nome do meu cachorro?",
            hierarchy_id="conversation:s1",
        )
        assert unresolved["status"] == "UNRESOLVED"
        assert unresolved["observation_count"] == 0

        first = structural.observe(
            "Meu gato se chama Alt.",
            hierarchy_id="conversation:s1",
            source_id="m1",
            sequence=1,
        )
        second = structural.observe(
            "Meu gato se chama Alt.",
            hierarchy_id="conversation:s1",
            source_id="m2",
            sequence=2,
        )
        structural.observe(
            "Meu gato dorme no sofa.",
            hierarchy_id="conversation:s1",
            source_id="m3",
            sequence=3,
        )
        structural.observe(
            "Meu cachorro se chama Bolt.",
            hierarchy_id="conversation:s2",
            source_id="x1",
            sequence=1,
        )
        assert first["duplicate"] is False
        assert second["duplicate"] is False

        duplicate = structural.observe(
            "Meu gato se chama Alt.",
            hierarchy_id="conversation:s1",
            source_id="m2",
            sequence=2,
        )
        assert duplicate["duplicate"] is True
        assert duplicate["observation_count"] == 4

        result = structural.resolve(
            "Qual nome do meu gato?",
            hierarchy_id="conversation:s1",
            top_k=3,
        )
        assert result["status"] == "HIT"
        assert result["semantic_projection"] is False
        top = result["contexts"][0]
        assert top["source_text"] == "Meu gato se chama Alt."
        assert top["repetitions"] == 2
        assert set(top["source_ids"]) == {"m1", "m2"}
        assert all(row["source_text"] != "Meu cachorro se chama Bolt." for row in result["contexts"])
        structural.flush()
    finally:
        structural.close()
        assert manager.active_runtime_count() == 1
        conversation.close()
        assert manager.active_runtime_count() == 0

    reopened = NativeStructuralTextService(
        library_path=library,
        data_dir=data_dir,
        organization_id=organization_id,
        runtime_manager=manager,
    )
    try:
        result = reopened.resolve(
            "Qual nome do meu gato?",
            hierarchy_id="conversation:s1",
            top_k=3,
        )
        assert result["status"] == "HIT"
        assert result["contexts"][0]["source_text"] == "Meu gato se chama Alt."
        assert set(result["contexts"][0]["source_ids"]) == {"m1", "m2"}
    finally:
        reopened.close()
        assert manager.active_runtime_count() == 0
