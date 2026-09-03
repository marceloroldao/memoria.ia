from __future__ import annotations

from dataclasses import dataclass
import hashlib
import hmac
import re
import unicodedata

from fastapi import Depends, FastAPI, Header, HTTPException
from pydantic import BaseModel, Field

from .evidence_core import EvidenceEdge
from .memory_provenance import MemoryProvenanceIndex, ProvenanceCandidate
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
_AGGREGATE_QUERY = re.compile(r"^\s*(?:quais|liste|listar|mostre|enumere)\b", re.IGNORECASE)


def _key(value: str) -> str:
    value = unicodedata.normalize("NFKD", value)
    value = "".join(ch for ch in value if not unicodedata.combining(ch))
    return " ".join(value.casefold().strip().split())


def _tokens(value: str) -> set[str]:
    return {_key(token) for token in _WORD_RE.findall(value) if _key(token) and _key(token) not in _QUERY_STOPWORDS}


def _aggregate_overlap(query_tokens: set[str], edge_tokens: set[str]) -> int:
    """Count exact terms plus conservative regular plural matches."""
    return sum(
        1
        for token in query_tokens
        if token in edge_tokens or (len(token) > 3 and token.endswith("s") and token[:-1] in edge_tokens)
    )


def _relation_term(value: str) -> str | None:
    value = value.strip().strip(".,;:!?\"")
    if not value or _key(value) in _RELATION_NOISE:
        return None
    return value


