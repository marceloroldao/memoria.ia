from __future__ import annotations

from dataclasses import dataclass
import hashlib

from .evidence_core import EvidenceCore, EvidenceEdge
from .episodic_recall import Episode, EpisodicRecallService
from .textual import tokenize


@dataclass(frozen=True, slots=True)
class OntogenesisObservation:
    evidence_id: str
    episode_id: str
    order: int
    tokens: tuple[str, ...]
    structural_edges: tuple[EvidenceEdge, ...]


class V2OntogenesisIngestor:
    """Additive V2 ingestion boundary: preserve first, interpret second.

    This layer intentionally does not contain phrase-specific regexes or a fixed
    truth parser. Raw user observations become immutable episodes and lexical
    structure. Semantic/concept relations can be added later by learned,
    deterministic or external interpreters while retaining provenance.
    """

    TOKEN_PREDICATE = "contains_token"
    NEXT_PREDICATE = "next_token"

    def __init__(self, core: EvidenceCore) -> None:
        self.core = core
        self.episodes = EpisodicRecallService(core)
        self._next_order: dict[str | None, int] = {}

    @staticmethod
    def _stable_id(namespace: str | None, order: int, text: str) -> str:
        payload = f"{namespace or ''}\0{order}\0{text}".encode("utf-8")
        return hashlib.blake2b(payload, digest_size=12).hexdigest()

    def _order(self, namespace: str | None) -> int:
        if namespace not in self._next_order:
            existing = self.episodes.episodes(namespace=namespace)
            self._next_order[namespace] = 0 if not existing else max(e.order for e in existing) + 1
        order = self._next_order[namespace]
        self._next_order[namespace] += 1
        return order

    def observe(
        self,
        text: str,
        *,
        namespace: str | None = None,
        provenance: str = "user",
        timestamp: str | None = None,
    ) -> OntogenesisObservation:
        raw = text.strip()
        if not raw:
            raise ValueError("text must be non-empty")
        order = self._order(namespace)
        identity = self._stable_id(namespace, order, raw)
        episode_id = f"v2-episode:{identity}"
        self.episodes.record(
            Episode(
                episode_id=episode_id,
                role="user",
                text=raw,
                namespace=namespace,
                order=order,
                timestamp=timestamp,
                event_type="observation",
                topics=(),
            ),
            source_type="user_assertion",
        )

        words = tuple(tokenize(raw))
        edges: list[EvidenceEdge] = []
        occurrence = f"observation:{identity}"
        for index, token in enumerate(words):
            edges.append(self.core.observe_relation(
                occurrence,
                self.TOKEN_PREDICATE,
                token,
                evidence_id=f"{episode_id}:token:{index}",
                source_text=raw,
                provenance=provenance,
                origin="user",
                namespace=namespace,
            ))
            if index:
                edges.append(self.core.observe_relation(
                    words[index - 1],
                    self.NEXT_PREDICATE,
                    token,
                    evidence_id=f"{episode_id}:next:{index - 1}:{index}",
                    source_text=raw,
                    provenance=provenance,
                    origin="user",
                    namespace=namespace,
                ))
        return OntogenesisObservation(episode_id, episode_id, order, words, tuple(edges))
