from __future__ import annotations

from pathlib import Path

from .native_runtime import NativeRuntimeManager, default_native_runtime_manager


MEMORIA_MOBILE_OK = 0
MEMORIA_MOBILE_INVALID_ARGUMENT = 1
MEMORIA_MOBILE_UNRESOLVED = 2


class NativeStructuralTextService:
    """Thin OFF.IA-facing boundary over the native non-semantic text field."""

    def __init__(
        self,
        *,
        library_path: str | Path,
        data_dir: str | Path,
        organization_id: str,
        runtime_manager: NativeRuntimeManager | None = None,
    ) -> None:
        manager = runtime_manager or default_native_runtime_manager()
        self._runtime_lease = manager.acquire(
            library_path=library_path,
            data_dir=data_dir,
            organization_id=organization_id,
        )
        if not self._runtime_lease.supports("memoria_mobile_observe_structural_text_json"):
            self._runtime_lease.release()
            raise RuntimeError("native runtime does not support structural text observation")
        if not self._runtime_lease.supports("memoria_mobile_resolve_structural_text_json"):
            self._runtime_lease.release()
            raise RuntimeError("native runtime does not support structural text resolution")
        self._closed = False

    def observe(
        self,
        text: str,
        *,
        hierarchy_id: str,
        source_id: str,
        sequence: int,
        source_kind: str = "user_assertion",
    ) -> dict[str, object]:
        if self._closed:
            raise RuntimeError("native structural text service is closed")
        text = text.strip()
        hierarchy_id = hierarchy_id.strip()
        source_id = source_id.strip()
        source_kind = source_kind.strip() or "unknown"
        if not text:
            raise ValueError("text must be non-empty")
        if not hierarchy_id:
            raise ValueError("hierarchy_id must be non-empty")
        if not source_id:
            raise ValueError("source_id must be non-empty")
        if sequence < 0:
            raise ValueError("sequence must be >= 0")

        status, response = self._runtime_lease.call(
            "memoria_mobile_observe_structural_text_json",
            {
                "hierarchy_id": hierarchy_id,
                "source_id": source_id,
                "source_kind": source_kind,
                "sequence": int(sequence),
                "text": text,
            },
        )
        if status == MEMORIA_MOBILE_INVALID_ARGUMENT:
            raise ValueError(str(response.get("reason") or "native structural observation rejected request"))
        if status != MEMORIA_MOBILE_OK or response.get("status") != "OK":
            raise RuntimeError(f"native structural observation failed: status={status}")
        return response

    def resolve(
        self,
        query: str,
        *,
        hierarchy_id: str,
        top_k: int = 3,
    ) -> dict[str, object]:
        if self._closed:
            raise RuntimeError("native structural text service is closed")
        query = query.strip()
        hierarchy_id = hierarchy_id.strip()
        if not query:
            raise ValueError("query must be non-empty")
        if not hierarchy_id:
            raise ValueError("hierarchy_id must be non-empty")
        if top_k < 1 or top_k > 16:
            raise ValueError("top_k must be between 1 and 16")

        status, response = self._runtime_lease.call(
            "memoria_mobile_resolve_structural_text_json",
            {
                "hierarchy_id": hierarchy_id,
                "query": query,
                "top_k": int(top_k),
            },
        )
        if status == MEMORIA_MOBILE_UNRESOLVED or response.get("status") == "UNRESOLVED":
            return {**response, "status": "UNRESOLVED"}
        if status == MEMORIA_MOBILE_INVALID_ARGUMENT:
            raise ValueError(str(response.get("reason") or "native structural resolution rejected request"))
        if status != MEMORIA_MOBILE_OK or response.get("status") != "HIT":
            raise RuntimeError(f"native structural resolution failed: status={status}")
        return response

    def flush(self) -> None:
        if not self._closed:
            self._runtime_lease.flush()

    def close(self) -> None:
        if self._closed:
            return
        self._closed = True
        self._runtime_lease.release()
