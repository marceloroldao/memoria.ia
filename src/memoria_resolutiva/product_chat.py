from __future__ import annotations

from dataclasses import asdict, dataclass
import json
import re
from time import perf_counter
from typing import Iterable, Literal, Protocol, Sequence

from .llm_adapter import LLMAdapter, estimate_tokens
from .product_identity import MemoryScope
from .product_service import EnterpriseMemoryService
from .relational_activation import activate as activate_relations

ChatMode = Literal["baseline", "memoria"]
MIN_COMPACT_RELATION_CONFIDENCE = 0.90
_POSSESSIVE_TYPE_QUERY = re.compile(
    r"\b(?:meu|minha|meus|minhas)\s+(?P<kind>[\wÀ-ÿ.-]+)\b",
    re.IGNORECASE,
)
_WORD_RE = re.compile(r"[\wÀ-ÿ.-]+", re.UNICODE)
_GENERIC_RELATION_STOPWORDS = {
    "a", "as", "ao", "aos", "como", "da", "das", "de", "do", "dos", "e", "em",
    "esta", "está", "estao", "estão", "eu", "funciona", "funcionar", "me", "meu", "meus",
    "minha", "minhas", "nome", "o", "os", "para", "por", "qual", "quais", "que", "um", "uma",
    "voce", "você", "caiu", "cair", "falhou", "falha", "problema", "status",
}
_MAX_GENERIC_RELATION_CONCEPTS = 2
_MAX_RELATIONAL_HOPS = 2
_RELATIONAL_HOP_DECAY = 0.72
_MIN_SECOND_HOP_CONFIDENCE = 0.45
_MAX_RELATIONAL_CONTEXT_CHARS = 1200


class ConversationResolver(Protocol):
    def resolve(self, *, query: str, session_id: str | None = None): ...


@dataclass(frozen=True, slots=True)
class ChatMetrics:
    mode: ChatMode
    memory_hits: int
    memory_misses: int
    retrieved_context_chars: int
    context_sent_chars: int
    input_tokens: int
    output_tokens: int
    memory_latency_ms: float
    llm_latency_ms: float
    external_calls: int
    estimated_cost_usd: float | None
    provider: str
    model: str

    def as_dict(self) -> dict:
        return asdict(self)


@dataclass(frozen=True, slots=True)
class ChatResult:
    text: str
    context: tuple[str, ...]
    metrics: ChatMetrics


def _materialize(payload: object) -> str:
    if isinstance(payload, str):
        return payload
    return json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _append_unique(items: list[str], value: str) -> None:
    normalized = " ".join(str(value).split()).strip()
    if normalized and normalized not in items:
        items.append(normalized)


def _append_with_budget(items: list[str], value: str, *, budget: int) -> bool:
    normalized = " ".join(str(value).split()).strip()
    if not normalized or normalized in items:
        return True
    used = sum(len(item) for item in items) + max(0, len(items) - 1)
    if used + len(normalized) > budget:
        return False
    items.append(normalized)
    return True


def _pluralize_pt(value: str) -> str:
    word = value.strip().strip(".,;:!?\"")
    if not word:
        return word
    lower = word.casefold()
    if lower.endswith("s"):
        return word
    if lower.endswith("m"):
        return word[:-1] + "ns"
    if lower.endswith("l"):
        return word[:-1] + "is"
    if lower.endswith("r") or lower.endswith("z"):
        return word + "es"
    return word + "s"


def _generic_relation_concepts(message: str) -> tuple[str, ...]:
    words = _WORD_RE.findall(message)
    if "?" not in message and len(words) > 4:
        return ()
    concepts: list[str] = []
    seen: set[str] = set()
    for word in words:
        key = word.casefold().strip(".,;:!?")
        if len(key) < 2 or key in _GENERIC_RELATION_STOPWORDS:
            continue
        if key in seen:
            continue
        seen.add(key)
        concepts.append(word.strip(".,;:!?"))
        if len(concepts) >= _MAX_GENERIC_RELATION_CONCEPTS:
            break
    return tuple(concepts)


