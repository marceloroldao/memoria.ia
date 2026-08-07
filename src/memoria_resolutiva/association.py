from __future__ import annotations
from collections import Counter

from .store import ResolutiveMemory


def trajectory_signature(memory: ResolutiveMemory, memory_id: str) -> Counter[str]:
    """Return a multiscale bag-of-nodes signature for one stored memory."""
    sig: Counter[str] = Counter()
    for node_id in memory._nodes_by_memory[memory_id]:
        sig[node_id] += 1
    return sig


def association_score(memory: ResolutiveMemory, a: str, b: str) -> float:
    """Jaccard-like structural overlap between two trajectories.

    This is deliberately non-semantic: v0.2 measures whether repeated structural
    context can create associations before embeddings or neural models are added.
    """
    sa = set(trajectory_signature(memory, a))
    sb = set(trajectory_signature(memory, b))
    if not sa and not sb:
        return 1.0
    union = sa | sb
    return len(sa & sb) / len(union) if union else 0.0


def nearest_associations(memory: ResolutiveMemory, memory_id: str, top_k: int = 5):
    scores = []
    for other in memory.memory_bytes:
        if other == memory_id:
            continue
        score = association_score(memory, memory_id, other)
        scores.append((other, score))
    scores.sort(key=lambda item: item[1], reverse=True)
    return scores[:top_k]
