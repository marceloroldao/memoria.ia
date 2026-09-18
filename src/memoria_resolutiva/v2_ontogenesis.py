from __future__ import annotations

from collections import Counter, defaultdict
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
    """Preserve observations and promote reusable structure without fixed semantics."""

    TOKEN_PREDICATE = "contains_token"
    NEXT_PREDICATE = "next_token"
    COMPOSITION_MEMBER_PREDICATE = "composition_member"
    OCCURRENCE_COMPOSITION_PREDICATE = "uses_composition"
    COMPOSITION_BRANCH_PREDICATE = "composition_branch"

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
        self._continuations: dict[str | None, dict[tuple[str, ...], Counter[str]]] = {}

    @staticmethod
    def _stable_id(namespace: str | None, order: int, text: str) -> str:
        return hashlib.blake2b(f"{namespace or ''}\0{order}\0{text}".encode(), digest_size=12).hexdigest()

    @staticmethod
    def _composition_id(tokens: tuple[str, ...]) -> str:
        return "composition:" + hashlib.blake2b("\0".join(tokens).encode(), digest_size=12).hexdigest()

    def _order(self, namespace: str | None) -> int:
        if namespace not in self._next_order:
            existing = self.episodes.episodes(namespace=namespace)
            self._next_order[namespace] = 0 if not existing else max(e.order for e in existing) + 1
        order = self._next_order[namespace]
        self._next_order[namespace] += 1
        return order

    def _learn_structure(self, words: tuple[str, ...], namespace: str | None) -> tuple[tuple[str, ...], ...]:
        support = self._sequence_support.setdefault(namespace, Counter())
        continuations = self._continuations.setdefault(namespace, defaultdict(Counter))
        upper = min(len(words), self.max_composition_tokens)

        for size in range(2, upper + 1):
            for start in range(len(words) - size + 1):
                support[words[start:start + size]] += 1
        for end in range(2, upper + 1):
            prefix = words[:end]
            if end < len(words):
                continuations[prefix][words[end]] += 1

        candidates: set[tuple[str, ...]] = set()
        # A branching prefix is a stable structural node even if a longer full
        # trajectory later recurs. This is the trunk/branch distinction.
        for prefix, branches in continuations.items():
            if support[prefix] >= self.min_composition_support and len(branches) >= 2:
                candidates.add(prefix)

        # Repeated full observations are valid specific compositions too.
        if 2 <= len(words) <= self.max_composition_tokens and support[words] >= self.min_composition_support:
            candidates.add(words)

        return tuple(sorted(candidates, key=lambda seq: (-len(seq), seq)))

    def observe(self, text: str, *, namespace: str | None = None, provenance: str = "user",
                timestamp: str | None = None) -> OntogenesisObservation:
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
                    evidence_id=f"{episode_id}:next:{index-1}:{index}", source_text=raw,
                    provenance=provenance, origin="user", namespace=namespace,
                ))

        promoted = self._learn_structure(words, namespace)
        ids: list[str] = []
        for seq in promoted:
            cid = self._composition_id(seq)
            ids.append(cid)
            edges.append(self.core.observe_relation(
                occurrence, self.OCCURRENCE_COMPOSITION_PREDICATE, cid,
                evidence_id=f"{episode_id}:composition:{cid}", source_text=raw,
                provenance=provenance, origin="user", namespace=namespace,
            ))
            for index, token in enumerate(seq):
                edges.append(self.core.observe_relation(
                    cid, self.COMPOSITION_MEMBER_PREDICATE, f"{index}:{token}",
                    evidence_id=f"{episode_id}:member:{cid}:{index}", source_text=raw,
                    provenance=provenance, origin="user", namespace=namespace,
                ))
            branches = self._continuations.get(namespace, {}).get(seq, {})
            for branch in sorted(branches):
                edges.append(self.core.observe_relation(
                    cid, self.COMPOSITION_BRANCH_PREDICATE, branch,
                    evidence_id=f"{episode_id}:branch:{cid}:{branch}", source_text=raw,
                    provenance=provenance, origin="user", namespace=namespace,
                ))
        return OntogenesisObservation(episode_id, episode_id, order, words, tuple(edges), tuple(ids))
