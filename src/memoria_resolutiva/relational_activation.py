from __future__ import annotations

from dataclasses import dataclass
import unicodedata


@dataclass(frozen=True, slots=True)
class RelationalActivationResult:
    status: str
    confidence: float
    selected_context: str
    concepts: tuple[str, ...]
    memory_ids: tuple[str, ...] = ()


def _key(value: str) -> str:
    value = unicodedata.normalize("NFKD", value)
    value = "".join(ch for ch in value if not unicodedata.combining(ch))
    return " ".join(value.casefold().strip().split())


def _render_edge(edge: object) -> str:
    subject = str(getattr(edge, "subject", "") or "").strip()
    predicate = str(getattr(edge, "predicate", "") or "").strip()
    object_ = str(getattr(edge, "object", "") or "").strip()
    return f"{subject} | {predicate} | {object_}" if subject and predicate and object_ else ""


def _from_native_payload(payload: object, *, concept: str) -> RelationalActivationResult | None:
    if not isinstance(payload, dict):
        return None
    status = str(payload.get("status") or "")
    if status == "UNSUPPORTED":
        return None
    if status not in {"HIT", "UNRESOLVED"}:
        raise RuntimeError("native relational activation returned invalid status")
    rows = payload.get("relations") or []
    memory_ids: list[str] = []
    concepts: list[str] = [concept]
    if isinstance(rows, list):
        for row in rows:
            if not isinstance(row, dict):
                continue
            evidence_id = str(row.get("evidence_id") or "")
            if evidence_id and evidence_id not in memory_ids:
                memory_ids.append(evidence_id)
            for key in ("subject_key", "object_key"):
                value = str(row.get(key) or "")
                if value and value not in concepts:
                    concepts.append(value)
    return RelationalActivationResult(
        status,
        float(payload.get("confidence", 0.0) or 0.0),
        str(payload.get("selected_context") or ""),
        tuple(concepts),
        tuple(memory_ids),
    )


def activate(
    resolver: object,
    *,
    concept: str,
    session_id: str | None = None,
    depth: int = 2,
    budget: int = 1200,
    hop_decay: float = 0.72,
    min_confidence: float = 0.45,
) -> RelationalActivationResult:
    """Traverse relation memory structurally, preferring the native runtime.

    NativeConversationService can expose ``activate_relations`` through the
    optional additive ABI-v1 symbol. When it is unavailable, the reference
    EvidenceCore traversal remains as compatibility fallback. Neither path
    synthesizes natural-language memory queries.
    """
    if depth < 1:
        raise ValueError("depth must be >= 1")
    if budget < 1:
        raise ValueError("budget must be >= 1")

    native_activate = getattr(resolver, "activate_relations", None)
    if callable(native_activate):
        native_result = _from_native_payload(
            native_activate(
                concept=concept,
                session_id=session_id,
                depth=depth,
                budget=budget,
                hop_decay=hop_decay,
                min_confidence=min_confidence,
            ),
            concept=concept,
        )
        if native_result is not None:
            return native_result

    evidence = getattr(resolver, "evidence", None)
    core = getattr(evidence, "core", None)
    active_edges = getattr(core, "active_edges", None)
    if not callable(active_edges):
        return RelationalActivationResult("UNSUPPORTED", 0.0, "", ())

    root = _key(concept)
    if not root:
        return RelationalActivationResult("UNRESOLVED", 0.0, "", ())

    edges = [
        edge for edge in active_edges(namespace=session_id)
        if str(getattr(edge, "predicate", "")) != "conversation_text"
        and not str(getattr(edge, "predicate", "")).startswith("provenance_")
    ]

    frontier = {root}
    visited = {root}
    selected: list[tuple[int, float, object]] = []
    selected_ids: list[str] = []
    concepts: list[str] = [concept]

    for hop in range(1, depth + 1):
        if not frontier:
            break
        next_frontier: set[str] = set()
        hop_factor = hop_decay ** (hop - 1)
        for edge in edges:
            subject = _key(str(getattr(edge, "subject", "") or ""))
            object_ = _key(str(getattr(edge, "object", "") or ""))
            if subject not in frontier and object_ not in frontier:
                continue
            base_confidence = float(getattr(edge, "confidence", 0.0) or 0.0)
            effective = max(0.0, min(1.0, base_confidence * hop_factor))
            if effective < min_confidence:
                continue
            selected.append((hop, effective, edge))
            evidence_id = str(getattr(edge, "evidence_id", "") or "")
            if evidence_id and evidence_id not in selected_ids:
                selected_ids.append(evidence_id)
            neighbor = object_ if subject in frontier else subject
            if neighbor and neighbor not in visited:
                visited.add(neighbor)
                next_frontier.add(neighbor)
                raw_neighbor = str(getattr(edge, "object", "") if subject in frontier else getattr(edge, "subject", ""))
                if raw_neighbor and raw_neighbor not in concepts:
                    concepts.append(raw_neighbor)
        frontier = next_frontier

    if not selected:
        return RelationalActivationResult("UNRESOLVED", 0.0, "", tuple(concepts))

    selected.sort(key=lambda row: (row[0], -row[1], _render_edge(row[2])))
    rendered: list[str] = []
    used = 0
    confidences: list[float] = []
    for hop, confidence, edge in selected:
        line = _render_edge(edge)
        if not line or line in rendered:
            continue
        cost = len(line) + (1 if rendered else 0)
        if used + cost > budget:
            break
        rendered.append(line)
        used += cost
        confidences.append(confidence)

    if not rendered:
        return RelationalActivationResult("UNRESOLVED", 0.0, "", tuple(concepts))

    return RelationalActivationResult(
        "HIT",
        min(confidences),
        "\n".join(rendered),
        tuple(concepts),
        tuple(selected_ids),
    )
