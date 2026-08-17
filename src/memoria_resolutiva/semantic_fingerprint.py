from __future__ import annotations

from dataclasses import dataclass
from re import findall

from .dependency_inference import lexical_jaccard


CANONICAL = {
    "cobranca": "fee", "cobrança": "fee", "taxa": "fee", "tarifa": "fee", "encargo": "fee",
    "fibra": "fiber", "optica": "fiber", "óptica": "fiber", "conexao": "fiber", "conexão": "fiber",
    "conexoes": "fiber", "conexões": "fiber", "link": "fiber", "enlace": "fiber", "enlaces": "fiber",
    "pagar": "pay", "paga": "pay", "pagara": "pay", "pagará": "pay", "pagarao": "pay", "pagarão": "pay",
    "pagamento": "pay", "custo": "pay", "custara": "pay", "custará": "pay",
    "provedor": "provider", "provedores": "provider", "operadora": "provider", "operadoras": "provider",
    "empresa": "provider", "empresas": "provider",
    "novo": "new", "nova": "new", "adicional": "new", "extra": "new",
    "mensal": "monthly", "mes": "monthly", "mês": "monthly",
}

KEY_CONCEPTS = {"fee", "fiber", "pay", "provider", "new", "monthly"}
ACTION_CONCEPTS = {"fee", "pay"}


@dataclass(frozen=True, slots=True)
class SemanticFingerprint:
    concepts: frozenset[str]
    actions: frozenset[str]
    numbers: frozenset[str]


def fingerprint(text: str) -> SemanticFingerprint:
    tokens = findall(r"\w+", text.lower())
    concepts = {
        canonical
        for token in tokens
        if (canonical := CANONICAL.get(token)) in KEY_CONCEPTS
    }
    actions = concepts & ACTION_CONCEPTS
    numbers = {
        value.replace(",", ".")
        for value in findall(r"\b\d+(?:[.,]\d+)?%?\b", text.lower())
    }
    return SemanticFingerprint(frozenset(concepts), frozenset(actions), frozenset(numbers))


def _jaccard(a: frozenset[str], b: frozenset[str]) -> float:
    union = a | b
    if not union:
        return 0.0
    return len(a & b) / len(union)


def structural_similarity(a: str, b: str) -> float:
    """Rule-based event fingerprint similarity for controlled provenance tests.

    This is intentionally non-neural and domain-limited. It tests whether a compact
    structural representation can recover some paraphrases missed by raw lexical
    overlap; it is not claimed to be general semantic understanding.
    """
    fa, fb = fingerprint(a), fingerprint(b)
    return (
        0.50 * _jaccard(fa.concepts, fb.concepts)
        + 0.35 * _jaccard(fa.actions, fb.actions)
        + 0.15 * _jaccard(fa.numbers, fb.numbers)
    )


def hybrid_similarity(a: str, b: str, lexical_weight: float = 0.25) -> float:
    if not 0.0 <= lexical_weight <= 1.0:
        raise ValueError("lexical_weight must be in [0, 1]")
    structural_weight = 1.0 - lexical_weight
    return lexical_weight * lexical_jaccard(a, b) + structural_weight * structural_similarity(a, b)
