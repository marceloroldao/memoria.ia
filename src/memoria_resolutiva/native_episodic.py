from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import unicodedata

from .episodic_recall import EpisodicRecallResult
from .native_runtime import NativeRuntimeManager, default_native_runtime_manager
from .product_episodic import EpisodeRecallRequest, EpisodeStoreRequest


MEMORIA_MOBILE_OK = 0
MEMORIA_MOBILE_INVALID_ARGUMENT = 1
MEMORIA_MOBILE_UNRESOLVED = 2




@dataclass(frozen=True, slots=True)
class NativeEpisodeEdge:
    evidence_id: str
    namespace: str | None


@dataclass(frozen=True, slots=True)
class NativeEpisodeReceipt:
    """Truthful durable-write receipt for the native BDR path.

    The mobile ABI currently guarantees a durable atomic write but does not expose
    the EvidenceCore snapshot state_id/sha256 contract. Those fields therefore
    remain explicitly unavailable instead of being synthesized.
    """

    backend: str = "bdr-native"
    durable: bool = True

    def as_dict(self) -> dict[str, object]:
        return {
            "backend": self.backend,
            "state_id": None,
            "sha256": None,
            "durable": self.durable,
        }


def _key(value: str) -> str:
    value = unicodedata.normalize("NFKD", value)
    value = "".join(ch for ch in value if not unicodedata.combining(ch))
    return " ".join(value.casefold().strip().split())


def _normalized_topics(values: list[str]) -> tuple[str, ...]:
    return tuple(sorted({_key(value) for value in values if _key(value)}))


class NativeEpisodicService:
    """Thin Python boundary over the authoritative native episodic runtime.

    FastAPI/Pydantic stay in Python. Episodic persistence, candidate selection,
    ambiguity handling and recency resolution are delegated to libmemoria_mobile.
    No Python episodic algorithm is consulted as a fallback.
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
            raise RuntimeError("native episodic runtime is closed")
        return self._runtime_lease.call(function_name, payload)

    def store(self, request: EpisodeStoreRequest) -> tuple[NativeEpisodeEdge, NativeEpisodeReceipt]:
        if request.parent_memory_ids:
            raise ValueError(
                "native episodic parent lineage is not yet supported; refusing to drop provenance"
            )
        topics = _normalized_topics(request.topics)
        source_type = "user_assertion" if request.role == "user" else "assistant_generated"
        source_authority = 0.95 if request.role == "user" else 0.25
        payload: dict[str, object] = {
            "episode_id": request.episode_id,
            "session_id": request.session_id or "",
            "role": request.role,
            "text": request.text,
            "order": request.order,
            "timestamp": request.timestamp or "",
            "event_type": _key(request.event_type) if request.event_type else "",
            "topics_csv": ",".join(topics),
            "source_type": source_type,
            "source_authority": source_authority,
            "ultimate_source_memory_id": request.episode_id,
        }
        status, response = self._call("memoria_mobile_store_episode_json", payload)
        if status == MEMORIA_MOBILE_INVALID_ARGUMENT:
            raise ValueError(str(response.get("reason") or "native episodic store rejected request"))
        if status != MEMORIA_MOBILE_OK or response.get("status") != "OK":
            raise RuntimeError(f"native episodic store failed: status={status}")
        if response.get("durable") is not True:
            raise RuntimeError("native episodic store did not confirm durable persistence")
        returned_id = str(response.get("episode_id") or "")
        if returned_id != request.episode_id:
            raise RuntimeError("native episodic store returned an unexpected episode_id")
        return NativeEpisodeEdge(request.episode_id, request.session_id), NativeEpisodeReceipt()

    def resolve(self, request: EpisodeRecallRequest) -> EpisodicRecallResult:
        topics = _normalized_topics(request.topics)
        payload: dict[str, object] = {
            "query": request.query,
            "session_id": request.session_id or "",
            "role": request.role or "",
            "event_type": _key(request.event_type) if request.event_type else "",
            "topics_csv": ",".join(topics),
        }
        status, response = self._call("memoria_mobile_recall_episode_json", payload)
        if status == MEMORIA_MOBILE_UNRESOLVED or response.get("status") == "UNRESOLVED":
            return EpisodicRecallResult("UNRESOLVED", 0.0, (), "", None, None, None, ())
        if status == MEMORIA_MOBILE_INVALID_ARGUMENT:
            raise ValueError(str(response.get("reason") or "native episodic recall rejected request"))
        if status != MEMORIA_MOBILE_OK or response.get("status") != "HIT":
            raise RuntimeError(f"native episodic recall failed: status={status}")
        episode_ids = tuple(str(value) for value in response.get("episode_ids", []))
        topics_csv = str(response.get("topics_csv") or "")
        return EpisodicRecallResult(
            "HIT",
            float(response.get("confidence", 0.0)),
            episode_ids,
            str(response.get("selected_context") or ""),
            int(response["order"]) if response.get("order") is not None else None,
            str(response["timestamp"]) if response.get("timestamp") else None,
            str(response["event_type"]) if response.get("event_type") else None,
            tuple(value for value in topics_csv.split(",") if value),
            str(response["source_type"]) if response.get("source_type") else None,
            float(response["source_authority"]) if response.get("source_authority") is not None else None,
            str(response["ultimate_source_memory_id"]) if response.get("ultimate_source_memory_id") else None,
        )

    def flush(self) -> None:
        if not self._closed:
            self._runtime_lease.flush()

    def close(self) -> None:
        if self._closed:
            return
        self._closed = True
        self._runtime_lease.release()
