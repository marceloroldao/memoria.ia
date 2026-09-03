from __future__ import annotations

from datetime import datetime, timezone
from typing import Callable, Protocol

from .conversation_contract import ConversationIngestResult, ConversationResolveResult
from .episodic_contract import EpisodeStoreRequest


class ConversationBackend(Protocol):
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
    ) -> ConversationIngestResult: ...

    def resolve(self, *, query: str, session_id: str | None = None) -> ConversationResolveResult: ...


class DerivedEpisodeSink(Protocol):
    def store_derived(self, request: EpisodeStoreRequest): ...

    def history(
        self,
        *,
        session_id: str | None = None,
        event_type: str | None = None,
        limit: int = 1000,
    ) -> list[dict[str, object]]: ...


_QUESTION_PREFIXES = (
    "qual ", "quais ", "quem ", "onde ", "quando ", "como ", "quanto ", "quantos ", "quantas ",
    "por que ", "porque ", "what ", "which ", "who ", "where ", "when ", "how ", "why ",
    "can ", "could ", "would ", "should ", "do ", "does ", "did ",
)


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z")


def _looks_like_question(text: str) -> bool:
    normalized = " ".join(text.casefold().strip().split())
    return "?" in text or any(normalized.startswith(prefix) for prefix in _QUESTION_PREFIXES)


def _episode_topics(relations: tuple[dict, ...]) -> list[str]:
    values: list[str] = []
    seen: set[str] = set()
    for row in relations:
        for key in ("subject", "object"):
            value = str(row.get(key) or "").strip()
            normalized = value.casefold()
            if value and normalized not in seen:
                seen.add(normalized)
                values.append(value)
            if len(values) >= 12:
                return values
    return values


class AutoEpisodicConversationService:
    """Conversation facade that conservatively forms derived factual episodes.

    The raw turn is always persisted first. Automatic episode formation is only
    attempted for explicit user assertions/corrections that extracted at least one
    sufficiently confident relation and have a stable conversational order.
    Assistant output and question-like turns remain conversational/generative data.
    """

    def __init__(
        self,
        conversation: ConversationBackend,
        episodes: DerivedEpisodeSink,
        *,
        clock: Callable[[], str] = _utc_now,
        relation_confidence_threshold: float = 0.75,
    ) -> None:
        self.conversation = conversation
        self.episodes = episodes
        self.clock = clock
        self.relation_confidence_threshold = relation_confidence_threshold

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
        effective_timestamp = timestamp or self.clock()
        result = self.conversation.ingest(
            role=role,
            text=text,
            session_id=session_id,
            order=order,
            timestamp=effective_timestamp,
            parent_memory_ids=parent_memory_ids,
            corrects_memory_ids=corrects_memory_ids,
        )
        if not self._eligible(role=role, text=text, order=order, result=result):
            return result

        turn_id = result.memory_ids[0]
        episode_id = f"episode:auto:{turn_id}"
        if self._episode_exists(episode_id, session_id=session_id):
            return result

        selected_relations = tuple(
            row for row in result.relations
            if float(row.get("confidence", 0.0)) >= self.relation_confidence_threshold
        )
        self.episodes.store_derived(EpisodeStoreRequest(
            episode_id=episode_id,
            role="user",
            text=text.strip(),
            session_id=session_id,
            order=order,
            timestamp=effective_timestamp,
            event_type="correction" if corrects_memory_ids else "assertion",
            topics=_episode_topics(selected_relations),
            parent_memory_ids=[turn_id],
        ))
        return result

    def resolve(self, *, query: str, session_id: str | None = None) -> ConversationResolveResult:
        return self.conversation.resolve(query=query, session_id=session_id)

    def _eligible(self, *, role: str, text: str, order: int | None, result: ConversationIngestResult) -> bool:
        if role != "user" or order is None or _looks_like_question(text):
            return False
        return any(
            float(row.get("confidence", 0.0)) >= self.relation_confidence_threshold
            for row in result.relations
        )

    def _episode_exists(self, episode_id: str, *, session_id: str | None) -> bool:
        return any(
            str(row.get("episode_id") or "") == episode_id
            for row in self.episodes.history(session_id=session_id, limit=5000)
        )
