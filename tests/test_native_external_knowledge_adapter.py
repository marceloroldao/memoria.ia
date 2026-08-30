from __future__ import annotations

import os
from pathlib import Path

import pytest

from memoria_resolutiva.native_conversation import NativeConversationService
from memoria_resolutiva.native_external_knowledge import NativeExternalKnowledgeService


def _native_library() -> Path:
    value = os.environ.get("MEMORIA_NATIVE_LIB")
    if not value:
        pytest.skip("MEMORIA_NATIVE_LIB is not set; external/native coverage runs in the host ABI workflow")
    path = Path(value)
    assert path.is_file()
    return path


def _service(root: Path, library: Path) -> NativeExternalKnowledgeService:
    return NativeExternalKnowledgeService(
        library_path=library,
        data_dir=root / "native-state",
        organization_id="external-adapter-org",
    )


def test_external_adapter_dedup_provenance_and_restart(tmp_path: Path):
    library = _native_library()
    service = _service(tmp_path, library)
    try:
        first = service.learn(
            content="orbital adapter code is 7319",
            source_url="https://example.org/a",
            source_domain="example.org",
            source_title="Adapter source A",
            acquired_time="2026-08-30T05:00:00Z",
            validation_confidence=0.91,
        )
        assert not first.deduplicated
        assert first.source_attached
        assert first.source_count == 1
        assert first.source_type == "external_import"
        memory_id = first.memory_ids[0]
        assert first.provenance["knowledge_class"] == "external_public"
        assert first.provenance["sources"][0]["source_url"] == "https://example.org/a"

        same = service.learn(
            content="orbital adapter code is 7319",
            source_url="https://example.org/a",
            source_domain="example.org",
            source_title="Adapter source A",
            acquired_time="2026-08-30T05:01:00Z",
        )
        assert same.memory_ids == (memory_id,)
        assert same.deduplicated
        assert not same.source_attached
        assert same.source_count == 1

        independent = service.learn(
            content="orbital adapter code is 7319",
            source_url="https://docs.example.net/b",
            source_domain="docs.example.net",
            source_title="Adapter source B",
            acquired_time="2026-08-30T05:02:00Z",
            import_kind="imported",
        )
        assert independent.memory_ids == (memory_id,)
        assert independent.deduplicated
        assert independent.source_attached
        assert independent.source_count == 2
        service.flush()
    finally:
        service.close()

    reopened = _service(tmp_path, library)
    try:
        provenance = reopened.inspect(memory_id=memory_id)
        assert provenance["knowledge_class"] == "external_public"
        assert provenance["source_count"] == 2
        assert {row["source_domain"] for row in provenance["sources"]} == {"example.org", "docs.example.net"}
        assert provenance["federation_eligible"] is False
    finally:
        reopened.close()

    conversation = NativeConversationService(
        library_path=library,
        data_dir=tmp_path / "native-state",
        organization_id="external-adapter-org",
    )
    try:
        result = conversation.resolve(query="orbital adapter code")
        assert result.status == "HIT"
        assert "7319" in result.selected_context
        assert result.provenance[0]["source_type"] == "external_import"
    finally:
        conversation.close()


def test_external_adapter_rejects_incomplete_provenance(tmp_path: Path):
    service = _service(tmp_path, _native_library())
    try:
        with pytest.raises(ValueError):
            service.learn(
                content="bad fact is 1",
                source_url="not-a-url",
                source_domain="example.org",
                source_title="Bad source",
                acquired_time="2026-08-30T05:03:00Z",
            )
    finally:
        service.close()
