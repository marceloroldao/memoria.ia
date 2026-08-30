from __future__ import annotations

import os
from pathlib import Path
import shutil

import pytest

from memoria_resolutiva.native_conversation import NativeConversationService
from memoria_resolutiva.native_episodic import NativeEpisodicService
from memoria_resolutiva.native_external_knowledge import NativeExternalKnowledgeService
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


def test_external_knowledge_shares_native_runtime_deduplicates_and_survives_restart(tmp_path: Path):
    library = _native_library()
    store = tmp_path / "external-native-store"
    manager = NativeRuntimeManager()
    external = NativeExternalKnowledgeService(
        library_path=library,
        data_dir=store,
        organization_id="external-runtime-org",
        runtime_manager=manager,
    )
    conversation = NativeConversationService(
        library_path=library,
        data_dir=store,
        organization_id="external-runtime-org",
        runtime_manager=manager,
    )
    assert manager.active_runtime_count() == 1
    assert external._lease.runtime is conversation._runtime_lease.runtime

    try:
        first = external.learn(
            content="orbital adapter code is 7319",
            source_url="https://example.org/a",
            source_domain="example.org",
            source_title="Adapter source A",
            acquired_time="2026-08-30T05:00:00Z",
            validation_confidence=0.91,
        )
        assert first.deduplicated is False
        assert first.source_attached is True
        assert first.source_count == 1
        assert first.source_type == "external_import"
        memory_id = first.memory_ids[0]
        assert first.provenance["knowledge_class"] == "external_public"
        assert first.provenance["sources"][0]["source_url"] == "https://example.org/a"

        repeated = external.learn(
            content="orbital adapter code is 7319",
            source_url="https://example.org/a",
            source_domain="example.org",
            source_title="Adapter source A",
            acquired_time="2026-08-30T05:01:00Z",
        )
        assert repeated.memory_ids == (memory_id,)
        assert repeated.deduplicated is True
        assert repeated.source_attached is False
        assert repeated.source_count == 1

        independent = external.learn(
            content="orbital adapter code is 7319",
            source_url="https://docs.example.net/b",
            source_domain="docs.example.net",
            source_title="Adapter source B",
            acquired_time="2026-08-30T05:02:00Z",
            import_kind="imported",
        )
        assert independent.memory_ids == (memory_id,)
        assert independent.deduplicated is True
        assert independent.source_attached is True
        assert independent.source_count == 2

        resolved = conversation.resolve(query="orbital adapter code")
        assert resolved.status == "HIT"
        assert "7319" in resolved.selected_context
        assert resolved.provenance
        assert resolved.provenance[0]["source_type"] == "external_import"
        external.flush()
    finally:
        external.close()
        conversation.close()

    assert manager.active_runtime_count() == 0

    reopened_external = NativeExternalKnowledgeService(
        library_path=library,
        data_dir=store,
        organization_id="external-runtime-org",
        runtime_manager=manager,
    )
    reopened_conversation = NativeConversationService(
        library_path=library,
        data_dir=store,
        organization_id="external-runtime-org",
        runtime_manager=manager,
    )
    try:
        provenance = reopened_external.inspect(memory_id=memory_id)
        assert provenance["knowledge_class"] == "external_public"
        assert provenance["source_count"] == 2
        assert {row["source_domain"] for row in provenance["sources"]} == {"example.org", "docs.example.net"}
        assert provenance["federation_eligible"] is False

        offline_resolve = reopened_conversation.resolve(query="orbital adapter code")
        assert offline_resolve.status == "HIT"
        assert "7319" in offline_resolve.selected_context
        assert offline_resolve.provenance[0]["source_type"] == "external_import"
    finally:
        reopened_external.close()
        reopened_conversation.close()

    assert manager.active_runtime_count() == 0


def test_external_knowledge_adapter_rejects_malformed_public_provenance(tmp_path: Path):
    library = _native_library()
    manager = NativeRuntimeManager()
    external = NativeExternalKnowledgeService(
        library_path=library,
        data_dir=tmp_path / "external-invalid-store",
        organization_id="external-invalid-org",
        runtime_manager=manager,
    )
    try:
        with pytest.raises(ValueError):
            external.learn(
                content="bad fact is 1",
                source_url="not-a-url",
                source_domain="example.org",
                source_title="Bad source",
                acquired_time="2026-08-30T05:03:00Z",
            )
    finally:
        external.close()
    assert manager.active_runtime_count() == 0


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
