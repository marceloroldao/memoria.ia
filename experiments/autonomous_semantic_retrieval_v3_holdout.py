from __future__ import annotations

import json

from memoria_resolutiva.product_identity import MemoryScope, OrganizationIdentity
from memoria_resolutiva.product_service import EnterpriseMemoryService

from autonomous_semantic_retrieval_v1 import CONCEPTS
from autonomous_semantic_retrieval_v2 import resolve

HOLDOUT = [
    ("qual a diferença de potencial da alimentação principal?", "source.voltage", "novel-synonym"),
    ("em quantos V trabalha a fonte?", "source.voltage", "symbolic"),
    ("qual a voltagem nominal da fonte?", "source.voltage", "mixed"),
    ("qual a amperagem máxima da alimentação?", "source.current", "novel-synonym"),
    ("quantos A a fonte entrega?", "source.current", "symbolic"),
    ("me diga o limite em amperes da fonte", "source.current", "mixed"),
    ("qual pacote de internet pertence ao assinante?", "customer.plan", "novel-synonym"),
    ("qual banda foi contratada pelo cliente?", "customer.plan", "novel-synonym"),
    ("o assinante tem quantos Mbps contratados?", "customer.plan", "mixed"),
    ("o débito de agosto foi liquidado?", "invoice.status", "novel-synonym"),
    ("como ficou a situação da conta de agosto?", "invoice.status", "novel-synonym"),
    ("a fatura referente a agosto já está quitada?", "invoice.status", "mixed"),
    ("o serviço ficou indisponível no prédio inteiro", "network.outage", "novel-synonym"),
    ("houve interrupção geral de conectividade no edifício", "network.outage", "novel-synonym"),
    ("todos os moradores perderam acesso à rede", "network.outage", "implicit"),
    ("o tempo de resposta da conexão ficou elevado", "network.latency", "novel-synonym"),
    ("a navegação continua disponível porém com atraso", "network.latency", "novel-synonym"),
    ("não houve queda; apenas o ping ficou maior", "network.latency", "contrast"),
    ("o enlace óptico foi seccionado", "fiber.break", "novel-synonym"),
    ("alguém partiu fisicamente o cabo de fibra", "fiber.break", "novel-synonym"),
    ("a fibra sofreu corte mecânico", "fiber.break", "mixed"),
    ("o gateway principal está avariado", "router.failure", "novel-synonym"),
    ("o equipamento que encaminha pacotes apresentou pane", "router.failure", "novel-synonym"),
    ("o roteador principal deixou de operar", "router.failure", "mixed"),
    ("qual a potência da fonte?", None, "near-domain-unknown"),
    ("qual a temperatura do roteador?", None, "near-domain-unknown"),
    ("qual o comprimento da fibra?", None, "near-domain-unknown"),
    ("qual o endereço do cliente?", None, "near-domain-unknown"),
    ("qual o valor total da fatura?", None, "near-domain-unknown"),
    ("a rede está funcionando normalmente", None, "normal-state"),
    ("a fibra está intacta", None, "normal-state"),
    ("o roteador está ligado e saudável", None, "normal-state"),
]


def main() -> None:
    org = OrganizationIdentity("autonomous-retrieval-v3-holdout")
    scope = MemoryScope(org.organization_id)
    memory = EnterpriseMemoryService(org)
    for concept_id, spec in CONCEPTS.items():
        memory.remember(scope, f"memory-{concept_id}", spec["payload"], ("key", concept_id), provenance="autonomous-semantic-retrieval-v3-holdout")

    rows = []
    correct = known_total = known_correct = unknown_total = unknown_correct = false_positive = wrong_memory = 0
    for query, expected, category in HOLDOUT:
        predicted, score, margin, diagnostics = resolve(query)
        record = memory.recall(scope, ("key", predicted)) if predicted else None
        ok = predicted == expected and (expected is None or record is not None)
        correct += int(ok)
        if expected is None:
            unknown_total += 1
            unknown_correct += int(predicted is None)
            false_positive += int(predicted is not None)
        else:
            known_total += 1
            known_correct += int(predicted == expected and record is not None)
            wrong_memory += int(predicted is not None and predicted != expected)
        rows.append({"query": query, "category": category, "expected": expected, "predicted": predicted, "score": score, "margin": margin, "correct": ok, "retrieved_payload": None if record is None else record.payload})

    report = {
        "benchmark": "memoria.ia-autonomous-semantic-retrieval-v3-holdout",
        "queries": len(HOLDOUT),
        "known_queries": known_total,
        "unknown_queries": unknown_total,
        "accuracy": correct / len(HOLDOUT),
        "known_recall": known_correct / known_total,
        "unknown_rejection": unknown_correct / unknown_total,
        "false_positive_rate": false_positive / unknown_total,
        "wrong_memory_rate_known": wrong_memory / known_total,
        "neural_network": False,
        "embeddings": False,
        "llm": False,
        "memory_key_supplied_by_query": False,
        "fresh_holdout": True,
        "rows": rows,
        "limitations": [
            "This holdout is new relative to the v2 schema but is still a small controlled domain benchmark.",
            "The ontology/schema is hand-authored and not induced automatically.",
            "Concept identifiers still map directly to memory keys.",
        ],
    }
    print(json.dumps(report, indent=2, ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()
