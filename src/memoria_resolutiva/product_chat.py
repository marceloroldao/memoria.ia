from __future__ import annotations

from dataclasses import asdict, dataclass
import json
from time import perf_counter
from typing import Iterable, Literal, Protocol, Sequence

from .llm_adapter import LLMAdapter, estimate_tokens
from .product_identity import MemoryScope
from .product_service import EnterpriseMemoryService

ChatMode = Literal["baseline", "memoria"]


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
                    if selected.strip():
                        resolver_hit = True
                        _append_unique(retrieved, selected)
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
                _append_unique(retrieved, _materialize(record.payload))

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
            retrieved_context_chars=sum(len(item) for item in retrieved),
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