def _activation_concepts(message: str) -> tuple[str, ...]:
    match = _POSSESSIVE_TYPE_QUERY.search(message)
    if match is not None:
        return (match.group("kind"),)
    return _generic_relation_concepts(message)


def _rank_relational_context(message: str, selected_context: str) -> str:
    """Rank retrieved relations against the current input without dropping evidence.

    The ranking remains deterministic and local. Relations mentioning the
    possessive target concept are preferred, and an entity that is supported by
    multiple edges receives a convergence boost. This lets a relation such as
    ``gato | is | Alt`` reinforce ``Alt | is | gato`` while keeping Vivi/Lay in
    the context for the LLM to inspect.
    """
    lines = [line.strip() for line in str(selected_context or "").splitlines() if line.strip()]
    if len(lines) < 2:
        return "\n".join(lines)

    match = _POSSESSIVE_TYPE_QUERY.search(message)
    target = match.group("kind").casefold().strip() if match is not None else ""
    query_terms = {
        token.casefold().strip(".,;:!?")
        for token in _WORD_RE.findall(message)
        if token.casefold().strip(".,;:!?") not in _GENERIC_RELATION_STOPWORDS
    }

    parsed: list[tuple[str, str, str, str]] = []
    entity_frequency: dict[str, int] = {}
    for line in lines:
        parts = [part.strip() for part in line.split("|", 2)]
        if len(parts) == 3:
            subject, predicate, object_ = parts
        else:
            subject, predicate, object_ = line, "", ""
        parsed.append((line, subject, predicate, object_))
        for entity in (subject, object_):
            key = entity.casefold().strip()
            if key and key not in query_terms and key != target:
                entity_frequency[key] = entity_frequency.get(key, 0) + 1

    ownership_markers = {"usuario", "usuário", "owner", "belongs_to", "pertence"}

    def score(row: tuple[str, str, str, str]) -> tuple[float, str]:
        line, subject, _predicate, object_ = row
        subject_key = subject.casefold().strip()
        object_key = object_.casefold().strip()
        line_terms = {token.casefold() for token in _WORD_RE.findall(line)}
        value = 0.0
        if target and target in line_terms:
            value += 4.0
        value += 1.5 * len(query_terms & line_terms)
        counterpart = object_key if subject_key == target else subject_key if object_key == target else ""
        if counterpart:
            value += 2.0 * max(0, entity_frequency.get(counterpart, 0) - 1)
        if ownership_markers & line_terms:
            value += 3.0
        return (-value, line.casefold())

    parsed.sort(key=score)
    return "\n".join(row[0] for row in parsed)


def _relation_probe_queries(message: str) -> tuple[str, ...]:
    """Temporary compatibility fallback for resolvers without structural graph access."""
    match = _POSSESSIVE_TYPE_QUERY.search(message)
    if match is not None:
        kind = match.group("kind")
        plural = _pluralize_pt(kind)
        return (f"Quais {plural} você conhece?",) if plural else ()
    concepts = _generic_relation_concepts(message)
    return tuple(f"O que está relacionado a {concept}?" for concept in concepts)


def _result_confidence(resolved: object) -> float:
    try:
        return max(0.0, min(1.0, float(getattr(resolved, "confidence", 0.0) or 0.0)))
    except (TypeError, ValueError):
        return 0.0


def _second_hop_probe(resolved: object, *, original_message: str) -> str | None:
    if _result_confidence(resolved) * _RELATIONAL_HOP_DECAY < _MIN_SECOND_HOP_CONFIDENCE:
        return None
    selected = str(getattr(resolved, "selected_context", "") or "")
    original = {token.casefold() for token in _WORD_RE.findall(original_message)}
    candidates = _generic_relation_concepts(selected)
    for concept in candidates:
        if concept.casefold() in original:
            continue
        return f"O que está relacionado a {concept}?"
    return None


