from __future__ import annotations

import json

from memoria_resolutiva.role_structural_router_v96 import RoleStructuralRouterV96


def build_sensor_router() -> RoleStructuralRouterV96:
    router = RoleStructuralRouterV96(
        role_threshold=0.30,
        role_min_margin=0.02,
        structural_threshold=0.45,
        structural_min_margin=0.08,
        relation_window=5,
        max_context_relabels=2,
    )
    router.observe(
        [
            "sensor mede temperatura ambiente",
            "medidor detecta umidade sala",
            "dispositivo registra pressao recinto",
            "sonda mede calor exterior",
            "sensor detecta calor exterior",
            "sonda registra temperatura ambiente",
            "ambiente fornece temperatura sensor",
            "sala fornece umidade medidor",
            "exterior fornece calor sonda",
            "recinto fornece pressao dispositivo",
        ]
    )
    router.register_role("device", ["sensor", "medidor", "dispositivo"])
    router.register_role("measure", ["mede", "detecta", "registra"])
    router.register_role("quantity", ["temperatura", "umidade", "pressao"])
    router.register_role("environment", ["ambiente", "sala", "recinto"])
    router.register_intent_pattern("device_measures_environment", ["device", "measure", "quantity", "environment"])
    router.register_intent_pattern("environment_reports_device", ["environment", "measure", "quantity", "device"])
    return router


def build_education_router() -> RoleStructuralRouterV96:
    router = RoleStructuralRouterV96(
        role_threshold=0.30,
        role_min_margin=0.02,
        structural_threshold=0.45,
        structural_min_margin=0.08,
        relation_window=5,
        max_context_relabels=2,
    )
    router.observe(
        [
            "professor explica conceito aluno",
            "docente ensina tema estudante",
            "mestre apresenta ideia aprendiz",
            "instrutor explica nocao discente",
            "professor ensina nocao discente",
            "instrutor apresenta conceito aluno",
            "aluno explica conceito professor",
            "estudante ensina tema docente",
            "aprendiz apresenta ideia mestre",
            "discente explica nocao instrutor",
        ]
    )
    router.register_role("teacher", ["professor", "docente", "mestre"])
    router.register_role("explain", ["explica", "ensina", "apresenta"])
    router.register_role("concept", ["conceito", "tema", "ideia"])
    router.register_role("student", ["aluno", "estudante", "aprendiz"])
    router.register_intent_pattern("teacher_to_student", ["teacher", "explain", "concept", "student"])
    router.register_intent_pattern("student_to_teacher", ["student", "explain", "concept", "teacher"])
    return router


def evaluate_domain(name: str, router: RoleStructuralRouterV96, valid, adversarial) -> dict[str, object]:
    valid_rows = []
    correct = 0
    for text, expected in valid:
        result = router.resolve_text(text)
        ok = result.concept_id == expected
        correct += int(ok)
        valid_rows.append({
            "text": text,
            "expected": expected,
            "predicted": result.concept_id,
            "canonical_roles": list(result.canonical_roles),
            "correct": ok,
        })

    adversarial_rows = []
    false_positives = 0
    for text in adversarial:
        result = router.resolve_text(text)
        fp = result.concept_id is not None
        false_positives += int(fp)
        adversarial_rows.append({
            "text": text,
            "predicted": result.concept_id,
            "canonical_roles": list(result.canonical_roles),
            "false_positive": fp,
        })

    return {
        "domain": name,
        "valid_recall": correct / len(valid),
        "adversarial_false_positive_rate": false_positives / len(adversarial),
        "valid": valid_rows,
        "adversarial": adversarial_rows,
    }


def main() -> None:
    sensor = evaluate_domain(
        "sensor",
        build_sensor_router(),
        [
            ("sonda mede calor exterior", "device_measures_environment"),
            ("exterior fornece calor sonda", "environment_reports_device"),
        ],
        [
            "sonda calor mede exterior",
            "exterior calor fornece sonda",
            "calor mede sonda exterior",
        ],
    )
    education = evaluate_domain(
        "education",
        build_education_router(),
        [
            ("instrutor explica nocao discente", "teacher_to_student"),
            ("discente explica nocao instrutor", "student_to_teacher"),
        ],
        [
            "instrutor nocao explica discente",
            "discente nocao explica instrutor",
            "nocao explica instrutor discente",
        ],
    )
    domains = [sensor, education]
    output = {
        "domains": domains,
        "mean_valid_recall": sum(float(row["valid_recall"]) for row in domains) / len(domains),
        "mean_adversarial_false_positive_rate": sum(
            float(row["adversarial_false_positive_rate"]) for row in domains
        ) / len(domains),
    }
    print(json.dumps(output, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
