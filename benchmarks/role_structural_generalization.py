from __future__ import annotations

import json
from time import perf_counter

from memoria_resolutiva.role_structural_router_v96 import RoleStructuralRouterV96


def build_router() -> RoleStructuralRouterV96:
    router = RoleStructuralRouterV96(
        role_threshold=0.30,
        role_min_margin=0.02,
        structural_threshold=0.45,
        structural_min_margin=0.08,
        relation_window=5,
    )
    router.observe(
        [
            "cliente envia pagamento banco",
            "comprador transfere dinheiro banco",
            "usuario remete valor instituicao",
            "depositante envia quantia agencia",
            "cliente transfere quantia agencia",
            "depositante remete pagamento banco",
            "banco envia pagamento cliente",
            "instituicao transfere dinheiro comprador",
            "agencia envia quantia depositante",
            "banco remete valor usuario",
        ]
    )
    router.register_role("customer", ["cliente", "comprador", "usuario"])
    router.register_role("transfer", ["paga", "envia", "transfere", "remete"])
    router.register_role("money", ["dinheiro", "pagamento", "valor"])
    router.register_role("bank", ["banco", "instituicao"])
    router.register_intent_pattern("customer_to_bank", ["customer", "transfer", "money", "bank"])
    router.register_intent_pattern("bank_to_customer", ["bank", "transfer", "money", "customer"])
    return router


def main() -> None:
    router = build_router()
    cases = [
        ("cliente transfere dinheiro para o banco", "customer_to_bank", "registered"),
        ("o banco transfere dinheiro para o cliente", "bank_to_customer", "registered"),
        ("depositante remete quantia para agencia", "customer_to_bank", "context_alias"),
        ("agencia remete quantia para depositante", "bank_to_customer", "context_alias"),
        ("hoje cliente realmente transfere dinheiro com cuidado para o banco", "customer_to_bank", "surface_noise"),
        ("ontem o banco calmamente transfere dinheiro de volta para o cliente", "bank_to_customer", "surface_noise"),
        ("cliente visita banco", None, "wrong_relation"),
        ("cliente consulta saldo banco", None, "wrong_relation"),
        ("cliente dinheiro transfere banco", None, "reordered"),
        ("cliente transfere banco dinheiro", None, "reordered"),
        ("cliente cliente transfere dinheiro banco", None, "role_supersequence"),
        ("cliente transfere dinheiro banco cliente", None, "role_supersequence"),
        ("astronauta observa planeta distante", None, "open_set"),
        ("sensor mede temperatura ambiente", None, "open_set"),
        ("motor gira eixo lentamente", None, "open_set"),
        ("professor explica conceito aluno", None, "open_set"),
    ]

    started = perf_counter()
    rows = []
    correct = 0
    negatives = 0
    false_positives = 0
    positives = 0
    false_negatives = 0
    by_group: dict[str, dict[str, int]] = {}

    for text, expected, group in cases:
        result = router.resolve_text(text)
        predicted = result.concept_id
        ok = predicted == expected
        correct += int(ok)
        bucket = by_group.setdefault(group, {"total": 0, "correct": 0})
        bucket["total"] += 1
        bucket["correct"] += int(ok)
        if expected is None:
            negatives += 1
            false_positives += int(predicted is not None)
        else:
            positives += 1
            false_negatives += int(predicted is None)
        rows.append(
            {
                "text": text,
                "group": group,
                "expected": expected,
                "predicted": predicted,
                "canonical_roles": list(result.canonical_roles),
                "score": result.score,
                "correct": ok,
            }
        )

    elapsed_ms = (perf_counter() - started) * 1000.0
    output = {
        "cases": len(cases),
        "accuracy": correct / len(cases),
        "false_positive_rate": false_positives / negatives if negatives else 0.0,
        "false_negative_rate": false_negatives / positives if positives else 0.0,
        "elapsed_ms": elapsed_ms,
        "avg_ms_per_case": elapsed_ms / len(cases),
        "groups": {
            group: {
                **counts,
                "accuracy": counts["correct"] / counts["total"],
            }
            for group, counts in sorted(by_group.items())
        },
        "results": rows,
    }
    print(json.dumps(output, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
