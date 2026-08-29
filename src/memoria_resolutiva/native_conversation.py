from __future__ import annotations

import hashlib
from pathlib import Path

from .conversation_contract import ConversationIngestResult, ConversationResolveResult
from .native_runtime import NativeRuntimeManager, default_native_runtime_manager


MEMORIA_MOBILE_OK = 0
MEMORIA_MOBILE_INVALID_ARGUMENT = 1
MEMORIA_MOBILE_UNRESOLVED = 2
MAX_NATIVE_RELATIONS = 4



def _memory_id(*, role: str, text: str, session_id: str | None, order: int | None, index: int) -> str:
    raw = f"{session_id or ''}\0{order if order is not None else ''}\0{role}\0{text}\0{index}".encode("utf-8")
    return "conv:" + hashlib.sha256(raw).hexdigest()[:24]


def _relation_payload(row: object, *, namespace: str | None, order: int | None) -> dict[str, object]:
    if not isinstance(row, dict):
        raise RuntimeError("native Memoria.ia returned an invalid relation row")
    return {
        "subject": str(row.get("subject") or ""),
        "predicate": str(row.get("predicate") or ""),
        "object": str(row.get("object") or ""),
        "memory_id": str(row.get("memory_id") or ""),
        "confidence": float(row.get("confidence", 0.0)),
        "epoch": order,
        "namespace": namespace,
    }


