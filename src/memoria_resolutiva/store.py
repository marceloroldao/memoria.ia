from __future__ import annotations
from collections import Counter, defaultdict
from dataclasses import dataclass
from math import log

from .layers import layer_bits
from .node import Node, digest_payload
from .trajectory import Occurrence


@dataclass(slots=True)
class RetrievalHit:
    memory_id: str
    score: float


class ResolutiveMemory:
    def __init__(self, max_layer: int = 3):
        self.max_layer = max_layer
        self.nodes: dict[str, Node] = {}
        self.occurrences: dict[str, list[Occurrence]] = defaultdict(list)
        self.memory_bytes: dict[str, bytes] = {}
        self.node_document_frequency: Counter[str] = Counter()
        self._nodes_by_memory: dict[str, set[str]] = defaultdict(set)

    def _chunks(self, data: bytes, layer: int):
        width = layer_bits(layer) // 8
        for offset in range(0, len(data), width):
            yield offset // width, data[offset:offset + width]

    def add(self, memory_id: str, data: bytes) -> None:
        if memory_id in self.memory_bytes:
            raise ValueError(f"memory_id already exists: {memory_id}")
        self.memory_bytes[memory_id] = bytes(data)
        seen = set()
        for layer in range(self.max_layer + 1):
            for local_time, payload in self._chunks(data, layer):
                if not payload:
                    continue
                node_id = digest_payload(payload, layer)
                self.nodes.setdefault(node_id, Node(node_id, layer, payload))
                occ = Occurrence(memory_id, layer, local_time, node_id)
                self.occurrences[node_id].append(occ)
                self._nodes_by_memory[memory_id].add(node_id)
                seen.add(node_id)
        for node_id in seen:
            self.node_document_frequency[node_id] += 1

    def reconstruct(self, memory_id: str) -> bytes:
        return self.memory_bytes[memory_id]

    def stats(self) -> dict:
        per_layer = Counter(node.layer for node in self.nodes.values())
        return {
            "memories": len(self.memory_bytes),
            "unique_nodes": len(self.nodes),
            "nodes_per_layer": dict(sorted(per_layer.items())),
            "occurrences": sum(len(v) for v in self.occurrences.values()),
        }

    def _query_nodes(self, query: bytes) -> set[str]:
        result = set()
        for layer in range(self.max_layer + 1):
            for _, payload in self._chunks(query, layer):
                if payload:
                    result.add(digest_payload(payload, layer))
        return result

    def search(self, query: bytes, top_k: int = 5, attractors: int = 8) -> list[RetrievalHit]:
        query_nodes = [n for n in self._query_nodes(query) if n in self.nodes]
        if not query_nodes:
            return []
        total_docs = max(1, len(self.memory_bytes))
        ranked_nodes = sorted(query_nodes, key=lambda n: self.node_document_frequency[n])[:attractors]
        scores: Counter[str] = Counter()
        for node_id in ranked_nodes:
            df = self.node_document_frequency[node_id]
            weight = log((total_docs + 1) / (df + 1)) + 1.0
            for occ in self.occurrences[node_id]:
                scores[occ.memory_id] += weight
        return [RetrievalHit(mid, score) for mid, score in scores.most_common(top_k)]
