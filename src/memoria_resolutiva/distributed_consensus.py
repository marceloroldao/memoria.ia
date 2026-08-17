from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable


def jaccard(a: set[str], b: set[str]) -> float:
    if not a and not b:
        return 1.0
    union = a | b
    return len(a & b) / len(union) if union else 0.0


@dataclass(frozen=True, slots=True)
class KnowledgeDescriptor:
    knowledge_id: str
    semantic_tokens: frozenset[str]
    modality_tokens: frozenset[str]
    payload_fingerprint: str
    polarity: int = 1
    confidence: float = 1.0


@dataclass(frozen=True, slots=True)
class ConsensusDecision:
    relation: str  # same | related | conflict | distinct
    score: float
    semantic_score: float
    modality_score: float
    reason: str


def compare_knowledge(a: KnowledgeDescriptor, b: KnowledgeDescriptor) -> ConsensusDecision:
    semantic = jaccard(set(a.semantic_tokens), set(b.semantic_tokens))
    modality = jaccard(set(a.modality_tokens), set(b.modality_tokens))
    fp_equal = a.payload_fingerprint == b.payload_fingerprint
    polarity_conflict = a.polarity != b.polarity
    confidence = min(a.confidence, b.confidence)

    if fp_equal and not polarity_conflict:
        return ConsensusDecision("same", 1.0, semantic, modality, "identical payload fingerprint")

    if semantic >= 0.70 and polarity_conflict and confidence >= 0.50:
        score = semantic * confidence
        return ConsensusDecision("conflict", score, semantic, modality, "high semantic overlap with opposing polarity")

    score = (0.75 * semantic + 0.25 * modality) * confidence
    if semantic >= 0.55 and score >= 0.45:
        return ConsensusDecision("related", score, semantic, modality, "shared semantic neighborhood without identity proof")

    return ConsensusDecision("distinct", score, semantic, modality, "insufficient evidence for merge or conflict")


def pairwise_consensus(items: Iterable[KnowledgeDescriptor]):
    xs = list(items)
    out = []
    for i in range(len(xs)):
        for j in range(i + 1, len(xs)):
            out.append((xs[i].knowledge_id, xs[j].knowledge_id, compare_knowledge(xs[i], xs[j])))
    return out
