from __future__ import annotations

from dataclasses import dataclass
import re
import unicodedata

from .evidence_core import EvidenceCore, EvidenceEdge
from .memory_provenance import MemoryProvenanceIndex

_WORD_RE = re.compile(r"[\wÀ-ÿ.-]+", re.UNICODE)
_STOPWORDS = {
    "a", "ao", "aos", "as", "da", "das", "de", "do", "dos", "e", "em", "eu", "foi", "me",
    "meu", "meus", "minha", "minhas", "o", "os", "para", "por", "que", "qual", "quais", "um",
    "uma", "uns", "umas", "voce", "você", "ultimo", "último", "ultima", "última", "mais", "recente",
}


def _key(value: str) -> str:
    value = unicodedata.normalize("NFKD", value)
    value = "".join(ch for ch in value if not unicodedata.combining(ch))
    return " ".join(value.casefold().strip().split())


def _tokens(value: str) -> set[str]:
    return {k for token in _WORD_RE.findall(value) if (k := _key(token)) and k not in _STOPWORDS}


@dataclass(frozen=True, slots=True)
class Episode:
    episode_id: str
    role: str
    text: str
    namespace: str | None
    order: int
    timestamp: str | None
    event_type: str | None = None
    topics: tuple[str, ...] = ()
    parent_memory_ids: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class EpisodicRecallResult:
    status: str
    confidence: float
    episode_ids: tuple[str, ...]
    selected_context: str
    order: int | None
    timestamp: str | None
    event_type: str | None
    topics: tuple[str, ...]
    source_type: str | None = None
    source_authority: float | None = None
    ultimate_source_memory_id: str | None = None


class EpisodicRecallService:
    """Generic temporal recall over EvidenceCore with provenance transparency.

    Historical recall keeps assistant-generated episodes available as history.
    Callers that need factual evidence can request ``factual_only=True``; in that
    mode an episode must resolve to an active factual root instead of becoming
    factual merely because it was generated or replayed.
    """

    PREDICATE = "conversation_episode"

    def __init__(self, core: EvidenceCore) -> None:
        self.core = core
        self.provenance = MemoryProvenanceIndex(core)

    def record(self, episode: Episode) -> EvidenceEdge:
        if episode.role not in {"user", "assistant"}:
            raise ValueError("role must be 'user' or 'assistant'")
        if not episode.episode_id.strip() or not episode.text.strip():
            raise ValueError("episode_id and text must be non-empty")
        if episode.order < 0:
            raise ValueError("order must be >= 0")
        event_type = _key(episode.event_type) if episode.event_type else ""
        topics = tuple(sorted({_key(t) for t in episode.topics if _key(t)}))
        metadata = "|".join((episode.role, str(episode.order), episode.timestamp or "", event_type, ",".join(topics)))
        row = self.core.observe_relation(
            f"episode:{episode.episode_id}", self.PREDICATE, metadata,
            evidence_id=episode.episode_id, source_text=episode.text,
            provenance="conversation-episode", origin=f"conversation-{episode.role}",
            confidence=1.0, namespace=episode.namespace,
        )
        source_type = "user_assertion" if episode.role == "user" else "assistant_generated"
        self.provenance.register(
            episode.episode_id, source_type=source_type,
            parent_memory_ids=episode.parent_memory_ids,
            created_order=episode.order, created_time=episode.timestamp,
            namespace=episode.namespace,
        )
        return row

    @staticmethod
    def _decode(edge: EvidenceEdge) -> Episode:
        role, order, timestamp, event_type, topics = (edge.object.split("|", 4) + ["", "", "", "", ""])[:5]
        return Episode(
            episode_id=edge.evidence_id, role=role, text=edge.source_text,
            namespace=edge.namespace, order=int(order), timestamp=timestamp or None,
            event_type=event_type or None, topics=tuple(t for t in topics.split(",") if t),
        )

    def episodes(self, *, namespace: str | None = None) -> tuple[Episode, ...]:
        rows = [e for e in self.core.active_edges(namespace=namespace) if e.predicate == self.PREDICATE]
        episodes: list[Episode] = []
        for edge in rows:
            if self.provenance.inspect(edge.evidence_id, namespace=namespace).superseded_by is None:
                episodes.append(self._decode(edge))
        return tuple(sorted(episodes, key=lambda e: (e.order, e.episode_id)))

    def recall_latest(self, *, query: str, namespace: str | None = None, role: str | None = None,
                      event_type: str | None = None, topics: tuple[str, ...] | list[str] = (),
                      factual_only: bool = False) -> EpisodicRecallResult:
        query = query.strip()
        if not query:
            raise ValueError("query must be non-empty")
        if role is not None and role not in {"user", "assistant"}:
            raise ValueError("role must be 'user' or 'assistant'")
        requested_type = _key(event_type) if event_type else None
        requested_topics = {_key(t) for t in topics if _key(t)}
        qtokens = _tokens(query)
        ranked: list[tuple[float, int, Episode]] = []
        for episode in self.episodes(namespace=namespace):
            if role is not None and episode.role != role:
                continue
            if factual_only:
                source = self.provenance.active_ultimate_source(episode.episode_id, namespace=namespace)
                if source is None or not self.provenance.is_factual_root_type(source.source_type):
                    continue
            if requested_type is not None and _key(episode.event_type or "") != requested_type:
                continue
            episode_topics = {_key(t) for t in episode.topics}
            if requested_topics and not requested_topics.issubset(episode_topics | _tokens(episode.text)):
                continue
            overlap = len(qtokens & (_tokens(episode.text) | episode_topics | ({_key(episode.event_type)} if episode.event_type else set())))
            explicit = (2 if requested_type else 0) + len(requested_topics)
            if overlap == 0 and explicit == 0:
                continue
            ranked.append((explicit + overlap / max(1, len(qtokens)), episode.order, episode))
        if not ranked:
            return EpisodicRecallResult("UNRESOLVED", 0.0, (), "", None, None, None, ())
        best_score = max(row[0] for row in ranked)
        candidates = [row for row in ranked if abs(row[0] - best_score) < 1e-12]
        latest_order = max(row[1] for row in candidates)
        latest = [row[2] for row in candidates if row[1] == latest_order]
        if len(latest) != 1:
            return EpisodicRecallResult("UNRESOLVED", 0.0, (), "", None, None, None, ())
        episode = latest[0]
        source = self.provenance.ultimate_source(episode.episode_id, namespace=namespace)
        confidence = min(1.0, 0.55 + 0.1 * min(best_score, 4.0))
        return EpisodicRecallResult(
            "HIT", confidence, (episode.episode_id,), episode.text, episode.order,
            episode.timestamp, episode.event_type, episode.topics,
            source.source_type, source.authority, source.memory_id,
        )
