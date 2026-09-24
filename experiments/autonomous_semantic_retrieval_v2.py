from __future__ import annotations

import json
import re
import unicodedata

from memoria_resolutiva.product_identity import MemoryScope, OrganizationIdentity
from memoria_resolutiva.product_service import EnterpriseMemoryService

from autonomous_semantic_retrieval_v1 import CONCEPTS, QUERIES


TOKEN_RE = re.compile(r"[a-z0-9]+", re.I)


def norm(text: str) -> str:
    text = unicodedata.normalize("NFKD", text.lower())
    text = "".join(ch for ch in text if not unicodedata.combining(ch))
    return " ".join(TOKEN_RE.findall(text))


def tokens(text: str) -> set[str]:
    return set(norm(text).split())


SCHEMA = {
    "source.voltage": {
        "entity": {"fonte", "alimentacao"},
        "intent": {"tensao", "voltagem", "volt", "volts"},
        "context": {"principal"},
    },
    "source.current": {
        "entity": {"fonte", "alimentacao"},
        "intent": {"corrente", "ampere", "amperes"},
        "context": {"maxima", "maximo", "limite", "suporta", "aguenta"},
    },
    "customer.plan": {
        "entity": {"cliente", "assinante"},
        "intent": {"plano", "assinatura", "contratou", "contratada", "velocidade", "mega", "mbps"},
        "context": {"internet", "fibra"},
    },
    "invoice.status": {
        "entity": {"fatura", "conta", "cobranca"},
        "intent": {"paga", "pago", "quitada", "quitado", "pagamento", "estado", "status"},
        "context": {"agosto"},
    },
    "network.outage": {
        "entity": {"internet", "rede", "predio", "edificio"},
        "intent": {"caiu", "queda", "indisponibilidade", "ninguem", "navegar", "acessar"},
        "context": {"completa", "total", "todo", "mundo", "predio", "edificio"},
        "phrases": {"sem internet", "todo mundo", "ninguem consegue"},
    },
    "network.latency": {
        "entity": {"internet", "rede", "conexao"},
        "intent": {"ping", "latencia", "lenta", "lento", "demorando", "responder", "atraso"},
        "context": {"funciona", "ativa", "ativo", "conectada", "conectado", "continue"},
    },
    "fiber.break": {
        "entity": {"fibra", "cabo", "optico", "optica"},
        "intent": {"rompeu", "rompimento", "cortou", "cortado", "danificou", "escavadeira", "maquina"},
        "context": {"fisicamente", "fisico"},
    },
    "router.failure": {
        "entity": {"roteador", "roteamento", "aparelho", "equipamento", "roteia"},
        "intent": {"falha", "defeito", "parou", "deixou", "hardware"},
        "context": {"principal", "funcionar"},
    },
}

NEGATED_PATTERNS = {
    "network.outage": ("nao caiu", "nao houve queda", "rede nao caiu", "internet nao caiu"),
    "fiber.break": ("nao rompeu", "nao foi rompida", "fibra intacta"),
    "router.failure": ("funciona normalmente", "funcionando normalmente", "sem falha", "sem defeito"),
}


def structured_score(concept_id: str, query: str) -> tuple[float, dict]:
    qn = norm(query)
    qt = tokens(query)
    spec = SCHEMA[concept_id]
    entity_hits = sorted(qt & spec.get("entity", set()))
    intent_hits = sorted(qt & spec.get("intent", set()))
    context_hits = sorted(qt & spec.get("context", set()))
    phrase_hits = sorted(p for p in spec.get("phrases", set()) if p in qn)

    score = 0.0
    score += min(2, len(entity_hits)) * 1.5
    score += min(2, len(intent_hits)) * 3.0
    score += min(2, len(context_hits)) * 0.75
    score += len(phrase_hits) * 2.5

    negated = [p for p in NEGATED_PATTERNS.get(concept_id, ()) if p in qn]
    if negated:
        score -= 8.0

    # Positive-state evidence should prevent normal operation from looking like failure/outage.
    if concept_id == "network.latency" and ({"ping", "latencia", "demorando", "responder", "lenta", "lento"} & qt):
        score += 1.5
    if concept_id == "network.outage" and "sem internet" in qn:
        score += 2.0
    if concept_id == "router.failure" and "normalmente" in qt and not intent_hits:
        score -= 6.0

    diagnostics = {
        "entity_hits": entity_hits,
        "intent_hits": intent_hits,
        "context_hits": context_hits,
        "phrase_hits": phrase_hits,
        "negated_patterns": negated,
    }
    return score, diagnostics


def resolve(query: str) -> tuple[str | None, float, float, dict]:
    ranked = []
    diagnostics = {}
    for concept_id in SCHEMA:
        score, diag = structured_score(concept_id, query)
        diagnostics[concept_id] = diag
        ranked.append((concept_id, score))
    ranked.sort(key=lambda item: (-item[1], item[0]))
    best_id, best_score = ranked[0]
    second_score = ranked[1][1]
    margin = best_score - second_score

    # Require structured evidence and separation from the runner-up.
    if best_score < 3.0 or margin < 1.0:
        return None, best_score, margin, diagnostics
    return best_id, best_score, margin, diagnostics


def main() -> None:
    org = OrganizationIdentity("autonomous-retrieval-v2")
    scope = MemoryScope(org.organization_id)
    memory = EnterpriseMemoryService(org)
    for concept_id, spec in CONCEPTS.items():
        memory.remember(
            scope,
            f"memory-{concept_id}",
            spec["payload"],
            ("key", concept_id),
            provenance="autonomous-semantic-retrieval-v2",
        )

    rows = []
    correct = known_total = known_correct = unknown_total = unknown_correct = false_positive = wrong_memory = 0
    for query, expected, category in QUERIES:
        predicted, score, margin, diagnostics = resolve(query)
        record = memory.recall(scope, ("key", predicted)) if predicted is not None else None
        is_correct = predicted == expected and (expected is None or record is not None)
        correct += int(is_correct)
        if expected is None:
            unknown_total += 1
            unknown_correct += int(predicted is None)
            false_positive += int(predicted is not None)
        else:
            known_total += 1
            known_correct += int(predicted == expected and record is not None)
            wrong_memory += int(predicted is not None and predicted != expected)
        rows.append({
            "query": query,
            "category": category,
            "expected": expected,
            "predicted": predicted,
            "score": score,
            "margin": margin,
            "retrieved_payload": None if record is None else record.payload,
            "correct": is_correct,
            "diagnostics": diagnostics.get(predicted) if predicted else None,
        })

    report = {
        "benchmark": "memoria.ia-autonomous-semantic-retrieval-v2",
        "neural_network": False,
        "embeddings": False,
        "llm": False,
        "memory_key_supplied_by_query": False,
        "structured_schema": True,
        "queries": len(QUERIES),
        "concepts": len(CONCEPTS),
        "accuracy": correct / len(QUERIES),
        "known_recall": known_correct / known_total,
        "unknown_rejection": unknown_correct / unknown_total,
        "false_positive_rate": false_positive / unknown_total,
        "wrong_memory_rate_known": wrong_memory / known_total,
        "rows": rows,
        "limitations": [
            "The structural schema and aliases are hand-authored from the domain ontology, not induced automatically.",
            "The evaluation set is the same controlled set as v1 so this is an ablation/comparison, not a fresh generalization benchmark.",
            "Concept identifiers still map directly to logical memory keys.",
        ],
    }
    print(json.dumps(report, indent=2, ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()
