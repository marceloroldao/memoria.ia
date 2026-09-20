from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Protocol

from .product_identity import MemoryScope


class ConversationResolver(Protocol):
    def resolve(self, *, query: str, session_id: str | None = None): ...


@dataclass(frozen=True, slots=True)
class NativeResolveResult:
    status: str
    text: str | None
    confidence: float
    context: tuple[str, ...]
    external_calls: int = 0

    def as_dict(self) -> dict:
        return asdict(self)


class NativeResolveService:
    """Resolve a user intention directly from persisted cognitive state.

    This path deliberately never calls an LLM. Ambiguous/weak evidence remains
    UNRESOLVED rather than being converted into generated prose.
    """

    def __init__(self, resolver: ConversationResolver, *, min_confidence: float = 0.75):
        self.resolver = resolver
        self.min_confidence = float(min_confidence)

    def resolve(self, *, scope: MemoryScope, message: str) -> NativeResolveResult:
        namespaces: list[str | None] = []
        if scope.agent_id:
            namespaces.append(scope.agent_id)
        profile = f"profile:{scope.application_id or 'default'}:{scope.user_id}" if scope.user_id else (
            f"profile:{scope.application_id}" if scope.application_id else None
        )
        if profile and profile not in namespaces:
            namespaces.append(profile)
        if not namespaces:
            namespaces.append(None)

        for namespace in namespaces:
            result = self.resolver.resolve(query=message, session_id=namespace)
            status = str(getattr(result, "status", "") or "").upper()
            try:
                confidence = max(0.0, min(1.0, float(getattr(result, "confidence", 0.0) or 0.0)))
            except (TypeError, ValueError):
                confidence = 0.0
            selected = " ".join(str(getattr(result, "selected_context", "") or "").split()).strip()
            if status == "HIT" and confidence >= self.min_confidence and selected:
                return NativeResolveResult("RESOLVED", selected, confidence, (selected,))
        return NativeResolveResult("UNRESOLVED", None, 0.0, ())
