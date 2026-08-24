from __future__ import annotations

from dataclasses import asdict, dataclass
import json
from pathlib import Path
from time import perf_counter
from typing import Iterable, Literal, Sequence

from .autonomous_memory_v097 import AutonomousTextMemoryV097
from .llm_adapter import LLMAdapter, estimate_tokens
from .product_identity import MemoryScope
from .product_service import EnterpriseMemoryService

ChatMode = Literal["baseline", "memoria"]


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
    autonomous_candidates: int = 0
    autonomous_selected: int = 0
    autonomous_decision: str | None = None
    autonomous_best_score: float = 0.0
    autonomous_memories_created: int = 0
    autonomous_abstentions: int = 0

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


def _should_observe(message: str) -> bool:
    clean = message.strip()
    if not clean or clean.endswith('?'):
        return False
    first = clean.casefold().split(maxsplit=1)[0] if clean else ''
    return first not in {'qual','quais','quem','como','onde','quando','porque','porquê','what','which','who','how','where','when','why'}


class ProductChatService:
    def __init__(
        self,
        memory: EnterpriseMemoryService,
        adapter: LLMAdapter,
        *,
        autonomous_memory: AutonomousTextMemoryV097 | None = None,
        autonomous_snapshot: str | Path | None = None,
    ):
        self.memory = memory
        self.adapter = adapter
        self.autonomous_memory = autonomous_memory
        self.autonomous_snapshot = Path(autonomous_snapshot) if autonomous_snapshot is not None else None

    def _persist_autonomous(self) -> None:
        if self.autonomous_memory is not None and self.autonomous_snapshot is not None:
            self.autonomous_memory.save(self.autonomous_snapshot)

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
        auto_candidates = auto_selected = auto_created = auto_abstentions = 0
        auto_decision: str | None = None
        auto_best = 0.0
        explicit_keys = tuple(memory_keys)

        if mode == "baseline":
            context = tuple(str(item) for item in baseline_context)
        else:
            start = perf_counter()
            for key in explicit_keys:
                record = self.memory.recall(scope, ("key", key))
                if record is None:
                    misses += 1
                    continue
                hits += 1
                retrieved.append(_materialize(record.payload))

            # Autonomous routing is used only when the caller did not supply
            # explicit keys. This keeps the validated exact-key contract intact.
            if not explicit_keys and self.autonomous_memory is not None:
                query = self.autonomous_memory.query(message, top_k=3)
                auto_candidates = query.metrics.candidate_count
                auto_selected = query.metrics.selected_count
                auto_decision = query.metrics.decision
                auto_best = query.metrics.best_score
                auto_abstentions = query.metrics.abstentions
                if query.hits:
                    hits += len(query.hits)
                    retrieved.extend(hit.text for hit in query.hits)
                elif query.abstained:
                    misses += 1

            memory_ms = (perf_counter() - start) * 1000.0
            context = tuple(retrieved)

        llm_start = perf_counter()
        response = self.adapter.generate(message=message, context=context)
        llm_ms = (perf_counter() - llm_start) * 1000.0

        # Observe user statements after answering so the current message is not
        # retrieved as its own context. Questions are not memorized by default.
        if mode == 'memoria' and not explicit_keys and self.autonomous_memory is not None and _should_observe(message):
            decision = self.autonomous_memory.observe(message, provenance='product-chat:user')
            auto_created += decision.metrics.memories_created
            self._persist_autonomous()
            if auto_decision is None or auto_decision == 'unresolved':
                auto_decision = decision.decision

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
            autonomous_candidates=auto_candidates,
            autonomous_selected=auto_selected,
            autonomous_decision=auto_decision,
            autonomous_best_score=auto_best,
            autonomous_memories_created=auto_created,
            autonomous_abstentions=auto_abstentions,
        )
        return ChatResult(text=response.text, context=context, metrics=metrics)


def token_reduction(*, baseline_tokens: int, memoria_tokens: int) -> float | None:
    if baseline_tokens <= 0:
        return None
    return 1.0 - (memoria_tokens / baseline_tokens)
