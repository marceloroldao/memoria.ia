from __future__ import annotations

from dataclasses import asdict, dataclass
import json
from time import perf_counter
from typing import Iterable, Literal, Protocol, Sequence

from .llm_adapter import LLMAdapter, estimate_tokens
from .product_identity import MemoryScope
from .product_service import EnterpriseMemoryService

ChatMode = Literal["baseline", "memoria"]
MIN_COMPACT_RELATION_CONFIDENCE = 0.90


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


def _minimal_factual_context(resolved: object, selected: str) -> str:
    """Compact only a single strong, unambiguous factual relation.

    Temporal responses, multiple memories/provenance rows, weak relations and
    malformed structured rows keep the resolver's original selected context.
    This deliberately optimizes the LLM boundary without changing memory recall.
    """
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
    """Stable semantic namespace shared by conversations of the same profile.

    Session memory remains isolated in scope.agent_id. The profile namespace is
    intentionally derived without agent_id so a new chat can recover facts that
    the same application/user promoted from an earlier conversation.
    """
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
                # Resolve from the narrowest namespace first. If the current
                # session does not contain enough evidence, widen to the stable
                # profile namespace shared by this application/user.
                namespaces: list[str | None] = []
                if scope.agent_id:
                    namespaces.append(scope.agent_id)
                profile = profile_namespace(scope)
                if profile and profile not in namespaces:
                    namespaces.append(profile)
                if not namespaces:
                    namespaces.append(None)

                resolver_hit = False
                for namespace in namespaces:
                    resolved = self.conversation_resolver.resolve(
                        query=message,
                        session_id=namespace,
                    )
                    if str(getattr(resolved, "status", "")) != "HIT":
                        continue
                    selected = str(getattr(resolved, "selected_context", "") or "")
                    normalized_selected = " ".join(selected.split()).strip()
                    if normalized_selected:
                        resolver_hit = True
                        retrieved_chars += len(normalized_selected)
                        _append_unique(retrieved, _minimal_factual_context(resolved, normalized_selected))
                        # Session evidence has priority. A profile lookup is only
                        # needed when the current session misses.
                        break
                if resolver_hit:
                    hits += 1
                else:
                    misses += 1

            # Explicit keys remain supported for applications that already know
            # which structured memories they want to request.
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
