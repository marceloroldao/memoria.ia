from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable

from .native_runtime import NativeRuntimeManager, default_native_runtime_manager


MEMORIA_MOBILE_OK = 0
MEMORIA_MOBILE_INVALID_ARGUMENT = 1
MEMORIA_MOBILE_NOT_FOUND = 3


@dataclass(frozen=True, slots=True)
class ExternalKnowledgeLearnResult:
    memory_ids: tuple[str, ...]
    deduplicated: bool
    source_attached: bool
    source_count: int
    source_type: str
    provenance: dict[str, Any]


class NativeExternalKnowledgeService:
    """Thin native-only boundary for post-v1 external/public knowledge.

    Acquisition policy remains with the consumer (for example OFF.IA Curiosity).
    Once this method is called, source classification, semantic deduplication,
    lineage, conflict behavior and BDR persistence are owned by Memoria.ia.
    """

    def __init__(
        self,
        *,
        library_path: str | Path,
        data_dir: str | Path,
        organization_id: str,
        runtime_manager: NativeRuntimeManager | None = None,
    ) -> None:
        manager = runtime_manager or default_native_runtime_manager()
        self._lease = manager.acquire(
            library_path=library_path,
            data_dir=data_dir,
            organization_id=organization_id,
        )
        self._closed = False

    def learn(
        self,
        *,
        content: str,
        source_url: str,
        source_domain: str,
        source_title: str,
        acquired_time: str,
        source_excerpt: str = "",
        provider_id: str = "",
        import_kind: str = "synthesized",
        validation_confidence: float = 0.85,
        request_id: str = "",
        session_id: str = "",
        namespace: str = "",
        parent_memory_ids: Iterable[str] = (),
    ) -> ExternalKnowledgeLearnResult:
        if self._closed:
            raise RuntimeError("external knowledge service is closed")
        payload: dict[str, object] = {
            "content": content,
            "source_class": "external_public",
            "source_url": source_url,
            "source_domain": source_domain,
            "source_title": source_title,
            "acquired_time": acquired_time,
            "source_excerpt": source_excerpt,
            "provider_id": provider_id,
            "import_kind": import_kind,
            "validation_confidence": validation_confidence,
            "request_id": request_id,
            "session_id": session_id,
            "namespace": namespace,
            "parent_memory_ids": list(parent_memory_ids),
        }
        status, response = self._lease.call("memoria_mobile_learn_external_knowledge_json", payload)
        if status == MEMORIA_MOBILE_INVALID_ARGUMENT:
            raise ValueError(str(response.get("reason") or "native external knowledge request rejected"))
        if status != MEMORIA_MOBILE_OK or response.get("status") != "OK":
            raise RuntimeError(f"native external knowledge learning failed: status={status}")
        memory_ids = tuple(str(value) for value in response.get("stored_memory_ids", []))
        if not memory_ids:
            raise RuntimeError("native external knowledge learning returned no memory id")
        provenance = response.get("provenance")
        if not isinstance(provenance, dict):
            raise RuntimeError("native external knowledge learning returned invalid provenance")
        return ExternalKnowledgeLearnResult(
            memory_ids=memory_ids,
            deduplicated=bool(response.get("deduplicated", False)),
            source_attached=bool(response.get("source_attached", False)),
            source_count=int(response.get("source_count", provenance.get("source_count", 0))),
            source_type=str(response.get("source_type") or provenance.get("source_type") or "external_import"),
            provenance=provenance,
        )

    def inspect(self, *, memory_id: str, namespace: str = "") -> dict[str, Any]:
        if self._closed:
            raise RuntimeError("external knowledge service is closed")
        status, response = self._lease.call(
            "memoria_mobile_inspect_external_knowledge_json",
            {"memory_id": memory_id, "namespace": namespace},
        )
        if status == MEMORIA_MOBILE_NOT_FOUND:
            raise KeyError(memory_id)
        if status == MEMORIA_MOBILE_INVALID_ARGUMENT:
            raise ValueError(str(response.get("reason") or "native external knowledge inspect rejected"))
        if status != MEMORIA_MOBILE_OK or response.get("status") != "OK":
            raise RuntimeError(f"native external knowledge inspect failed: status={status}")
        provenance = response.get("provenance")
        if not isinstance(provenance, dict):
            raise RuntimeError("native external knowledge inspect returned invalid provenance")
        return provenance

    def flush(self) -> None:
        if not self._closed:
            self._lease.flush()

    def close(self) -> None:
        if self._closed:
            return
        self._closed = True
        self._lease.release()
