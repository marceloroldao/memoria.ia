from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import unicodedata

from .episodic_contract import EpisodeRecallRequest, EpisodeStoreRequest, EpisodicRecallResult
from .native_runtime import NativeRuntimeManager, default_native_runtime_manager


MEMORIA_MOBILE_OK = 0
MEMORIA_MOBILE_INVALID_ARGUMENT = 1
MEMORIA_MOBILE_UNRESOLVED = 2


@dataclass(frozen=True, slots=True)
class NativeEpisodeEdge:
    evidence_id: str
    namespace: str | None


@dataclass(frozen=True, slots=True)
class NativeEpisodeReceipt:
    """Truthful durable-write receipt for the native BDR path."""

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
    """Thin Python boundary over the authoritative native episodic runtime."""

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

    def _store_payload(self, request: EpisodeStoreRequest, *, source_type: str, source_authority: float,
                       ultimate_source_memory_id: str) -> tuple[NativeEpisodeEdge, NativeEpisodeReceipt]:
        topics = _normalized_topics(request.topics)
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
            "ultimate_source_memory_id": ultimate_source_memory_id,
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

    def store(self, request: EpisodeStoreRequest) -> tuple[NativeEpisodeEdge, NativeEpisodeReceipt]:
        if request.parent_memory_ids:
            raise ValueError(
                "native episodic parent lineage is not yet supported on the public store path; refusing to drop provenance"
            )
        source_type = "user_assertion" if request.role == "user" else "assistant_generated"
        source_authority = 0.95 if request.role == "user" else 0.25
        return self._store_payload(
            request,
            source_type=source_type,
            source_authority=source_authority,
            ultimate_source_memory_id=request.episode_id,
        )

    def store_derived(self, request: EpisodeStoreRequest) -> tuple[NativeEpisodeEdge, NativeEpisodeReceipt]:
        """Persist an internal automatic episode with one already-validated factual parent.

        The bridge is intentionally narrower than the public episode store. Native
        schema v1 stores one ultimate-source pointer, so multi-parent provenance is
        rejected rather than silently flattened.
        """
        if len(request.parent_memory_ids) != 1:
            raise ValueError("automatic derived episode requires exactly one factual parent memory")
        parent_id = request.parent_memory_ids[0]
        if not parent_id.strip():
            raise ValueError("automatic derived episode parent must be non-empty")
        return self._store_payload(
            request,
            source_type="derived_relation",
            source_authority=0.75,
            ultimate_source_memory_id=parent_id,
        )

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

    def history(
        self,
        *,
        session_id: str | None = None,
        event_type: str | None = None,
        limit: int = 1000,
    ) -> list[dict[str, object]]:
        wanted_event = _key(event_type) if event_type else None
        collected: list[dict[str, object]] = []
        offset = 0
        page_size = 64
        while len(collected) < limit:
            status, snapshot = self._call(
                "memoria_mobile_export_snapshot_json",
                {
                    "turn_offset": 0,
                    "turn_limit": 1,
                    "episode_offset": offset,
                    "episode_limit": page_size,
                },
            )
            if status != MEMORIA_MOBILE_OK or snapshot.get("status") != "OK":
                raise RuntimeError(f"native diagnostic snapshot failed: status={status}")
            episodes = snapshot.get("episodes") or []
            if not isinstance(episodes, list):
                raise RuntimeError("native diagnostic snapshot returned invalid episodes")
            for episode in episodes:
                if not isinstance(episode, dict):
                    continue
                if session_id is not None and str(episode.get("session_id") or "") != session_id:
                    continue
                if wanted_event is not None and _key(str(episode.get("event_type") or "")) != wanted_event:
                    continue
                collected.append(dict(episode))
                if len(collected) >= limit:
                    break
            page = snapshot.get("episode_page") or {}
            next_offset = page.get("next_offset") if isinstance(page, dict) else None
            if next_offset is None:
                break
            offset = int(next_offset)
        collected.sort(key=lambda item: (str(item.get("session_id") or ""), int(item.get("order") or 0)))
        return collected

    def flush(self) -> None:
        if not self._closed:
            self._runtime_lease.flush()

    def close(self) -> None:
        if self._closed:
            return
        self._closed = True
        self._runtime_lease.release()
