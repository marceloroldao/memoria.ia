from __future__ import annotations

import json
import random
from copy import deepcopy

from memoria_resolutiva.trajectory_policy_gate_experimental import ExperimentalTrajectoryPolicyGate

BASE_OBSERVATIONS = [
    "fonte transmite sinal destino",
    "origem envia dado alvo",
    "emissor remete pacote receptor",
    "terminal transmite quadro servidor",
]
NOISE = [
    "azul rapido frio pedra",
    "motor gira eixo roda",
    "chuva molha rua cidade",
    "livro fica mesa sala",
]


def build(observations):
    gate = ExperimentalTrajectoryPolicyGate(use_native=False)
    gate.observe(observations)
    gate.register_role("source", ["fonte", "origem", "emissor", "terminal"])
    gate.register_role("action", ["transmite", "envia", "remete"])
    gate.register_role("payload", ["sinal", "dado", "pacote", "quadro"])
    gate.register_role("destination", ["destino", "alvo", "receptor", "servidor"])
    gate.register_pattern(("source", "action", "payload", "destination"))
    return gate


def main():
    probes = [
        ("fonte transmite sinal destino", "accept"),
        ("origem remete pacote servidor", "accept"),
        ("destino transmite sinal fonte", "reject"),
        ("fonte sinal transmite destino", "reject"),
        ("fonte transmite misterio destino", "fail_closed"),
    ]

    scenarios = []
    scenarios.append(("baseline", list(BASE_OBSERVATIONS)))

    shuffled = list(BASE_OBSERVATIONS)
    random.Random(7).shuffle(shuffled)
    scenarios.append(("shuffled", shuffled))

    noisy = list(BASE_OBSERVATIONS) + NOISE * 25
    random.Random(11).shuffle(noisy)
    scenarios.append(("heavy_noise", noisy))

    imbalanced = []
    imbalanced.extend([BASE_OBSERVATIONS[0]] * 80)
    imbalanced.extend([BASE_OBSERVATIONS[1]] * 10)
    imbalanced.extend([BASE_OBSERVATIONS[2]] * 3)
    imbalanced.extend([BASE_OBSERVATIONS[3]] * 1)
    scenarios.append(("frequency_imbalance", imbalanced))

    rows = []
    baseline_signature = None
    for name, observations in scenarios:
        gate = build(observations)
        calibrated = gate.calibrate()
        decisions = []
        for text, expected in probes:
            r = gate.resolve(text)
            decisions.append((text, expected, r.decision, r.coverage, r.threshold, r.margin, r.reason))
        signature = [(x[0], x[2]) for x in decisions]
        if baseline_signature is None:
            baseline_signature = signature
        rows.append({
            "scenario": name,
            "calibrated": calibrated,
            "threshold": gate.threshold,
            "margin": gate.calibration_margin,
            "decision_signature_matches_baseline": signature == baseline_signature,
            "all_expected": all(expected == decision for _, expected, decision, *_ in decisions),
            "decisions": [
                {"text": t, "expected": e, "decision": d, "coverage": c, "threshold": th, "margin": m, "reason": reason}
                for t, e, d, c, th, m, reason in decisions
            ],
        })

    output = {
        "experiment": "trajectory temporal robustness",
        "rows": rows,
        "summary": {
            "scenarios": len(rows),
            "all_calibrated": all(r["calibrated"] for r in rows),
            "all_expected": all(r["all_expected"] for r in rows),
            "all_decision_signatures_stable": all(r["decision_signature_matches_baseline"] for r in rows),
            "thresholds": {r["scenario"]: r["threshold"] for r in rows},
            "margins": {r["scenario"]: r["margin"] for r in rows},
        },
    }
    print(json.dumps(output, ensure_ascii=False, indent=2))

    assert output["summary"]["all_calibrated"]
    assert output["summary"]["all_expected"]
    assert output["summary"]["all_decision_signatures_stable"]


if __name__ == "__main__":
    main()
