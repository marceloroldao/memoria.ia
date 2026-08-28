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


_COLOR_WORDS = (
    "verde", "azul", "vermelho", "vermelha", "preto", "preta", "branco", "branca",
    "amarelo", "amarela", "cinza", "prata", "marrom", "laranja", "roxo", "roxa",
)
_COLOR_ALT = "|".join(_COLOR_WORDS)
_WORD = r"[A-Za-zÀ-ÿ0-9_.-]+"
_RESERVED_ENTITY_WORDS = {
    "e", "ou", "outro", "outra", "um", "uma", "carro", "carros", "veiculo", "veiculos",
    "veículo", "veículos", "cor", "cores",
}

_EXPLICIT_COLOR_NAME = re.compile(
    rf"(?:\bo\b|\ba\b)?\s*(?P<color>{_COLOR_ALT})\s+(?:(?:é|eh|=)\s*)?(?:um\s+|uma\s+)?(?P<entity>{_WORD})",
    re.IGNORECASE,
)
_ENTITY_COLOR = re.compile(
    rf"(?:\bmeu\b|\bminha\b|\bo\b|\ba\b)?\s*(?P<entity>{_WORD})\s*(?:é|eh|=|tem\s+cor)\s*(?P<color>{_COLOR_ALT})\b",
    re.IGNORECASE,
)
_COLOR_OF_ENTITY = re.compile(
    rf"\bcor\s+(?:da|do)\s+(?:minha\s+|meu\s+)?(?P<entity>{_WORD})\s*(?:é|eh|=)\s*(?P<color>{_COLOR_ALT})\b",
    re.IGNORECASE,
)
_QUERY_ENTITY_COLOR = (
    re.compile(rf"\bcor\s+(?:da|do)\s+(?:minha\s+|meu\s+)?(?P<entity>{_WORD})\b", re.IGNORECASE),
    re.compile(rf"\bde\s+que\s+cor\s+(?:é|eh|e)\s+(?:a\s+|o\s+|minha\s+|meu\s+)?(?P<entity>{_WORD})\b", re.IGNORECASE),
)
_QUERY_ENTITY_BY_COLOR = re.compile(
    rf"\b(?:qual|que)\s+(?:é\s+|e\s+)?(?:o\s+|a\s+)?(?:meu\s+|minha\s+)?(?:carro|veiculo|veículo)\s+(?P<color>{_COLOR_ALT})\b",
    re.IGNORECASE,
)
_QUERY_OWNED_COLORS = re.compile(
    r"\b(?:qual|quais)\s+(?:é|são|sao|e)?\s*(?:a\s+)?cor(?:es)?\s+(?:dos|das)\s+(?:meus|minhas)\s+(?:carros|veiculos|veículos)\b",
    re.IGNORECASE,
)
_OWNERSHIP_SIGNAL = re.compile(r"\b(?:eu\s+tenho|tenho|meu|meus|minha|minhas)\b", re.IGNORECASE)


def _key(value: str) -> str:
    value = unicodedata.normalize("NFKD", value)
    value = "".join(ch for ch in value if not unicodedata.combining(ch))
    return " ".join(value.casefold().strip().split())


def _clean_entity(value: str) -> str | None:
    value = value.strip().strip(".,;:!?\"")
    if not value or _key(value) in {_key(x) for x in _RESERVED_ENTITY_WORDS}:
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
    """Conservative natural-language adapter over the stable Evidence Core.

    This adapter intentionally supports a small, explicit conversational relation
    vocabulary. It must abstain when the query shape or relation is ambiguous.
    The Evidence Core remains parser-free and stores the source-backed relations.
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
            key = (_key(subject), predicate, _key(obj))
            if key not in seen:
                seen.add(key)
                extracted.append((subject, predicate, obj, confidence))

        if role == "user":
            for pattern in (_COLOR_OF_ENTITY, _ENTITY_COLOR):
                for match in pattern.finditer(text):
                    entity = _clean_entity(match.group("entity"))
                    if entity:
                        add(entity, "has_color", match.group("color").casefold(), 1.0)
                        if _OWNERSHIP_SIGNAL.search(text):
                            add("user", "owns", entity, 0.95)

            # Handles elliptical conversational constructions such as
            # "o azul é Corsa, e o verde um Saveiro" conservatively.
            for match in _EXPLICIT_COLOR_NAME.finditer(text):
                entity = _clean_entity(match.group("entity"))
                if entity:
                    add(entity, "has_color", match.group("color").casefold(), 0.95)
                    if _OWNERSHIP_SIGNAL.search(text):
                        add("user", "owns", entity, 0.95)

        rows: list[EvidenceEdge] = []
        provenance = "conversation" if timestamp is None else f"conversation:{timestamp}"
        for index, (subject, predicate, obj, confidence) in enumerate(extracted):
            memory_id = self._memory_id(
                role=role, text=text, session_id=session_id, order=order, index=index
            )
            rows.append(self.evidence.core.observe_relation(
                subject,
                predicate,
                obj,
                evidence_id=memory_id,
                source_text=text,
                provenance=provenance,
                origin="conversation-user" if role == "user" else "conversation-assistant",
                confidence=confidence,
                namespace=session_id,
            ))
        if rows:
            self.evidence.save()
        return ConversationIngestResult(
            tuple(row.evidence_id for row in rows),
            tuple(_edge_payload(row) for row in rows),
            not rows,
        )

    def _result(self, status: str, rows: list[EvidenceEdge]) -> ConversationResolveResult:
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
        return ConversationResolveResult(
            "HIT",
            min(row.confidence for row in ordered),
            tuple(row.evidence_id for row in ordered),
            "\n".join(contexts),
            tuple(_edge_payload(row) for row in ordered),
        )

    def resolve(self, *, query: str, session_id: str | None = None) -> ConversationResolveResult:
        query = query.strip()
        if not query:
            raise ValueError("query must be non-empty")
        active = list(self.evidence.core.active_edges(namespace=session_id))

        entity: str | None = None
        for pattern in _QUERY_ENTITY_COLOR:
            match = pattern.search(query)
            if match:
                entity = _clean_entity(match.group("entity"))
                break
        if entity is not None:
            rows = [e for e in active if e.predicate == "has_color" and _key(e.subject) == _key(entity)]
            values = {_key(e.object) for e in rows}
            if len(values) == 1:
                return self._result("HIT", rows)
            return self._result("UNRESOLVED" if len(values) > 1 else "MISS", [])

        match = _QUERY_ENTITY_BY_COLOR.search(query)
        if match:
            color = _key(match.group("color"))
            owned = {_key(e.object) for e in active if e.predicate == "owns" and _key(e.subject) == "user"}
            rows = [e for e in active if e.predicate == "has_color" and _key(e.object) == color and (not owned or _key(e.subject) in owned)]
            subjects = {_key(e.subject) for e in rows}
            if len(subjects) == 1:
                return self._result("HIT", rows)
            return self._result("UNRESOLVED" if len(subjects) > 1 else "MISS", [])

        if _QUERY_OWNED_COLORS.search(query):
            owned_edges = [e for e in active if e.predicate == "owns" and _key(e.subject) == "user"]
            owned = {_key(e.object): e for e in owned_edges}
            if not owned:
                return self._result("MISS", [])
            color_rows = [e for e in active if e.predicate == "has_color" and _key(e.subject) in owned]
            by_subject = {_key(e.subject) for e in color_rows}
            if by_subject != set(owned):
                return self._result("UNRESOLVED", [])
            return self._result("HIT", [*owned_edges, *color_rows])

        return self._result("UNRESOLVED", [])


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