class NativeConversationService:
    """Thin Python boundary over the authoritative native conversation runtime.

    HTTP, authentication and Pydantic stay in Python. Persistent memory,
    relation extraction, ranking, ambiguity, correction, temporal resolution and
    provenance authority are delegated to libmemoria_mobile. There is no Python
    semantic fallback.
    """

    def __init__(
        self,
        *,
        library_path: str | Path,
        data_dir: str | Path,
        organization_id: str,
        runtime_manager: NativeRuntimeManager | None = None,
    ) -> None:
        self.library_path = Path(library_path)
        self.data_dir = Path(data_dir)
        self.organization_id = organization_id
        manager = runtime_manager or default_native_runtime_manager()
        self._runtime_lease = manager.acquire(
            library_path=self.library_path,
            data_dir=self.data_dir,
            organization_id=organization_id,
        )
        self._closed = False

    def _call(self, function_name: str, payload: dict[str, object]) -> tuple[int, dict[str, object]]:
        if self._closed:
            raise RuntimeError("native conversation runtime is closed")
        return self._runtime_lease.call(function_name, payload)

    def ingest(
        self,
        *,
        role: str,
        text: str,
        session_id: str | None = None,
        order: int | None = None,
        timestamp: str | None = None,
        parent_memory_ids: tuple[str, ...] | list[str] = (),
        corrects_memory_ids: tuple[str, ...] | list[str] = (),
    ) -> ConversationIngestResult:
        if role not in {"user", "assistant"}:
            raise ValueError("role must be 'user' or 'assistant'")
        if corrects_memory_ids and role != "user":
            raise ValueError("only user turns may explicitly correct prior memories")
        text = text.strip()
        if not text:
            raise ValueError("text must be non-empty")
        turn_id = _memory_id(role=role, text=text, session_id=session_id, order=order, index=-1)
        relation_ids = [
            _memory_id(role=role, text=text, session_id=session_id, order=order, index=index)
            for index in range(MAX_NATIVE_RELATIONS)
        ]
        source_type = "user_correction" if corrects_memory_ids else ("user_assertion" if role == "user" else "assistant_generated")
        if source_type == "user_correction":
            source_authority = 1.0
        elif source_type == "user_assertion":
            source_authority = 0.95
        else:
            source_authority = 0.25
        payload: dict[str, object] = {
            "role": role,
            "text": text,
            "memory_id": turn_id,
            "namespace": session_id or "",
            "source_type": source_type,
            "source_authority": source_authority,
            "timestamp": timestamp or "",
            "parent_memory_ids": list(parent_memory_ids),
            "corrects_memory_ids": list(corrects_memory_ids),
            "relation_memory_ids": relation_ids,
        }
        if order is not None:
            payload["order"] = order
        status, response = self._call("memoria_mobile_learn_turn_json", payload)
        if status == MEMORIA_MOBILE_INVALID_ARGUMENT:
            raise ValueError(str(response.get("reason") or "native conversation ingest rejected request"))
        if status != MEMORIA_MOBILE_OK or response.get("status") != "OK":
            raise RuntimeError(f"native conversation ingest failed: status={status}")
        rows = response.get("relations", [])
        if not isinstance(rows, list):
            raise RuntimeError("native conversation ingest returned invalid relations")
        relations = tuple(_relation_payload(row, namespace=session_id, order=order) for row in rows)
        actual_relation_ids = tuple(str(row["memory_id"]) for row in relations if row.get("memory_id"))
        return ConversationIngestResult((turn_id, *actual_relation_ids), relations, not relations)

    def resolve(self, *, query: str, session_id: str | None = None) -> ConversationResolveResult:
        query = query.strip()
        if not query:
            raise ValueError("query must be non-empty")
        status, response = self._call(
            "memoria_mobile_resolve_context_json",
            {"query": query, "namespace": session_id or ""},
        )
        if status == MEMORIA_MOBILE_UNRESOLVED or response.get("status") == "UNRESOLVED":
            return ConversationResolveResult("UNRESOLVED", 0.0, (), "", (), ())
        if status == MEMORIA_MOBILE_INVALID_ARGUMENT:
            raise ValueError(str(response.get("reason") or "native conversation resolve rejected request"))
        if status != MEMORIA_MOBILE_OK or response.get("status") != "HIT":
            raise RuntimeError(f"native conversation resolve failed: status={status}")

        rows = response.get("relations", [])
        if not isinstance(rows, list):
            raise RuntimeError("native conversation resolve returned invalid relations")
        relations = tuple(_relation_payload(row, namespace=session_id, order=None) for row in rows)
        native_memory_ids = tuple(str(value) for value in response.get("memory_ids", []))

        provenance_rows: list[dict[str, object]] = []
        raw_provenance = response.get("provenance", [])
        if not isinstance(raw_provenance, list):
            raise RuntimeError("native conversation resolve returned invalid provenance")
        for row in raw_provenance:
            if not isinstance(row, dict):
                raise RuntimeError("native conversation resolve returned invalid provenance row")
            source_type = str(row.get("source_type") or "")
            provenance_rows.append({
                "memory_id": str(row.get("memory_id") or ""),
                "source_type": source_type,
                "source_authority": float(row.get("source_authority", 0.0)),
                "immediate_source_type": str(row.get("immediate_source_type") or source_type),
                "parent_memory_ids": list(row.get("parent_memory_ids") or []),
                "ultimate_source_memory_id": str(row.get("ultimate_source_memory_id") or row.get("memory_id") or ""),
                "created_order": row.get("created_order"),
                "created_time": row.get("created_time"),
                "superseded_by": row.get("superseded_by"),
            })

        if len(provenance_rows) == 1 and provenance_rows[0].get("created_order") is not None:
            relation_order = provenance_rows[0]["created_order"]
            relations = tuple({**row, "epoch": relation_order} for row in relations)

        # The native resolver ranks authoritative turns. The historic product API,
        # however, exposes the derived relation ID for a single-relation factual HIT.
        # This is identity normalization only: native extraction/ranking already chose
        # the source. We deliberately do not guess when multiple relations/sources exist.
        public_memory_ids = native_memory_ids
        if len(native_memory_ids) == 1 and len(relations) == 1:
            relation_id = str(relations[0].get("memory_id") or "")
            if relation_id and relation_id != native_memory_ids[0]:
                turn_id = native_memory_ids[0]
                public_memory_ids = (relation_id,)
                if len(provenance_rows) == 1:
                    provenance_rows[0]["memory_id"] = relation_id
                    provenance_rows[0]["immediate_source_type"] = "derived_relation"
                    provenance_rows[0]["parent_memory_ids"] = [turn_id]

        return ConversationResolveResult(
            "HIT",
            float(response.get("confidence", 0.0)),
            public_memory_ids,
            str(response.get("selected_context") or ""),
            relations,
            tuple(provenance_rows),
        )

    def flush(self) -> None:
        if not self._closed:
            self._runtime_lease.flush()

    def close(self) -> None:
        if self._closed:
            return
        self._closed = True
        self._runtime_lease.release()
