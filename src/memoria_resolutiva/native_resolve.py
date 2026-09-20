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
            # Direct recall is deliberately first. If it cannot collapse the
            # intention, activate the persisted relation graph from query
            # concepts and let the nearest bounded structural attractor expose
            # candidate evidence. No embeddings/LLM are involved here.
            if str(getattr(result, "status", "") or "").upper() != "HIT":
                activate = getattr(self.resolver, "activate_relations", None)
                if callable(activate):
                    words = [w.strip(" ?!.,:;").casefold() for w in message.split()]
                    stop = {"qual", "quais", "que", "é", "e", "era", "foi", "a", "o", "as", "os", "da", "do", "de", "minha", "meu"}
                    concepts = [w for w in words if len(w) > 2 and w not in stop]
                    for concept in concepts[:4]:
                        activated = activate(concept=concept, session_id=namespace)
                        if str(activated.get("status", "")).upper() == "HIT":
                            class _Activated: pass
                            candidate = _Activated()
                            candidate.status = "HIT"
                            candidate.confidence = activated.get("confidence", 0.0)
                            candidate.selected_context = activated.get("selected_context", "")
                            result = candidate
                            break
            status = str(getattr(result, "status", "") or "").upper()
            try:
                confidence = max(0.0, min(1.0, float(getattr(result, "confidence", 0.0) or 0.0)))
            except (TypeError, ValueError):
                confidence = 0.0
            selected = " ".join(str(getattr(result, "selected_context", "") or "").split()).strip()
            if status == "HIT" and confidence >= self.min_confidence and selected:
                return NativeResolveResult("RESOLVED", selected, confidence, (selected,))
        return NativeResolveResult("UNRESOLVED", None, 0.0, ())
