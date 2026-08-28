from __future__ import annotations

from dataclasses import dataclass
import hashlib
import hmac
import re
import unicodedata

from fastapi import Depends, FastAPI, Header, HTTPException
from pydantic import BaseModel, Field

from .evidence_core import EvidenceEdge
from .product_evidence import ProductEvidenceService

_WORD_RE = re.compile(r"[\wÀ-ÿ.-]+", re.UNICODE)
_COPULAR = re.compile(
    r"(?:\bmeu\b|\bminha\b|\bo\b|\ba\b)?\s*(?P<left>[\wÀ-ÿ.-]+)\s*(?:é|eh|=)\s*(?:um\s+|uma\s+)?(?P<right>[\wÀ-ÿ.-]+)",
    re.IGNORECASE,
)
_ELLIPTIC = re.compile(
    r"(?:^|[,;.]|\be\b)\s*(?:o|a)\s+(?P<left>[\wÀ-ÿ.-]+)\s+(?:um\s+|uma\s+)(?P<right>[\wÀ-ÿ.-]+)",
    re.IGNORECASE,
)
_QUERY_STOPWORDS = {
    "a", "ao", "aos", "as", "da", "das", "de", "do", "dos", "e", "eh", "é", "em", "eu",
    "foi", "me", "meu", "meus", "minha", "minhas", "o", "os", "para", "por", "que", "qual",
    "quais", "um", "uma", "uns", "umas", "voce", "você",
}
_RELATION_NOISE = _QUERY_STOPWORDS | {"outro", "outra"}


def _key(value: str) -> str:
    value = unicodedata.normalize("NFKD", value)
    value = "".join(ch for ch in value if not unicodedata.combining(ch))
    return " ".join(value.casefold().strip().split())


def _tokens(value: str) -> set[str]:
    return {
        _key(token)
        for token in _WORD_RE.findall(value)
        if _key(token) and _key(token) not in _QUERY_STOPWORDS
    }


def _relation_term(value: str) -> str | None:
    value = value.strip().strip(".,;:!?\"")
    if not value or _key(value) in _RELATION_NOISE:
        return None
    return value


def _edge_payload(edge: EvidenceEdge) -> dict:
    return {
        "subject": edge.subject,
        "predicate": edge.predicate,
        "object": edge.object,
        "memory_id": edge.evidence_id,
        "confidence": edge.confidence,
        "epoch": edge.epoch,
        "namespace": edge.namespace,
    }


@dataclass(frozen=True, slots=True)
class ConversationIngestResult:
    memory_ids: tuple[str, ...]
    relations: tuple[dict, ...]
    unresolved: bool


@dataclass(frozen=True, slots=True)
class ConversationResolveResult:
    status: str
    confidence: float
    memory_ids: tuple[str, ...]
    selected_context: str
    relations: tuple[dict, ...]


