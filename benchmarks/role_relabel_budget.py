from __future__ import annotations

import json

from memoria_resolutiva.role_structural_router_v96 import RoleStructuralRouterV96


OBSERVATIONS = [
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

VALID_CONTEXT = [
    ("depositante remete quantia para agencia", "customer_to_bank"),
    ("agencia remete quantia para depositante", "bank_to_customer"),
]

ADVERSARIAL_CONTEXT = [
    "depositante quantia remete agencia",
    "agencia quantia remete depositante",
    "quantia remete depositante agencia",
]


def build_router(budget: int) -> RoleStructuralRouterV96:
    router = RoleStructuralRouterV96(
        role_threshold=0.30,
        role_min_margin=0.02,
        structural_threshold=0.45,
        structural_min_margin=0.08,
        relation_window=5,
        max_context_relabels=budget,
    )
    router.observe(OBSERVATIONS)
    router.register_role("customer", ["cliente", "comprador", "usuario"])
    router.register_role("transfer", ["paga", "envia", "transfere", "remete"])
    router.register_role("money", ["dinheiro", "pagamento", "valor"])
    router.register_role("bank", ["banco", "instituicao"])
    router.register_intent_pattern("customer_to_bank", ["customer", "transfer", "money", "bank"])
    router.register_intent_pattern("bank_to_customer", ["bank", "transfer", "money", "customer"])
    return router


def evaluate(budget: int) -> dict[str, object]:
    router = build_router(budget)
    valid_rows = []
    valid_correct = 0
    for text, expected in VALID_CONTEXT:
        result = router.resolve_text(text)
        ok = result.concept_id == expected
        valid_correct += int(ok)
        valid_rows.append(
            {
                "text": text,
                "expected": expected,
                "predicted": result.concept_id,
                "canonical_roles": list(result.canonical_roles),
                "correct": ok,
            }
        )

    adversarial_rows = []
    false_positives = 0
    for text in ADVERSARIAL_CONTEXT:
        result = router.resolve_text(text)
        false_positive = result.concept_id is not None
        false_positives += int(false_positive)
        adversarial_rows.append(
            {
                "text": text,
                "predicted": result.concept_id,
                "canonical_roles": list(result.canonical_roles),
                "false_positive": false_positive,
            }
        )

    return {
        "budget": budget,
        "valid_recall": valid_correct / len(VALID_CONTEXT),
        "adversarial_false_positive_rate": false_positives / len(ADVERSARIAL_CONTEXT),
        "valid": valid_rows,
        "adversarial": adversarial_rows,
    }


def main() -> None:
    rows = [evaluate(budget) for budget in (0, 1, 2, 3)]
    safe = [
        row["budget"]
        for row in rows
        if row["valid_recall"] == 1.0
        and row["adversarial_false_positive_rate"] == 0.0
    ]
    output = {
        "budgets": rows,
        "safe_budgets": safe,
        "recommended_budget": min(safe) if safe else None,
    }
    print(json.dumps(output, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