def _edge_payload(edge: EvidenceEdge, *, epoch: int | None) -> dict:
    """Public conversation relation metadata.

    EvidenceCore.epoch is an internal graph sequence and also advances for
    provenance bookkeeping. Conversation API `epoch` is therefore frozen as the
    persisted conversational order so the value is reproducible across Python,
    native/BDR and restart boundaries.
    """
    return {
        "subject": edge.subject,
        "predicate": edge.predicate,
        "object": edge.object,
        "memory_id": edge.evidence_id,
        "confidence": edge.confidence,
        "epoch": epoch,
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
    provenance: tuple[dict, ...] = ()


class ConversationSemanticService:
    """Domain-agnostic conversational recall with source-authority separation."""

    def __init__(self, evidence: ProductEvidenceService) -> None:
        self.evidence = evidence
        self.provenance = MemoryProvenanceIndex(evidence.core)

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
        parent_memory_ids: tuple[str, ...] | list[str] = (),
        corrects_memory_ids: tuple[str, ...] | list[str] = (),
    ) -> ConversationIngestResult:
        if role not in {"user", "assistant"}:
            raise ValueError("role must be 'user' or 'assistant'")
        if corrects_memory_ids and role != "user":
            raise ValueError("only user turns may explicitly correct prior memories")
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

        provenance_label = "conversation" if timestamp is None else f"conversation:{timestamp}"
        origin = "conversation-user" if role == "user" else "conversation-assistant"
        turn_id = self._memory_id(role=role, text=text, session_id=session_id, order=order, index=-1)
        turn_edge = self.evidence.core.observe_relation(
            f"turn:{turn_id}", "conversation_text", text,
            evidence_id=turn_id, source_text=text, provenance=provenance_label,
            origin=origin, confidence=1.0, namespace=session_id,
        )
        source_type = "user_correction" if corrects_memory_ids else ("user_assertion" if role == "user" else "assistant_generated")
        parents = tuple(dict.fromkeys([*parent_memory_ids, *corrects_memory_ids]))
        self.provenance.register(
            turn_id, source_type=source_type, parent_memory_ids=parents,
            created_order=order, created_time=timestamp, namespace=session_id,
        )
        for prior_id in corrects_memory_ids:
            self.provenance.supersede(prior_id, by_memory_id=turn_id, namespace=session_id)

        relation_rows: list[EvidenceEdge] = []
        for index, (subject, predicate, obj, confidence) in enumerate(extracted):
            memory_id = self._memory_id(role=role, text=text, session_id=session_id, order=order, index=index)
            row = self.evidence.core.observe_relation(
                subject, predicate, obj, evidence_id=memory_id, source_text=text,
                provenance=provenance_label, origin=origin, confidence=confidence,
                namespace=session_id,
            )
            relation_rows.append(row)
            self.provenance.register(
                memory_id, source_type="derived_relation", parent_memory_ids=(turn_id,),
                created_order=order, created_time=timestamp, namespace=session_id,
            )
        self.evidence.save()
        return ConversationIngestResult(
            (turn_edge.evidence_id, *(row.evidence_id for row in relation_rows)),
            tuple(_edge_payload(row, epoch=order) for row in relation_rows),
            not relation_rows,
        )

    def _result(self, status: str, rows: list[EvidenceEdge], *, confidence: float | None = None, namespace: str | None = None) -> ConversationResolveResult:
        if status != "HIT" or not rows:
            return ConversationResolveResult(status, 0.0, (), "", (), ())
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
        relation_rows = [row for row in ordered if row.predicate != "conversation_text" and not row.predicate.startswith("provenance_")]
        provenance_rows = []
        created_order_by_id: dict[str, int | None] = {}
        for row in ordered:
            direct = self.provenance.inspect(row.evidence_id, namespace=namespace)
            source = self.provenance.ultimate_source(row.evidence_id, namespace=namespace)
            created_order_by_id[row.evidence_id] = direct.created_order
            provenance_rows.append({
                "memory_id": direct.memory_id,
                "source_type": source.source_type,
                "source_authority": source.authority,
                "immediate_source_type": direct.source_type,
                "parent_memory_ids": list(direct.parent_memory_ids),
                "ultimate_source_memory_id": source.memory_id,
                "created_order": direct.created_order,
                "created_time": direct.created_time,
                "superseded_by": direct.superseded_by,
            })
        return ConversationResolveResult(
            "HIT",
            float(confidence if confidence is not None else min(row.confidence for row in ordered)),
            tuple(row.evidence_id for row in ordered),
            "\n".join(contexts),
            tuple(_edge_payload(row, epoch=created_order_by_id.get(row.evidence_id)) for row in relation_rows),
            tuple(provenance_rows),
        )

    def _select_authoritative(self, scored: list[tuple[float, int, EvidenceEdge]], *, namespace: str | None) -> tuple[float, EvidenceEdge] | None:
        if not scored:
            return None
        best_relevance = max(score for score, _order, _edge in scored)
        pool = [(score, order, edge) for score, order, edge in scored if score >= best_relevance - 0.15]
        selected = self.provenance.select(
            [ProvenanceCandidate(edge.evidence_id, score, order) for score, order, edge in pool],
            namespace=namespace,
        )
        if selected is None:
            return None
        for score, _order, edge in pool:
            if edge.evidence_id == selected.memory_id:
                return score, edge
        return None

    @staticmethod
    def _distinct_claims(scored: list[tuple[float, int, EvidenceEdge]]) -> set[tuple[str, str, str]]:
        return {(_key(edge.subject), edge.predicate, _key(edge.object)) for _score, _order, edge in scored}

    def _ultimate_source_ids(self, scored: list[tuple[float, int, EvidenceEdge]], *, namespace: str | None) -> set[str]:
        roots: set[str] = set()
        for _score, _order, edge in scored:
            source = self.provenance.active_ultimate_source(edge.evidence_id, namespace=namespace)
            if source is not None:
                roots.add(source.memory_id)
        return roots

    def _native_reference_confidence(self, *, qtokens: set[str], edge: EvidenceEdge, namespace: str | None) -> float:
        overlap = len(qtokens & _tokens(edge.source_text)) / max(1, len(qtokens))
        source = self.provenance.active_ultimate_source(edge.evidence_id, namespace=namespace)
        authority = 0.0 if source is None else max(0.0, min(1.0, float(source.authority)))
        return round(min(0.8, 0.30 + 0.25 * overlap + 0.25 * authority), 6)

    def resolve(self, *, query: str, session_id: str | None = None) -> ConversationResolveResult:
        query = query.strip()
        if not query:
            raise ValueError("query must be non-empty")
        active = list(self.evidence.core.active_edges(namespace=session_id))
        qtokens = _tokens(query)
        if not qtokens:
            return self._result("UNRESOLVED", [])

        relations = [e for e in active if e.predicate != "conversation_text" and not e.predicate.startswith("provenance_")]
        if _AGGREGATE_QUERY.search(query):
            grouped: dict[tuple[str, str, str], list[tuple[float, int, EvidenceEdge]]] = {}
            for edge in relations:
                overlap = _aggregate_overlap(qtokens, _tokens(edge.subject) | _tokens(edge.object))
                if overlap:
                    claim = (_key(edge.subject), edge.predicate, _key(edge.object))
                    grouped.setdefault(claim, []).append((float(overlap), edge.epoch, edge))
            aggregate_rows: list[EvidenceEdge] = []
            for claim in sorted(grouped):
                selected_claim = self._select_authoritative(grouped[claim], namespace=session_id)
                if selected_claim is not None:
                    aggregate_rows.append(selected_claim[1])
            if aggregate_rows:
                return self._result(
                    "HIT",
                    aggregate_rows,
                    confidence=min(0.8, min(edge.confidence for edge in aggregate_rows)),
                    namespace=session_id,
                )

        anchored: list[tuple[float, int, EvidenceEdge]] = []
        for edge in relations:
            overlap = len(qtokens & (_tokens(edge.subject) | _tokens(edge.object)))
            if overlap:
                anchored.append((float(overlap), edge.epoch, edge))
        if anchored:
            best_overlap = max(score for score, _order, _edge in anchored)
            exact_best = [row for row in anchored if row[0] == best_overlap]
            if len(self._distinct_claims(exact_best)) > 1 and len(self._ultimate_source_ids(exact_best, namespace=session_id)) > 1:
                return self._result("UNRESOLVED", [])
        selected = self._select_authoritative(anchored, namespace=session_id)
        if selected is not None:
            _relevance, edge = selected
            return self._result(
                "HIT", [edge],
                confidence=self._native_reference_confidence(qtokens=qtokens, edge=edge, namespace=session_id),
                namespace=session_id,
            )

        turns = [edge for edge in active if edge.predicate == "conversation_text"]
        ranked: list[tuple[float, int, EvidenceEdge]] = []
        for edge in turns:
            overlap = len(qtokens & _tokens(edge.source_text))
            if overlap:
                ranked.append((overlap / max(1, len(qtokens)), edge.epoch, edge))
        if ranked:
            best_score = max(score for score, _order, _edge in ranked)
            exact_best = [row for row in ranked if abs(row[0] - best_score) < 1e-12]
            if len(exact_best) > 1:
                roots = self._ultimate_source_ids(exact_best, namespace=session_id)
                contexts = {_key(edge.source_text) for _score, _order, edge in exact_best}
                if len(roots) > 1 and len(contexts) > 1:
                    return self._result("UNRESOLVED", [])
        selected = self._select_authoritative(ranked, namespace=session_id)
        if selected is None:
            return self._result("UNRESOLVED", [])
        _score, edge = selected
        return self._result(
            "HIT", [edge],
            confidence=self._native_reference_confidence(qtokens=qtokens, edge=edge, namespace=session_id),
            namespace=session_id,
        )


