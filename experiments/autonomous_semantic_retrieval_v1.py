from __future__ import annotations

import json
from dataclasses import asdict

from memoria_resolutiva.product_identity import MemoryScope, OrganizationIdentity
from memoria_resolutiva.product_service import EnterpriseMemoryService
from memoria_resolutiva.relation_aware_v96 import RelationAwareTrajectoryRouterV96

CONCEPTS = {
    "source.voltage": {"payload": "A fonte principal trabalha com 24 V.", "examples": ["a fonte principal trabalha com 24 volts", "a tensão da fonte é 24 v", "alimentação principal em vinte e quatro volts"]},
    "source.current": {"payload": "A fonte principal suporta 10 A.", "examples": ["a corrente da fonte é 10 amperes", "a fonte suporta dez amperes", "corrente máxima da alimentação em 10 a"]},
    "customer.plan": {"payload": "O cliente está no plano fibra 600 Mbps.", "examples": ["o cliente usa plano de 600 mega", "assinatura fibra de 600 mbps", "velocidade contratada pelo cliente é 600 mega"]},
    "invoice.status": {"payload": "A fatura de agosto está paga.", "examples": ["a fatura de agosto foi paga", "pagamento da conta de agosto confirmado", "cobrança de agosto quitada"]},
    "network.outage": {"payload": "Há uma indisponibilidade total da rede no prédio.", "examples": ["a internet caiu para todo o prédio", "ninguém no prédio consegue acessar a rede", "indisponibilidade total de internet no edifício"]},
    "network.latency": {"payload": "A rede está conectada, porém com latência alta.", "examples": ["a internet funciona mas o ping está alto", "rede conectada com latência elevada", "conexão ativa porém muito lenta para responder"]},
    "fiber.break": {"payload": "A fibra óptica foi rompida por uma escavadeira.", "examples": ["a escavadeira rompeu a fibra", "o cabo óptico foi cortado", "houve rompimento físico da fibra"]},
    "router.failure": {"payload": "O roteador principal está com falha de hardware.", "examples": ["o roteador principal apresentou defeito", "falha de hardware no roteador", "equipamento de roteamento parou de funcionar"]},
}

COUNTEREXAMPLES = {
    "network.outage": ["a internet não caiu mas o ping está alto", "somente um computador está sem acesso"],
    "network.latency": ["ninguém consegue acessar a internet porque a rede caiu"],
    "fiber.break": ["a fibra não rompeu e o sinal óptico está normal"],
    "router.failure": ["o roteador está funcionando normalmente"],
}

QUERIES = [
    ("quanto é a tensão da fonte principal?", "source.voltage", "paraphrase"),
    ("qual voltagem estamos usando na alimentação?", "source.voltage", "synonym"),
    ("me lembra os volts da fonte", "source.voltage", "short"),
    ("qual corrente máxima a fonte aguenta?", "source.current", "paraphrase"),
    ("quantos amperes suporta a alimentação?", "source.current", "synonym"),
    ("qual é o limite de corrente da fonte?", "source.current", "relation"),
    ("qual velocidade o cliente contratou?", "customer.plan", "paraphrase"),
    ("qual é o plano de internet do assinante?", "customer.plan", "synonym"),
    ("quantos mega tem a assinatura?", "customer.plan", "short"),
    ("a conta de agosto já foi quitada?", "invoice.status", "paraphrase"),
    ("qual o estado do pagamento de agosto?", "invoice.status", "relation"),
    ("a cobrança de agosto está paga?", "invoice.status", "direct"),
    ("todo mundo no prédio ficou sem internet", "network.outage", "paraphrase"),
    ("houve queda completa da rede no edifício", "network.outage", "synonym"),
    ("ninguém consegue navegar no prédio", "network.outage", "implicit"),
    ("a internet funciona mas está demorando para responder", "network.latency", "paraphrase"),
    ("o ping subiu embora a conexão continue ativa", "network.latency", "relation"),
    ("a rede não caiu, só está com muita latência", "network.latency", "negation"),
    ("uma máquina cortou o cabo de fibra", "fiber.break", "paraphrase"),
    ("houve rompimento do cabo óptico", "fiber.break", "synonym"),
    ("a escavadeira danificou fisicamente a fibra", "fiber.break", "relation"),
    ("o equipamento principal de roteamento deu defeito", "router.failure", "paraphrase"),
    ("o roteador parou por falha de hardware", "router.failure", "direct"),
    ("o aparelho que roteia a rede deixou de funcionar", "router.failure", "implicit"),
    ("qual é a cor do carro?", None, "unknown"),
    ("qual a temperatura da sala?", None, "unknown"),
    ("a fibra não rompeu e está tudo normal", None, "negated-unknown"),
    ("o roteador funciona normalmente", None, "negated-unknown"),
    ("a internet não caiu mas o ping aumentou", "network.latency", "contrast"),
    ("somente um notebook perdeu acesso", None, "near-miss"),
]


def main() -> None:
    org = OrganizationIdentity("autonomous-retrieval-v1")
    scope = MemoryScope(org.organization_id)
    memory = EnterpriseMemoryService(org)
    router = RelationAwareTrajectoryRouterV96(threshold=0.08, min_margin=0.0, negative_threshold=0.20, min_contrast_margin=0.04, negation_scope=3)

    for concept_id, spec in CONCEPTS.items():
        memory.remember(scope, f"memory-{concept_id}", spec["payload"], ("key", concept_id), provenance="autonomous-semantic-retrieval-v1")
        router.observe_concept(concept_id, spec["examples"])
    for concept_id, examples in COUNTEREXAMPLES.items():
        for example in examples:
            router.observe_counterexample(concept_id, example)

    rows = []
    correct = known_total = known_correct = unknown_total = unknown_correct = false_positive = wrong_memory = 0
    for query, expected, category in QUERIES:
        decision = router.resolve(query)
        predicted = decision.concept_id
        record = memory.recall(scope, ("key", predicted)) if predicted is not None else None
        is_correct = predicted == expected and (expected is None or record is not None)
        correct += int(is_correct)
        if expected is None:
            unknown_total += 1; unknown_correct += int(predicted is None); false_positive += int(predicted is not None)
        else:
            known_total += 1; known_correct += int(predicted == expected and record is not None); wrong_memory += int(predicted is not None and predicted != expected)
        rows.append({"query": query, "category": category, "expected": expected, "predicted": predicted, "retrieved_payload": None if record is None else record.payload, "correct": is_correct, "decision": asdict(decision)})

    report = {
        "benchmark": "memoria.ia-autonomous-semantic-retrieval-v1",
        "neural_network": False,
        "embeddings": False,
        "llm": False,
        "memory_key_supplied_by_query": False,
        "queries": len(QUERIES),
        "concepts": len(CONCEPTS),
        "accuracy": correct / len(QUERIES),
        "known_recall": known_correct / known_total,
        "unknown_rejection": unknown_correct / unknown_total,
        "false_positive_rate": false_positive / unknown_total,
        "wrong_memory_rate_known": wrong_memory / known_total,
        "rows": rows,
        "limitations": [
            "Concept profiles are learned from labeled examples before evaluation.",
            "The concept identifier is deliberately identical to the logical memory key; this tests semantic route discovery, not automatic schema induction.",
            "This is a controlled benchmark, not arbitrary open-domain language understanding."
        ],
    }
    print(json.dumps(report, indent=2, ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()
