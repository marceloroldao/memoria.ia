from __future__ import annotations

from collections import Counter
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
    compositions: tuple[str, ...] = ()


class V2OntogenesisIngestor:
    """Additive V2 ingestion boundary: preserve first, interpret second.

    Raw observations remain immutable. Repeated contiguous structure can promote
    itself into content-addressed compositions without phrase-specific rules.
    Promotion never replaces source episodes or lexical evidence.
    """

    TOKEN_PREDICATE = "contains_token"
    NEXT_PREDICATE = "next_token"
    COMPOSITION_MEMBER_PREDICATE = "composition_member"
    OCCURRENCE_COMPOSITION_PREDICATE = "uses_composition"

    def __init__(self, core: EvidenceCore, *, min_composition_support: int = 2, max_composition_tokens: int = 8) -> None:
        if min_composition_support < 2:
            raise ValueError("min_composition_support must be >= 2")
        if max_composition_tokens < 2:
            raise ValueError("max_composition_tokens must be >= 2")
        self.core = core
        self.episodes = EpisodicRecallService(core)
        self.min_composition_support = min_composition_support
        self.max_composition_tokens = max_composition_tokens
        self._next_order: dict[str | None, int] = {}
        self._sequence_support: dict[str | None, Counter[tuple[str, ...]]] = {}

    @staticmethod
    def _stable_id(namespace: str | None, order: int, text: str) -> str:
        payload = f"{namespace or ''}\0{order}\0{text}".encode("utf-8")
        return hashlib.blake2b(payload, digest_size=12).hexdigest()

    @staticmethod
    def _composition_id(tokens: tuple[str, ...]) -> str:
        payload = "\0".join(tokens).encode("utf-8")
        return "composition:" + hashlib.blake2b(payload, digest_size=12).hexdigest()

    def _order(self, namespace: str | None) -> int:
        if namespace not in self._next_order:
            existing = self.episodes.episodes(namespace=namespace)
            self._next_order[namespace] = 0 if not existing else max(e.order for e in existing) + 1
        order = self._next_order[namespace]
        self._next_order[namespace] += 1
        return order

    def _support(self, namespace: str | None) -> Counter[tuple[str, ...]]:
        return self._sequence_support.setdefault(namespace, Counter())

    def _promoted_sequences(self, words: tuple[str, ...], namespace: str | None) -> tuple[tuple[str, ...], ...]:
        support = self._support(namespace)
        promoted: set[tuple[str, ...]] = set()
        upper = min(len(words), self.max_composition_tokens)
        for size in range(2, upper + 1):
            for start in range(0, len(words) - size + 1):
                seq = words[start:start + size]
                support[seq] += 1
                if support[seq] >= self.min_composition_support:
                    promoted.add(seq)
        # Keep every supported address. A longer recurrence must not erase a
        # previously promoted reusable sub-composition: both are valid nodes in
        # the hierarchy and may branch differently in future observations.
        return tuple(sorted(promoted, key=lambda seq: (-len(seq), seq)))

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
            Episode(episode_id, "user", raw, namespace, order, timestamp, "observation", ()),
            source_type="user_assertion",
        )

        words = tuple(tokenize(raw))
        edges: list[EvidenceEdge] = []
        occurrence = f"observation:{identity}"
        for index, token in enumerate(words):
            edges.append(self.core.observe_relation(
                occurrence, self.TOKEN_PREDICATE, token,
                evidence_id=f"{episode_id}:token:{index}", source_text=raw,
                provenance=provenance, origin="user", namespace=namespace,
            ))
            if index:
                edges.append(self.core.observe_relation(
                    words[index - 1], self.NEXT_PREDICATE, token,
                    evidence_id=f"{episode_id}:next:{index - 1}:{index}", source_text=raw,
                    provenance=provenance, origin="user", namespace=namespace,
                ))

        promoted = self._promoted_sequences(words, namespace)
        composition_ids: list[str] = []
        for seq in promoted:
            composition_id = self._composition_id(seq)
            composition_ids.append(composition_id)
            edges.append(self.core.observe_relation(
                occurrence, self.OCCURRENCE_COMPOSITION_PREDICATE, composition_id,
                evidence_id=f"{episode_id}:composition:{composition_id}", source_text=raw,
                provenance=provenance, origin="user", namespace=namespace,
            ))
            for index, token in enumerate(seq):
                edges.append(self.core.observe_relation(
                    composition_id, self.COMPOSITION_MEMBER_PREDICATE, f"{index}:{token}",
                    evidence_id=f"{episode_id}:member:{composition_id}:{index}", source_text=raw,
                    provenance=provenance, origin="user", namespace=namespace,
                ))
        return OntogenesisObservation(episode_id, episode_id, order, words, tuple(edges), tuple(composition_ids))