def _minimal_factual_context(resolved: object, selected: str) -> str:
    normalized = " ".join(selected.split()).strip()
    if not normalized:
        return normalized
    if normalized.upper().startswith(("CURRENT:", "PREVIOUS:", "TRANSITION:")):
        return normalized

    relations = tuple(getattr(resolved, "relations", ()) or ())
    provenance = tuple(getattr(resolved, "provenance", ()) or ())
    memory_ids = tuple(getattr(resolved, "memory_ids", ()) or ())
    if len(relations) != 1 or len(provenance) != 1 or len(memory_ids) != 1:
        return normalized

    relation = relations[0]
    if not isinstance(relation, dict):
        return normalized
    try:
        confidence = float(relation.get("confidence", 0.0))
    except (TypeError, ValueError):
        return normalized
    if confidence < MIN_COMPACT_RELATION_CONFIDENCE:
        return normalized

    subject = " ".join(str(relation.get("subject") or "").split()).strip()
    predicate = " ".join(str(relation.get("predicate") or "").split()).strip()
    object_ = " ".join(str(relation.get("object") or "").split()).strip()
    if not subject or not predicate or not object_:
        return normalized

    compact = f"{subject} | {predicate} | {object_}"
    return compact if len(compact) < len(normalized) else normalized


def profile_namespace(scope: MemoryScope) -> str | None:
    application = (scope.application_id or "default").strip()
    user = (scope.user_id or "").strip()
    if not application and not user:
        return None
    return f"profile:{application}:{user}" if user else f"profile:{application}"


