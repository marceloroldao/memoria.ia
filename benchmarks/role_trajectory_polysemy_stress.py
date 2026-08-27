from __future__ import annotations

import json

from memoria_resolutiva.trajectory_policy_gate_experimental import ExperimentalTrajectoryPolicyGate


def build_gate():
    gate = ExperimentalTrajectoryPolicyGate(use_native=False)
    gate.observe([
        # Family A: canal is a source-like node.
        "canal transmite sinal usuario",
        "emissora envia programa publico",
        "estacao transmite alerta cliente",
        "canal envia programa cliente",
        # Family B: canal is a destination-like node.
        "roteador envia pacote canal",
        "sensor transmite dado servidor",
        "terminal envia quadro enlace",
        "roteador transmite dado canal",
    ])
    gate.register_role("source", ["emissora", "estacao", "roteador", "sensor", "terminal"])
    gate.register_role("action", ["transmite", "envia"])
    gate.register_role("payload", ["sinal", "programa", "alerta", "pacote", "dado", "quadro"])
    gate.register_role("destination", ["usuario", "publico", "cliente", "servidor", "enlace"])
    gate.register_pattern(("source", "action", "payload", "destination"))
    assert gate.calibrate()
    return gate


def classify(gate, text, expected):
    result = gate.resolve(text)
    return {
        "text": text,
        "expected": expected,
        "decision": result.decision,
        "coverage": result.coverage,
        "threshold": result.threshold,
        "reason": result.reason,
        "correct": result.decision == expected,
    }


def main():
    gate = build_gate()
    rows = []

    # Both learned senses of the same token are legitimate.
    rows += [
        classify(gate, "canal transmite sinal usuario", "accept"),
        classify(gate, "roteador envia pacote canal", "accept"),
        classify(gate, "canal envia programa cliente", "accept"),
        classify(gate, "roteador transmite dado canal", "accept"),
    ]

    # Structurally malformed permutations made only from supported vocabulary.
    # usuario is an exact destination anchor, so placing it at source must reject
    # even though canal itself is polysemous.
    for text in [
        "canal sinal transmite usuario",
        "roteador pacote envia canal",
        "usuario transmite sinal canal",
        "canal envia roteador pacote",
    ]:
        rows.append(classify(gate, text, "reject"))

    # Novel recombinations are intentionally expected to generalize when every
    # token can satisfy the registered role topology. They must not be rejected
    # merely because the exact lexical combination was absent from observations.
    for text in [
        "canal transmite pacote servidor",
        "canal envia dado enlace",
        "roteador transmite sinal canal",
        "terminal envia programa canal",
        "emissora envia pacote canal",
        "sensor transmite programa usuario",
    ]:
        rows.append(classify(gate, text, "accept"))

    # Absolute open set remains epistemically unknown, not structurally false.
    rows.append(classify(gate, "canal transmite misterio usuario", "fail_closed"))

    output = {
        "experiment": "shared vocabulary / polysemy stress",
        "ambiguous_token": "canal",
        "principle": "role topology constrains ambiguous vocabulary while preserving compositional generalization",
        "rows": rows,
        "summary": {
            "total": len(rows),
            "correct": sum(row["correct"] for row in rows),
            "accuracy": sum(row["correct"] for row in rows) / len(rows),
            "false_accepts": [row for row in rows if row["expected"] == "reject" and row["decision"] == "accept"],
            "false_rejects": [row for row in rows if row["expected"] == "accept" and row["decision"] != "accept"],
            "unexpected_fail_closed": [row for row in rows if row["expected"] != "fail_closed" and row["decision"] == "fail_closed"],
        },
    }
    print(json.dumps(output, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