class ConversationSemanticService:
    """Domain-agnostic conversational recall adapter over the Evidence Core.

    Domain examples belong in tests, not in the runtime ontology. Every turn is
    retained as source evidence. The adapter may additionally extract only generic
    surface relations (currently conservative copular/elliptical A-is-B forms).
    Resolution first uses explicit relation anchors and then a lexical source-turn
    fallback. Ties that cannot be justified are returned as UNRESOLVED.
    """

    def __init__(self, evidence: ProductEvidenceService) -> None:
        self.evidence = evidence

    @staticmethod
    def _memory_id(*, role: str, text: str, session_id: str | None, order: int | None, index: int) -> str:
        raw = f"{session_id or ''}\0{order if order is not None else ''}\0{role}\0{text}\0{index}".encode("utf-8")
        return "conv:" + hashlib.sha256(raw).hexdigest()[:24]

    def ingest(
        self,
        *,
        role: str,
        text: str,
        session_id: str | None = None,
        order: int | None = None,
        timestamp: str | None = None,
    ) -> ConversationIngestResult:
        if role not in {"user", "assistant"}:
            raise ValueError("role must be 'user' or 'assistant'")
        text = text.strip()
        if not text:
            raise ValueError("text must be non-empty")

        extracted: list[tuple[str, str, str, float]] = []
        seen: set[tuple[str, str, str]] = set()

        def add(subject: str, predicate: str, obj: str, confidence: float) -> None:
            left, right = _relation_term(subject), _relation_term(obj)
            if left is None or right is None:
                return
            key = (_key(left), predicate, _key(right))
            if key not in seen:
                seen.add(key)
                extracted.append((left, predicate, right, confidence))

        for pattern, confidence in ((_COPULAR, 0.95), (_ELLIPTIC, 0.85)):
            for match in pattern.finditer(text):
                add(match.group("left"), "is", match.group("right"), confidence)

        provenance = "conversation" if timestamp is None else f"conversation:{timestamp}"
        origin = "conversation-user" if role == "user" else "conversation-assistant"
        rows: list[EvidenceEdge] = []

        # Each raw turn gets its own subject, so long conversations remain fully
        # recoverable instead of collapsing to the latest turn in active_edges().
        turn_id = self._memory_id(role=role, text=text, session_id=session_id, order=order, index=-1)
        rows.append(self.evidence.core.observe_relation(
            f"turn:{turn_id}",
            "conversation_text",
            text,
            evidence_id=turn_id,
            source_text=text,
            provenance=provenance,
            origin=origin,
            confidence=1.0,
            namespace=session_id,
        ))

        relation_rows: list[EvidenceEdge] = []
        for index, (subject, predicate, obj, confidence) in enumerate(extracted):
            memory_id = self._memory_id(role=role, text=text, session_id=session_id, order=order, index=index)
            relation_rows.append(self.evidence.core.observe_relation(
                subject,
                predicate,
                obj,
                evidence_id=memory_id,
                source_text=text,
                provenance=provenance,
                origin=origin,
                confidence=confidence,
                namespace=session_id,
            ))
        rows.extend(relation_rows)
        self.evidence.save()
        return ConversationIngestResult(
            tuple(row.evidence_id for row in rows),
            tuple(_edge_payload(row) for row in relation_rows),
            not relation_rows,
        )

    def _result(self, status: str, rows: list[EvidenceEdge], *, confidence: float | None = None) -> ConversationResolveResult:
        if status != "HIT" or not rows:
            return ConversationResolveResult(status, 0.0, (), "", ())
        ordered: list[EvidenceEdge] = []
        seen_ids: set[str] = set()
        for row in rows:
            if row.evidence_id not in seen_ids:
                seen_ids.add(row.evidence_id)
                ordered.append(row)
        contexts: list[str] = []
        for row in ordered:
            if row.source_text not in contexts:
                contexts.append(row.source_text)
        relation_rows = [row for row in ordered if row.predicate != "conversation_text"]
        return ConversationResolveResult(
            "HIT",
            float(confidence if confidence is not None else min(row.confidence for row in ordered)),
            tuple(row.evidence_id for row in ordered),
            "\n".join(contexts),
            tuple(_edge_payload(row) for row in relation_rows),
        )

    def resolve(self, *, query: str, session_id: str | None = None) -> ConversationResolveResult:
        query = query.strip()
        if not query:
            raise ValueError("query must be non-empty")
        active = list(self.evidence.core.active_edges(namespace=session_id))
        qtokens = _tokens(query)
        if not qtokens:
            return self._result("UNRESOLVED", [])

        relations = [edge for edge in active if edge.predicate != "conversation_text"]
        anchored: list[tuple[int, int, EvidenceEdge]] = []
        for edge in relations:
            subject_tokens = _tokens(edge.subject)
            object_tokens = _tokens(edge.object)
            overlap = len(qtokens & (subject_tokens | object_tokens))
            if overlap:
                anchored.append((overlap, edge.epoch, edge))
        if anchored:
            best_overlap = max(item[0] for item in anchored)
            best = [item for item in anchored if item[0] == best_overlap]
            if len(best) == 1:
                edge = best[0][2]
                return self._result("HIT", [edge], confidence=min(1.0, 0.65 + 0.15 * best_overlap))
            distinct = {(_key(item[2].subject), item[2].predicate, _key(item[2].object)) for item in best}
            if len(distinct) > 1:
                return self._result("UNRESOLVED", [])

        turns = [edge for edge in active if edge.predicate == "conversation_text"]
        ranked: list[tuple[float, int, EvidenceEdge]] = []
        for edge in turns:
            stokens = _tokens(edge.source_text)
            overlap = len(qtokens & stokens)
            if not overlap:
                continue
            score = overlap / max(1, len(qtokens))
            ranked.append((score, edge.epoch, edge))
        if not ranked:
            return self._result("UNRESOLVED", [])
        ranked.sort(key=lambda item: (-item[0], -item[1], item[2].evidence_id))
        best_score = ranked[0][0]
        tied = [item for item in ranked if abs(item[0] - best_score) < 1e-12]
        if len(tied) > 1:
            return self._result("UNRESOLVED", [])
        return self._result("HIT", [ranked[0][2]], confidence=min(0.8, 0.45 + 0.35 * best_score))


class ConversationIngestRequest(BaseModel):
    role: str = Field(pattern="^(user|assistant)$")
    text: str = Field(min_length=1, max_length=20000)
    session_id: str | None = Field(default=None, max_length=256)
    timestamp: str | None = Field(default=None, max_length=128)
    order: int | None = Field(default=None, ge=0)


class ConversationResolveRequest(BaseModel):
    query: str = Field(min_length=1, max_length=4000)
    session_id: str | None = Field(default=None, max_length=256)


def attach_conversation_routes(
    app: FastAPI,
    *,
    api_key: str,
    service: ConversationSemanticService,
) -> None:
    def require_admin(x_memoria_key: str | None = Header(default=None)) -> None:
        if x_memoria_key is None or not hmac.compare_digest(x_memoria_key, api_key):
            raise HTTPException(status_code=401, detail="invalid API credentials")

    @app.post("/api/v1/conversation/ingest", dependencies=[Depends(require_admin)])
    def ingest(request: ConversationIngestRequest):
        try:
            result = service.ingest(
                role=request.role,
                text=request.text,
                session_id=request.session_id,
                timestamp=request.timestamp,
                order=request.order,
            )
        except ValueError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc
        return {
            "stored_memory_ids": list(result.memory_ids),
            "relations": list(result.relations),
            "unresolved": result.unresolved,
        }

    @app.post("/api/v1/conversation/resolve", dependencies=[Depends(require_admin)])
    def resolve(request: ConversationResolveRequest):
        try:
            result = service.resolve(query=request.query, session_id=request.session_id)
        except ValueError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc
        return {
            "status": result.status,
            "confidence": result.confidence,
            "memory_ids": list(result.memory_ids),
            "selected_context": result.selected_context,
            "relations": list(result.relations),
        }