class ProductChatService:
    def __init__(
        self,
        memory: EnterpriseMemoryService,
        adapter: LLMAdapter,
        *,
        conversation_resolver: ConversationResolver | None = None,
    ):
        self.memory = memory
        self.adapter = adapter
        self.conversation_resolver = conversation_resolver

    def run(
        self,
        *,
        scope: MemoryScope,
        message: str,
        mode: ChatMode,
        baseline_context: Sequence[str] = (),
        memory_keys: Iterable[str] = (),
    ) -> ChatResult:
        if mode not in ("baseline", "memoria"):
            raise ValueError("mode must be 'baseline' or 'memoria'")

        hits = misses = 0
        memory_ms = 0.0
        retrieved: list[str] = []
        retrieved_chars = 0

        if mode == "baseline":
            context = tuple(str(item) for item in baseline_context)
        else:
            start = perf_counter()

            if self.conversation_resolver is not None:
                namespaces: list[str | None] = []
                if scope.agent_id:
                    namespaces.append(scope.agent_id)
                profile = profile_namespace(scope)
                if profile and profile not in namespaces:
                    namespaces.append(profile)
                if not namespaces:
                    namespaces.append(None)

                resolver_hit = False
                activation_concepts = _activation_concepts(message)
                fallback_probes = _relation_probe_queries(message)

                # Preserve the established lookup hierarchy: try the original
                # question in every eligible namespace before any expansion.
                for namespace in namespaces:
                    direct = self.conversation_resolver.resolve(query=message, session_id=namespace)
                    if str(getattr(direct, "status", "")) != "HIT":
                        continue
                    selected = str(getattr(direct, "selected_context", "") or "")
                    normalized = " ".join(selected.split()).strip()
                    if not normalized:
                        continue
                    resolver_hit = True
                    retrieved_chars += len(normalized)
                    _append_with_budget(
                        retrieved,
                        _minimal_factual_context(direct, normalized),
                        budget=_MAX_RELATIONAL_CONTEXT_CHARS,
                    )
                    break

                # Only after all direct namespaces miss do we activate graph
                # neighborhoods. This keeps session/profile precedence stable.
                if not resolver_hit:
                    for namespace in namespaces:
                        structural_supported = False
                        for concept in activation_concepts:
                            activated = activate_relations(
                                self.conversation_resolver,
                                concept=concept,
                                session_id=namespace,
                                depth=_MAX_RELATIONAL_HOPS,
                                budget=_MAX_RELATIONAL_CONTEXT_CHARS,
                                hop_decay=_RELATIONAL_HOP_DECAY,
                                min_confidence=_MIN_SECOND_HOP_CONFIDENCE,
                            )
                            if activated.status != "UNSUPPORTED":
                                structural_supported = True
                            if activated.status != "HIT" or not activated.selected_context:
                                continue
                            resolver_hit = True
                            ranked_context = _rank_relational_context(message, activated.selected_context)
                            retrieved_chars += len(ranked_context)
                            _append_with_budget(
                                retrieved,
                                ranked_context,
                                budget=_MAX_RELATIONAL_CONTEXT_CHARS,
                            )
                        if resolver_hit:
                            break

                        if not structural_supported:
                            for probe in fallback_probes:
                                resolved = self.conversation_resolver.resolve(query=probe, session_id=namespace)
                                if str(getattr(resolved, "status", "")) != "HIT":
                                    continue
                                selected = str(getattr(resolved, "selected_context", "") or "")
                                normalized = " ".join(selected.split()).strip()
                                if not normalized:
                                    continue
                                resolver_hit = True
                                retrieved_chars += len(normalized)
                                _append_with_budget(
                                    retrieved,
                                    _minimal_factual_context(resolved, normalized),
                                    budget=_MAX_RELATIONAL_CONTEXT_CHARS,
                                )
                                second_probe = _second_hop_probe(resolved, original_message=message)
                                if second_probe is not None:
                                    second = self.conversation_resolver.resolve(query=second_probe, session_id=namespace)
                                    if str(getattr(second, "status", "")) == "HIT":
                                        second_selected = str(getattr(second, "selected_context", "") or "")
                                        second_normalized = " ".join(second_selected.split()).strip()
                                        if second_normalized:
                                            retrieved_chars += len(second_normalized)
                                            _append_with_budget(
                                                retrieved,
                                                _minimal_factual_context(second, second_normalized),
                                                budget=_MAX_RELATIONAL_CONTEXT_CHARS,
                                            )
                                break
                        if resolver_hit:
                            break

                if resolver_hit:
                    hits += 1
                else:
                    misses += 1

            for key in memory_keys:
                record = self.memory.recall(scope, ("key", key))
                if record is None:
                    misses += 1
                    continue
                hits += 1
                materialized = _materialize(record.payload)
                retrieved_chars += len(" ".join(materialized.split()).strip())
                _append_unique(retrieved, materialized)

            memory_ms = (perf_counter() - start) * 1000.0
            context = tuple(retrieved)

        llm_start = perf_counter()
        response = self.adapter.generate(message=message, context=context)
        llm_ms = (perf_counter() - llm_start) * 1000.0

        sent_text = "\n".join(context)
        provider_input = response.usage.input_tokens
        provider_output = response.usage.output_tokens
        metrics = ChatMetrics(
            mode=mode,
            memory_hits=hits,
            memory_misses=misses,
            retrieved_context_chars=retrieved_chars,
            context_sent_chars=len(sent_text),
            input_tokens=provider_input if provider_input is not None else estimate_tokens(sent_text + message),
            output_tokens=provider_output if provider_output is not None else estimate_tokens(response.text),
            memory_latency_ms=memory_ms,
            llm_latency_ms=llm_ms,
            external_calls=1,
            estimated_cost_usd=response.usage.estimated_cost_usd,
            provider=response.provider,
            model=response.model,
        )
        return ChatResult(text=response.text, context=context, metrics=metrics)


def token_reduction(*, baseline_tokens: int, memoria_tokens: int) -> float | None:
    if baseline_tokens <= 0:
        return None
    return 1.0 - (memoria_tokens / baseline_tokens)
