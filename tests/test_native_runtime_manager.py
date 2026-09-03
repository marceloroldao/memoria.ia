from __future__ import annotations

import os
from pathlib import Path
import shutil

import pytest

from memoria_resolutiva.conversation_episodic_bridge import AutoEpisodicConversationService
from memoria_resolutiva.native_conversation import NativeConversationService
from memoria_resolutiva.native_episodic import NativeEpisodicService
from memoria_resolutiva.native_runtime import NativeRuntimeManager
from memoria_resolutiva.product_episodic import EpisodeRecallRequest, EpisodeStoreRequest


def _native_library() -> Path:
    value = os.environ.get("MEMORIA_NATIVE_LIB")
    if not value:
        pytest.skip("MEMORIA_NATIVE_LIB is not set; native runtime manager runs in the host ABI workflow")
    path = Path(value)
    assert path.is_file()
    return path


def test_conversation_and_episodic_share_one_runtime_and_survive_release_restart(tmp_path: Path):
    library = _native_library()
    store = tmp_path / "shared-native-store"
    manager = NativeRuntimeManager()

    conversation = NativeConversationService(
        library_path=library,
        data_dir=store,
        organization_id="shared-runtime-org",
        runtime_manager=manager,
    )
    episodic = NativeEpisodicService(
        library_path=library,
        data_dir=store,
        organization_id="shared-runtime-org",
        runtime_manager=manager,
    )
    assert manager.active_runtime_count() == 1
    assert conversation._runtime_lease.runtime is episodic._runtime_lease.runtime

    try:
        conversation.ingest(
            role="user",
            text="sensor = active",
            session_id="conversation",
            order=1,
            timestamp="2026-08-29T18:00:00Z",
        )
        episodic.store(EpisodeStoreRequest(
            episode_id="episode-1",
            role="user",
            text="atlas status report shared runtime",
            session_id="episodes",
            order=2,
            timestamp="2026-08-29T18:01:00Z",
            event_type="report",
            topics=["atlas", "status"],
        ))

        conversation.close()
        assert manager.active_runtime_count() == 1
        recalled = episodic.resolve(EpisodeRecallRequest(
            query="latest atlas status report",
            session_id="episodes",
            role="user",
            event_type="report",
            topics=["atlas", "status"],
        ))
        assert recalled.status == "HIT"
        assert recalled.episode_ids == ("episode-1",)
        episodic.flush()
    finally:
        conversation.close()
        episodic.close()

    assert manager.active_runtime_count() == 0

    reopened_conversation = NativeConversationService(
        library_path=library,
        data_dir=store,
        organization_id="shared-runtime-org",
        runtime_manager=manager,
    )
    reopened_episodic = NativeEpisodicService(
        library_path=library,
        data_dir=store,
        organization_id="shared-runtime-org",
        runtime_manager=manager,
    )
    try:
        assert manager.active_runtime_count() == 1
        resolved = reopened_conversation.resolve(query="sensor active", session_id="conversation")
        assert resolved.status == "HIT"
        assert resolved.selected_context == "sensor = active"
        recalled = reopened_episodic.resolve(EpisodeRecallRequest(
            query="latest atlas status report",
            session_id="episodes",
            role="user",
            event_type="report",
            topics=["atlas", "status"],
        ))
        assert recalled.status == "HIT"
        assert recalled.episode_ids == ("episode-1",)
    finally:
        reopened_conversation.close()
        reopened_episodic.close()

    assert manager.active_runtime_count() == 0


def test_native_auto_episode_forms_from_user_fact_and_survives_restart(tmp_path: Path):
    library = _native_library()
    store = tmp_path / "auto-episode-store"
    manager = NativeRuntimeManager()
    conversation = NativeConversationService(
        library_path=library,
        data_dir=store,
        organization_id="auto-episode-org",
        runtime_manager=manager,
    )
    episodic = NativeEpisodicService(
        library_path=library,
        data_dir=store,
        organization_id="auto-episode-org",
        runtime_manager=manager,
    )
    bridge = AutoEpisodicConversationService(conversation, episodic)
    try:
        result = bridge.ingest(
            role="user",
            text="sensor = active",
            session_id="chat",
            order=1,
            timestamp="2026-09-03T22:31:00Z",
        )
        turn_id = result.memory_ids[0]
        history = episodic.history(session_id="chat")
        assert len(history) == 1
        assert history[0]["episode_id"] == f"episode:auto:{turn_id}"
        assert history[0]["source_type"] == "derived_relation"
        assert history[0]["ultimate_source_memory_id"] == turn_id
        assert history[0]["timestamp"] == "2026-09-03T22:31:00Z"
        episodic.flush()
    finally:
        conversation.close()
        episodic.close()

    reopened_conversation = NativeConversationService(
        library_path=library,
        data_dir=store,
        organization_id="auto-episode-org",
        runtime_manager=manager,
    )
    reopened_episodic = NativeEpisodicService(
        library_path=library,
        data_dir=store,
        organization_id="auto-episode-org",
        runtime_manager=manager,
    )
    try:
        history = reopened_episodic.history(session_id="chat")
        assert len(history) == 1
        assert history[0]["ultimate_source_memory_id"] == turn_id
        assert history[0]["timestamp"] == "2026-09-03T22:31:00Z"
        resolved = reopened_conversation.resolve(query="sensor active", session_id="chat")
        assert resolved.status == "HIT"
    finally:
        reopened_conversation.close()
        reopened_episodic.close()


def test_runtime_manager_rejects_two_libraries_for_same_open_store(tmp_path: Path):
    library = _native_library()
    copied_library = tmp_path / library.name
    shutil.copy2(library, copied_library)
    store = tmp_path / "conflict-store"
    manager = NativeRuntimeManager()
    first = manager.acquire(
        library_path=library,
        data_dir=store,
        organization_id="conflict-org",
    )
    try:
        with pytest.raises(RuntimeError, match="different Memoria.ia library"):
            manager.acquire(
                library_path=copied_library,
                data_dir=store,
                organization_id="conflict-org",
            )
    finally:
        first.release()
    assert manager.active_runtime_count() == 0