class ConversationIngestRequest(BaseModel):
    role: str = Field(pattern="^(user|assistant)$")
    text: str = Field(min_length=1, max_length=20000)
    session_id: str | None = Field(default=None, max_length=256)
    timestamp: str | None = Field(default=None, max_length=128)
    order: int | None = Field(default=None, ge=0)
    parent_memory_ids: list[str] = Field(default_factory=list)
    corrects_memory_ids: list[str] = Field(default_factory=list)


class ConversationResolveRequest(BaseModel):
    query: str = Field(min_length=1, max_length=4000)
    session_id: str | None = Field(default=None, max_length=256)


def attach_conversation_routes(app: FastAPI, *, api_key: str, service: ConversationSemanticService) -> None:
    def require_admin(x_memoria_key: str | None = Header(default=None)) -> None:
        if x_memoria_key is None or not hmac.compare_digest(x_memoria_key, api_key):
            raise HTTPException(status_code=401, detail="invalid API credentials")

    @app.post("/api/v1/conversation/ingest", dependencies=[Depends(require_admin)])
    def ingest(request: ConversationIngestRequest):
        try:
            result = service.ingest(
                role=request.role, text=request.text, session_id=request.session_id,
                timestamp=request.timestamp, order=request.order,
                parent_memory_ids=request.parent_memory_ids,
                corrects_memory_ids=request.corrects_memory_ids,
            )
        except ValueError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc
        return {"stored_memory_ids": list(result.memory_ids), "relations": list(result.relations), "unresolved": result.unresolved}

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
            "provenance": list(result.provenance),
        }
