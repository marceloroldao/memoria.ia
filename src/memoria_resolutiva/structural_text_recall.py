from __future__ import annotations

from dataclasses import dataclass
import hashlib
from typing import Any

from .structural_association_runtime import StructuralAssociationRuntime
from .structural_observation import StructuralObservationStore
from .textual import tokenize


TEXT_ADAPTER_FORMAT = "memoria.ia-structural-text-v1"


def structural_text_symbol(token: str) -> int:
    """Map one normalized text token to an opaque, deterministic 64-bit symbol."""
    normalized = token.strip().casefold()
    if not normalized:
        raise ValueError("token must be non-empty")
    digest = hashlib.blake2b(
        ("memoria.ia:text-token:v1\0" + normalized).encode("utf-8"),
        digest_size=8,
    ).digest()
    return int.from_bytes(digest, "big", signed=False)


@dataclass(frozen=True, slots=True)
class StructuralTextObservation:
    observation_id: str
    duplicate: bool
    association_sync_observations: int
    symbol_count: int


@dataclass(frozen=True, slots=True)
class StructuralTextContext:
    source_text: str
    score: float
    exact_overlap: int
    association_mass: float
    observation_ids: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class StructuralTextResolution:
    status: str
    contexts: tuple[StructuralTextContext, ...]
    scanned_observations: int
    query_symbol_count: int
    semantic_projection: bool = False


class StructuralTextRecall:
    """Experimental text adapter over the non-semantic structural field.

    This adapter deliberately does not create predicates, grammar classes, facts
    or ontology labels. Text is tokenized only to obtain deterministic opaque
    symbols. The StructuralAssociationRuntime remains responsible for recurrence,
    causal distance and forgetting. Original text is preserved as provenance so a
    later consumer can materialize selected context without reversing symbol IDs.

    Resolution is read-only: a query is converted to symbols in memory but is not
    appended as an observation and therefore cannot reinforce its own answer.
    """

    def __init__(
        self,
        store: StructuralObservationStore,
        associations: StructuralAssociationRuntime,
    ) -> None:
        self.store = store
        self.associations = associations

    @staticmethod
    def _symbols(text: str) -> tuple[int, ...]:
        tokens = tuple(tokenize(text))
        if not tokens:
            raise ValueError("text must contain at least one token")
        return tuple(structural_text_symbol(token) for token in tokens)

    def observe(
        self,
        text: str,
        *,
        hierarchy_id: str,
        source_id: str,
        sequence: int,
        source_kind: str = "user",
    ) -> StructuralTextObservation:
        raw = text.strip()
        hierarchy_id = hierarchy_id.strip()
        source_id = source_id.strip()
        source_kind = source_kind.strip() or "unknown"
        if not raw:
            raise ValueError("text must be non-empty")
        if not hierarchy_id:
            raise ValueError("hierarchy_id must be non-empty")
        if not source_id:
            raise ValueError("source_id must be non-empty")
        if sequence < 0:
            raise ValueError("sequence must be >= 0")

        symbols = self._symbols(raw)
        encoded = raw.encode("utf-8")
        event = {
            "version": 1,
            "source_id": source_id,
            "sequence": int(sequence),
            "byte_offset": int(sequence),
            "byte_length": len(encoded),
            "trail": list(symbols),
            "relation_ids": [],
            "signature": hashlib.blake2b(encoded, digest_size=8).hexdigest(),
            "resolution": 1,
        }
        envelope, duplicate = self.store.append(
            event,
            provenance={
                "hierarchy_id": hierarchy_id,
                "adapter": TEXT_ADAPTER_FORMAT,
                "source_text": raw,
                "source_kind": source_kind,
            },
        )
        replayed = self.associations.sync()
        return StructuralTextObservation(
            observation_id=str(envelope["observation_id"]),
            duplicate=duplicate,
            association_sync_observations=replayed,
            symbol_count=len(symbols),
        )

    def _score(
        self,
        hierarchy_id: str,
        query_symbols: tuple[int, ...],
        candidate_symbols: tuple[int, ...],
    ) -> tuple[float, int, float]:
        qset = tuple(dict.fromkeys(query_symbols))
        cset = tuple(dict.fromkeys(candidate_symbols))
        exact = len(set(qset) & set(cset))
        association_mass = 0.0
        for query_symbol in qset:
            for candidate_symbol in cset:
                if query_symbol == candidate_symbol:
                    continue
                forward = self.associations.association(
                    hierarchy_id,
                    query_symbol,
                    candidate_symbol,
                )
                reverse = self.associations.association(
                    hierarchy_id,
                    candidate_symbol,
                    query_symbol,
                )
                association_mass += max(forward, reverse)

        normalized_exact = exact / float(max(1, len(qset)))
        normalized_mass = association_mass / float(max(1, len(qset) * len(cset)))
        return normalized_exact + normalized_mass, exact, normalized_mass

    def resolve(
        self,
        query: str,
        *,
        hierarchy_id: str,
        top_k: int = 3,
        max_scan: int = 2048,
    ) -> StructuralTextResolution:
        raw_query = query.strip()
        hierarchy_id = hierarchy_id.strip()
        if not raw_query:
            raise ValueError("query must be non-empty")
        if not hierarchy_id:
            raise ValueError("hierarchy_id must be non-empty")
        if top_k < 1:
            raise ValueError("top_k must be >= 1")
        if max_scan < 1:
            raise ValueError("max_scan must be >= 1")

        query_symbols = self._symbols(raw_query)
        self.associations.sync()

        start = max(0, self.store.count - max_scan)
        rows = self.store.ordered_from(start)
        grouped: dict[str, dict[str, Any]] = {}
        scanned = 0

        for envelope in rows:
            provenance = envelope.get("provenance")
            if not isinstance(provenance, dict):
                continue
            if provenance.get("adapter") != TEXT_ADAPTER_FORMAT:
                continue
            if str(provenance.get("hierarchy_id") or "") != hierarchy_id:
                continue
            source_text = str(provenance.get("source_text") or "").strip()
            if not source_text:
                continue
            event = envelope.get("event")
            if not isinstance(event, dict):
                continue
            candidate_symbols = tuple(int(item) for item in event.get("trail", ()))
            if not candidate_symbols:
                continue

            scanned += 1
            score, exact, mass = self._score(
                hierarchy_id,
                query_symbols,
                candidate_symbols,
            )
            if score <= 0.0:
                continue

            observation_id = str(envelope.get("observation_id") or "")
            current = grouped.get(source_text)
            if current is None:
                grouped[source_text] = {
                    "score": score,
                    "exact": exact,
                    "mass": mass,
                    "observation_ids": [observation_id],
                }
            else:
                current["observation_ids"].append(observation_id)
                if (score, exact, mass) > (
                    current["score"],
                    current["exact"],
                    current["mass"],
                ):
                    current["score"] = score
                    current["exact"] = exact
                    current["mass"] = mass

        contexts = [
            StructuralTextContext(
                source_text=text,
                score=float(values["score"]),
                exact_overlap=int(values["exact"]),
                association_mass=float(values["mass"]),
                observation_ids=tuple(values["observation_ids"]),
            )
            for text, values in grouped.items()
        ]
        contexts.sort(
            key=lambda item: (
                -item.score,
                -item.exact_overlap,
                -item.association_mass,
                item.source_text.casefold(),
            )
        )
        selected = tuple(contexts[:top_k])
        return StructuralTextResolution(
            status="HIT" if selected else "UNRESOLVED",
            contexts=selected,
            scanned_observations=scanned,
            query_symbol_count=len(query_symbols),
            semantic_projection=False,
        )
